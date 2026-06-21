# Bug 2 fix + determinism fix — collocation artifact filter, merge-layer reproducibility

**Applied:** 2026-06-13

## Fix #1: Collocation artifact filter

Added `COLLOC_ARTIFACTS = frozenset({"…", "..."})` constant in
`src/scraper/oxford.py` (top of file, near other helpers). Filter
applied in `_extract_collocations()` immediately after extracting
`<li>` text:

```python
items = [_text_of(li) for li in nxt.cssselect("li")]
items = [i for i in items if i and i not in COLLOC_ARTIFACTS]
if items:
    out[cat] = items
```

Filter applies to **every category** (adverb, phrases, verb + X,
X + noun, adjective, etc.), not just "adverb".

## Verification

- `pytest`: 78/78 passing (was 65 baseline, +13 from earlier sessions)
- 2 fixtures regenerated via `python -m tools._make_golden_v2`
  (`oxford_linger_(verb).html`, `oxford_delight_(noun).html`) — only
  the `…` items in their `collocations` lists changed
- Rebuilt `data/oxford_merged.jsonl` from cache: 6,830 → 5,367 merged
  records (normal pipeline output, 50 flagged `_skip`)

## Cascade diff check (Bug 2 pre-fix vs post-fix jsonl)

**Bug 2 changes (intentional):**
- 9,153 definitions had `…`/`...` items removed from their collocations
- 21,986 artifact items removed total
- All 9,153 definitions have **identical** `text` and `cefr` — only
  the `collocations` dict changed

**Collateral changes (NOT caused by Bug 2 — pre-existing
non-determinism in merge layer):**

| Field | Records changed | Cause |
|---|---:|---|
| `source_files` | 574 | Order-only (`os.listdir()` non-determinism) |
| `idioms` | 95 | Picked from different source homonym |
| `oxford_badge` | 72 | Picked from different source homonym |
| `see_also` | 43 | Picked from different source homonym |
| `audio` | 40 | Picked from different source homonym |
| `oxford_lists` | 6 | Picked from different source homonym |
| `verb_forms` | 1 | Picked from different source homonym |

**Root cause of collateral changes:**

The merge layer (`src/scraper/merge.py`) uses "first non-null" logic
for `oxford_badge`, `audio`, `idioms`, etc. The "first" depends on
`os.listdir()` ordering of the cache directory, which is non-
deterministic across rebuilds. When `source_files` order changed
between builds, the merge layer picked a different homonym's
metadata for some words.

**Example:** `transport`
- Old build: `source_files=['oxford_transport_(verb).html', 'oxford_transport_(noun).html']`
  → badge/audio came from `verb` homonym (`B1`, `_gb_2.mp3`)
- New build: `source_files=['oxford_transport_(noun).html', 'oxford_transport_(verb).html']`
  → badge/audio came from `noun` homonym (`A2`, `_gb_1.mp3`)

## Recommended follow-up (NOT in this task)

**Make merge layer deterministic.** Two options:

1. **Sort source_files by `(homonym_index, pos_suffix)`** before
   merging — same input → same output every build.
2. **Sort by name** — simpler, but doesn't preserve "primary" sense
   logic.

Either is a one-line change. Worth doing before any future rebuilds
to ensure reproducible builds.

---

## Determinism fix — applied same session

**Root cause of non-determinism:** `tools/_run_full_cache.py:127` sorted
records by `word` only. Multi-file words (e.g. `transport` has both
`oxford_transport_(verb).html` and `oxford_transport_(noun).html`) have
identical `word` values, so the sort key was a tie. The pre-sort order
from `as_completed()` in the parallel parser leaked through to the
merge layer's "first non-null" picks, causing 574 records to have
non-deterministic `oxford_badge` / `audio` / `idioms` / `see_also` /
`source_files` ordering across rebuilds.

**Fix (1 line):**

```python
# tools/_run_full_cache.py:127
records.sort(key=lambda r: (
    r.get("word") or "",
    (r.get("source_files") or [""])[0],
))
```

Tuple sort is lexicographic; filenames are ASCII
(`oxford_<word>_(<pos>).html`); default `[""]` handles empty/missing
edge cases (verified: 0 records with empty `source_files` in
`oxford_full.jsonl`). Stable on every OS.

## Verification (2-build comparison)

Built `data/oxford_merged.jsonl` twice from cache, SHA-256 compared:

| Build | SHA-256 |
|---|---|
| `deterministic_run1` | `B162E78E2638789CBA888062D1C12689096C6E8CC3B242EECFDB378087A5D3AA` |
| `deterministic_run2` | `B162E78E2638789CBA888062D1C12689096C6E8CC3B242EECFDB378087A5D3AA` |

**PASS: byte-identical.** Same input → same output every build.

## Example: `transport`

| Build | `source_files` | `oxford_badge` | `audio.uk` |
|---|---|---:|---|
| Pre-fix (race-dependent) | `[verb, noun]` or `[noun, verb]` | `B1` or `A2` | `_gb_2.mp3` or `_gb_1.mp3` |
| Post-fix (deterministic) | `[noun, verb]` (alphabetical) | `A2` (noun homonym) | `_gb_1.mp3` |

The deterministic order picks the **alphabetically-first** filename
(`(noun)` < `(verb)`) as the "primary" homonym. This is stable and
predictable. The downside: if a word has historically been presented
from the verb homonym's perspective, the new build will pick the
noun homonym instead. The Anki deck will need a rebuild to reflect
this.

## Diff vs pre-bug2 backup (informational)

The pre-bug2 backup (`oxford_merged.jsonl.bak_pre_bug2_20260613_110052`)
was itself a non-deterministic build, so the diff vs the new
deterministic build still shows collateral changes:

| Field | Records | Cause |
|---|---:|---|
| `source_files` | 655 | Order changed (some pre-bug2 had non-alphabetical order from race) |
| `idioms` | 126 | Picked from a different primary homonym |
| `oxford_badge` | 83 | Same |
| `see_also` | 44 | Same |
| `audio` | 37 | Same |
| `oxford_lists` | 8 | Same |
| `definitions.collocations` | 9,153 | Bug 2 fix (intentional) |

This is **expected**. The pre-bug2 backup was non-deterministic; the
new build is deterministic. They CAN differ. The key invariant —
**deterministic build is byte-stable across runs** — is verified above.

## Impact

- **Anki deck**: needs rebuild. The new `oxford_merged.jsonl` will
  produce slightly different cards for ~700 words (different primary
  homonym for multi-POS words).
- **Phase (b) CEFR audit**: should be re-run after the deck rebuild.
  The 8 outlier patches applied earlier are still valid (they were
  per-card patches, not data-driven).

## Bug 3 — NOT FIXED (correctly diagnosed as not-a-bug)

See session log: the "6,035 perfect match" observation between
`sense.cefr` and `topic.cefr` is real Oxford HTML data (the page
sets both elements to the same value when both are present), not a
scraper bug. The current `_extract_cefr()` already does the right
thing: reads `li.sense[cefr]` directly with no fallback. No change
needed.

## Bug 3 — NOT FIXED (correctly diagnosed as not-a-bug)

See session log: the "6,035 perfect match" observation between
`sense.cefr` and `topic.cefr` is real Oxford HTML data (the page
sets both elements to the same value when both are present), not a
scraper bug. The current `_extract_cefr()` already does the right
thing: reads `li.sense[cefr]` directly with no fallback. No change
needed.
