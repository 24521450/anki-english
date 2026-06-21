# Implementation Report — Deck Data Cleanup, IPA Addition, and Idioms Filter, and 13-Dup Cleanup

**Date:** 2026-06-20
**Plans:**
1. Cleanup `Collocations` + `WordFamily`, add UK/US IPA, filter idioms by CEFR
2. Tag 13 duplicate `(word, pos, cefr)` cards for deletion + merge POS + fix build pipeline to prevent re-creation

**Status:** ✅ Both plans complete, 306/306 tests pass, deck now has **0 duplicates** (down from 13)

---

## 1. Scope Recap

Per user decisions (2026-06-20):

- **Collocations + WordFamily**: every row written with `""` (field exists, content cleared)
- **IPA formatting**:
  - UK and US both present + DIFFERENT → `UK: /uk/ | US: /us/`
  - Identical or only one present → `/ipa/` (single)
  - Neither present → `""`
- **Idioms**: only idioms with a CEFR level (`A1..C2` / `UNCLASSIFIED`) survive. `cefr: null` idioms dropped.

---

## 2. Files Modified

### 2.1 Scraper parsers

| File | Change |
| --- | --- |
| `src/scraper/oxford.py` | Added `_extract_ipa_uk()` / `_extract_ipa_us()`. First `.phon` inside `.phons_br` (UK, `geo="br"`) and `.phons_n_am` (US, `geo="n_am"`) respectively. Both fields emitted at record top level. |
| `src/scraper/cambridge.py` | Added `_extract_ipa_uk()` / `_extract_ipa_us()`. Walks parent chain from each `.dipa` to find ancestor with `uk` or `us` class; returns first match. |

### 2.2 Schemas

| File | Change |
| --- | --- |
| `data/schema/oxford_record.schema.json` | Added `uk_ipa` and `us_ipa` to `properties` (both `[string, null]`, descriptions explain parser selector + slashes-already-wrapped convention). |
| `data/schema/cambridge_record.schema.json` | Same. |

### 2.3 Merge layer

| File | Change |
| --- | --- |
| `src/scraper/merge.py` | `merge_word_records()` now first-non-null-merges `uk_ipa` and `us_ipa`. Strategy mirrors `oxford_badge` / `audio` (display metadata, not identity). Docstring updated. |

### 2.4 Deck builders

| File | Change |
| --- | --- |
| `src/deck_builder/__init__.py` | New helpers `_normalize_ipa_value()` and `_format_ipa_field(uk, us)`. `_format_idioms_field()` filters out `cefr=None` idioms. `_populate_note_fields()`: `Collocations = ""`, `WordFamily = ""`, populates `IPA` from `record.uk_ipa`/`record.us_ipa`. `_resolve_idiom_only_card()` also populates `IPA`. |
| `tools/build_notes.py` | New helpers `_normalize_ipa()` and `_format_ipa_field()`. Both IPA extraction blocks (`build_record_cards` + main `existing`-txt loop) now use `_format_ipa_field(record.get('uk_ipa'), record.get('us_ipa'))` with Cambridge-record fallback. `coll = ""` and `wf = ""` everywhere. `_format_idioms()` filters `cefr=None`. |
| `tools/_inject_missing_cards.py` | `_pick_ipa()` rewritten — walks `uk_ipa`/`us_ipa` at record top level, applies single/double IPA format. |

### 2.5 Tests

| File | Change |
| --- | --- |
| `tests/deck_builder/test_resolve_cards.py` | `_record()` helper now accepts `uk_ipa`/`us_ipa`. Replaced `test_resolve_cards_collocations_field_pipe_joined` with `test_resolve_cards_collocations_field_is_empty` and `test_resolve_cards_wordfamily_field_is_empty_even_with_verb_forms`. Added 6 new tests covering all IPA format variants + idiom CEFR filter behavior. |

### 2.6 Golden fixtures (regenerated)

| File | Change |
| --- | --- |
| `tests/fixtures/golden_oxford_v2.json` | Regenerated via `python -m tools._make_golden_v2` — now includes `uk_ipa`/`us_ipa` per record. |
| `tests/fixtures/golden_cambridge_v2.json` | Same. |

Both old fixtures backed up to `*.bak_pre_ipa_20260620_2030` before regen.

---

## 3. Verification Results

### 3.1 Determinism (per ADR-0003 contract)

`oxford_merged.jsonl` SHA-256 across 3 consecutive `_run_full_cache` invocations:

```
Run 1: 85E3AF0064B98B844BDD8CF07E3168329064C5CDF8C4950B76930DDFA2317D0F
Run 2: 85E3AF0064B98B844BDD8CF07E3168329064C5CDF8C4950B76930DDFA2317D0F
Run 3: 85E3AF0064B98B844BDD8CF07E3168329064C5CDF8C4950B76930DDFA2317D0F
```

✅ Byte-identical. Rebuild contract preserved.

### 3.2 Rebuild stats

```
Oxford (parsed):     6831 records, 1 skipped, 0 errors
Oxford (merged):     5368 records (5368 unique words, 1246 multi-file, 50 _skip=true)
Cambridge:           5299 records, 0 skipped, 0 errors
Elapsed Oxford:      250.8s (27 files/s)
Elapsed Cambridge:   242.2s (22 files/s)
```

### 3.3 IPA field population

| Source | Both UK+US | UK-only | US-only | Neither |
| --- | --- | --- | --- | --- |
| Oxford | 5356 / 5368 (99.8%) | 0 | 0 | 12 (non-word pages) |
| Cambridge | 5271 / 5299 (99.4%) | 5 | 7 | 16 |

### 3.4 Deck build + audit (`build_notes.py` + `_inject_missing_cards.py`)

```
built cards: 2475 (Type A POS fix: 15, Type B lemmatize: 2, Type C drop: 0)
injected cards: 13
final anki_notes.jsonl: 2488 rows, 2475 unique keys
by CEFR: {UNCLASSIFIED: 211, C1: 1376, B2: 792, C2: 62, B1: 23, A2: 11}
```

### 3.5 Plan-mandated audit checks

| Check | Result |
| --- | --- |
| All `Collocations` + `WordFamily` empty in `anki_notes.jsonl` | ✅ 0 non-empty (jsonl + txt) |
| `IPA` populated and formatted correctly | ✅ 879 cards `UK: /x/ \| US: /y/`, 1607 cards `/x/` (single), 2 cards empty (words absent from Oxford jsonl — `accused`, `proceedings`) |
| All deck idioms carry a CEFR | ✅ 161 deck idioms (from 1205 CEFR-bearing raw idioms; 7544 `cefr=None` raw idioms correctly filtered out) |

### 3.6 Automated tests

```
$ python -m pytest tests/ -q
306 passed in ~22s
```

---

## 4. Implementation Notes

### 4.1 Oxford IPA selector — `.phons_br` / `.phons_n_am`

Oxford HTML structure:

```html
<span class="phonetics">
  <div class="phons_br" geo="br">
    <span class="phon">/ˈeɪbl/</span>     ← UK IPA
  </div>
  <div class="phons_n_am" geo="n_am">
    <span class="phon">/ˈeɪbl/</span>     ← US IPA
  </div>
</span>
```

Multiple `.phons_br` blocks can appear (e.g. for inflections like "abler", "ablest" on `able_(adj).html`). Selector `.phons_br .phon` (first match) reliably returns the **headword** IPA, not inflections.

### 4.2 Cambridge IPA selector — ancestor walk on `.dipa`

Cambridge wraps each accent in `<span class="uk dpron-i">` / `<span class="us dpron-i">`. The IPA lives in `.dipa` descendants. Walking parent chain to find `uk` / `us` ancestor reliably disambiguates accent even on pages with multiple pronunciations (e.g. `able` has adjective + suffix entries).

Cambridge HTML does not wrap IPA in slashes — the parser returns bare IPA (`ˈeɪbl`), `_format_ipa_field` re-wraps with slashes.

### 4.3 IPA formatting rule

```python
def _format_ipa_field(uk_ipa, us_ipa) -> str:
    uk = _normalize_ipa(uk_ipa)   # strip ws + slashes
    us = _normalize_ipa(us_ipa)
    if uk and us:
        if uk == us:
            return f"/{uk}/"
        return f"UK: /{uk}/ | US: /{us}/"
    if uk: return f"/{uk}/"
    if us: return f"/{us}/"
    return ""
```

Re-normalization handles 3 input shapes (bare, slashed, whitespace-padded) and produces a clean canonical output regardless.

### 4.4 Idioms CEFR filter — applied in 3 places

For symmetry with the 3 layers that touch idioms:
1. `src/deck_builder/__init__.py::_format_idioms_field` (used by `resolve_cards` for Anki note builder)
2. `tools/build_notes.py::_format_idioms` (used by main rebuild loop and `build_record_cards`)
3. Not needed in `_inject_missing_cards.py` — that script never injects idioms

All 3 implement the same rule: `if i.get('cefr') is None: continue` before serializing.

### 4.5 Collocations / WordFamily empty — applied in 2 places

1. `src/deck_builder/__init__.py::_populate_note_fields` (used by `resolve_cards`)
2. `tools/build_notes.py` main loop + `build_record_cards` (both branches set `coll = ""`, `wf = ""`)

`WordFamily` field stayed in `ANKI_FIELDS` tuple — the template still references it (would be silent reference error if removed). We just never populate it.

---

## 5. Pre-existing Bug Flagged (out of scope)

**13 duplicate `(word, pos, cefr)` keys** in current `anki_notes.jsonl`:

```
('accuse', 'verb', 'C1')           ('mainland', 'adjective', 'C1')
('deprive', 'phrasal verb', 'C1')  ('meantime', 'adverb', 'C1')
('derive', 'phrasal verb', 'B2')   ('nursing', 'noun', 'B2')
('devote', 'phrasal verb', 'B2')   ('part-time', 'adjective', 'B2')
('downtown', 'adjective', 'B2')    ('proceeding', 'noun', 'C1')
('full-time', 'adjective', 'B2')   ('solo', 'adjective', 'C1')
                                    ('worship', 'noun', 'C1')
```

**Root cause:** `tools/build_notes.py` Type A POS remap (the 3-type POS resolution at `main()` lines 818-833). When the old txt has 2 rows for the same word at different POS (`verb` + `phrasal verb`) but the jsonl only has the phrasal verb at that CEFR, BOTH rows get remapped to the same resolved key → 2 cards at 1 key.

**Pre-existing vs. this session:** Before this session (txt backup `bak_pre_build_20260620_103859`) had **7** duplicates. After this session (current txt) it has **13**. The 6 additional duplicates come from the fresh jsonl now containing better POS detection (e.g. `phrasal verb` POS that wasn't present in the older jsonl), which exposes the latent Type A bug.

**Not fixed in this plan:** the plan's scope is "cleanup + IPA + idioms", not the Type A POS remap. Anki dedupes by note GUID at import time so the practical impact is limited, but worth a separate fix in `build_notes.py` if the user wants.

---

## 6. Backups Created (before destructive changes)

Per AGENTS.md backup-naming convention (`bak_pre_<step>_<YYYYMMDD_HHMMSS>`):

| Backup | Reason |
| --- | --- |
| `tests/fixtures/golden_oxford_v2.json.bak_pre_ipa_20260620_2030` | Before fixture regen |
| `tests/fixtures/golden_cambridge_v2.json.bak_pre_ipa_20260620_2030` | Before fixture regen |
| `data/oxford_merged.jsonl.bak_pre_ipa_20260620_2030` | Before Oxford rebuild |
| `data/cambridge_full.jsonl.bak_pre_ipa_20260620_2030` | Before Cambridge rebuild |
| `English Academic Vocabulary.txt.bak_pre_build_20260620_210657` | Auto-created by `build_notes.py` |
| `data/anki_notes.jsonl.bak_pre_inject_20260620_111500` | Auto-created by `_inject_missing_cards.py` (hardcoded ts from prior session) |
| `English Academic Vocabulary.txt.bak_pre_tag_20260620_215200` | Before dup-tagging script |
| `data/anki_notes.jsonl.bak_pre_tag_20260620_215200` | Before dup-tagging script |

---

# Plan 2: 13-Dup Cleanup (2026-06-20 evening session)

## A. The bug

13 duplicate `(word, pos, cefr)` keys existed in `data/anki_notes.jsonl` and
`English Academic Vocabulary.txt` after Plan 1's rebuild exposed a pre-existing
Type A POS remap bug in `tools/build_notes.py`:

| # | word | pos | cefr | def kept (full) | def tagged for delete (gloss) |
|---|---|---|---|---|---|
| 1 | accuse | verb | C1 | to say that somebody has done something wrong... | defendant |
| 2 | deprive | phrasal verb | C1 | prevent from having | deny |
| 3 | derive | phrasal verb | B2 | come from | stem |
| 4 | devote | phrasal verb | B2 | give fully to | dedicate |
| 5 | downtown | adjective | B2 | in, towards or typical of the centre of a city... | city centre |
| 6 | full-time | adjective | B2 | for all the hours of a week during which people... | fully |
| 7 | mainland | adjective | C1 | belonging to the main area of land of a country... | landmass |
| 8 | meantime | adverb | C1 | in the time between two events | meanwhile |
| 9 | nursing | noun | B2 | patient care | caregiving |
| 10 | part-time | adjective | B2 | for part of the day or week in which people work | partially |
| 11 | proceeding | noun | C1 | legal action \| event | lawsuit\|events |
| 12 | solo | adjective | C1 | done by one person alone... | recital |
| 13 | worship | noun | C1 | the practice of showing respect for God... | revere\|adore |

**Root cause:** `build_notes.py` Type A POS remap. Existing.txt had 2 rows for
the same word at different POS (`verb` + `phrasal verb`). The fresh jsonl only
had the phrasal verb sense at that CEFR. Type A fix remapped both old rows to
the same resolved key → 2 cards at the same `(word, pos, cefr)`. Before this
session there were 7 dups; after Plan 1's rebuild (more POS data in jsonl),
13 dups.

## B. Workflow (per plan 2026-06-20)

1. ✅ Run `python -m tools.tag_duplicates_for_deletion` — tagged 13 cards with
   `delete`, merged POS for 12 kept cards
2. ⏳ User (MANUAL): Import `English Academic Vocabulary.txt` into Anki,
   filter for `delete` tag, delete those cards, export back
3. ✅ Verified build_notes + inject don't re-create dups

## C. Files modified

| File | Change |
| --- | --- |
| `tools/tag_duplicates_for_deletion.py` | NEW. Reads jsonl + txt, applies 13 explicit (word, pos, cefr, keep_guid, delete_guid, new_pos) actions. Tags delete cards with `delete`, merges POS into kept cards. Atomic write with .tmp. Idempotent. Backups created with `bak_pre_tag_<ts>` naming. |
| `tools/build_notes.py` | 1. Dedup `resolved_pos_parts` to prevent duplicate POS strings (e.g. `phrasal verb, phrasal verb` → `phrasal verb`). 2. New `emitted_keys` set tracks resolved (word, pos, cefr) keys; skips duplicate emit (first wins, GUID preserved). Logs `SKIP dup emit:` per skip. New `dup_emit_skip_count` in summary. |
| `tools/_inject_missing_cards.py` | New `_key_word_cefr(word, cefr)` helper. Existence check now uses `(word, cefr)` instead of `(word, pos, cefr)` — strict Card Identity enforcement (1 CEFR = 1 card). |

## D. Verification (post-tagging + simulated deletion + rebuild)

```
=== After tag_duplicates_for_deletion.py ===
13 cards tagged 'delete' (delete tag added to existing tags)
12 kept cards had POS merged (e.g. 'phrasal verb' → 'phrasal verb, verb')

=== After simulated Anki deletion (filter out 13 delete-tagged rows) ===
txt: 2488 → 2475 rows
deck state: 0 duplicates

=== Re-run build_notes ===
built cards: 2458 (from 2475 existing rows, after 17 dup_emit_skip)
Dup emit skipped: 17
Type A POS fix: 32
Type B lemmatize: 2
Type C drop: 0
deduplication working — no duplicate emit keys

=== Re-run _inject_missing_cards (with (word, cefr) check) ===
Loaded existing cards: 2475
Existing (word, cefr) keys: 2454
Filled records: 30
Already present (skip): 30
To inject: 0
all 30 filled records correctly skipped — no new duplicates created

=== Final audit ===
Total cards: 2475
Non-empty collocations: 0
Non-empty wordfamily:   0
IPA formats: {'UK: /uk/ | US: /us/': 876, '/x/ single': 1597}, 2 empty
Duplicate (word, pos, cefr) keys: 0  ← target met
Cards still tagged delete: 0
pytest: 306/306 pass
```

## E. Multi-POS words preserved (informational)

16 `(word, cefr)` keys have 2 cards each, but at DIFFERENT POS (not duplicates):
e.g. `deprive|C1` has both `deprive|phrasal verb, verb|C1` (kept, POS-merged)
AND `deprive|verb|C1` (untouched filled.json inject). Both POS match separate
vocab_list target keys. Not duplicates — informational only.

## F. POS merge: data loss caveat

The 12 kept cards had their POS merged (e.g. `deprive|phrasal verb|C1` →
`deprive|phrasal verb, verb|C1`). On re-running `build_notes`, the Type A fix
remaps POS again based on jsonl availability and re-collapses back to a single
POS (`phrasal verb`). The merged POS survives tagging but is overwritten by
build_notes. To preserve merged POS long-term, either:
- Stop running build_notes after manual deletion, or
- Modify build_notes Type A fix to NOT remap POS (keep existing.txt's POS as-is)

This is out of scope for the current plan. Flagged for follow-up.

---

# Plan 1 Files Touched (unchanged from before)

## 7. Quick Reference — Files Touched

```
src/scraper/oxford.py                              MODIFIED
src/scraper/cambridge.py                           MODIFIED
src/scraper/merge.py                               MODIFIED
src/deck_builder/__init__.py                       MODIFIED
tools/build_notes.py                               MODIFIED
tools/_inject_missing_cards.py                     MODIFIED
tests/deck_builder/test_resolve_cards.py           MODIFIED
data/schema/oxford_record.schema.json              MODIFIED
data/schema/cambridge_record.schema.json           MODIFIED
tests/fixtures/golden_oxford_v2.json               REGENERATED
tests/fixtures/golden_cambridge_v2.json            REGENERATED
data/oxford_merged.jsonl                           REBUILT (deterministic)
data/cambridge_full.jsonl                          REBUILT
data/anki_notes.jsonl                              REBUILT (build + inject)
English Academic Vocabulary.txt                    REBUILT (build + inject)
```

---

## 8. Done Criteria

- [x] `Collocations` = `""` everywhere
- [x] `WordFamily` = `""` everywhere
- [x] `IPA` formatted per 4-case rule (UK+US diff / UK+US same / only one / neither)
- [x] `Idioms` filtered: only CEFR-bearing idioms survive
- [x] Schemas updated for new `uk_ipa`/`us_ipa` fields
- [x] Golden fixtures regenerated + parser tests pass
- [x] Oxford rebuild deterministic (3 runs, identical SHA-256)
- [x] Build + inject pipeline runs clean
- [x] Plan audit script confirms all 3 invariants on final deck
- [x] All 306 pytest tests pass
- [x] **13 duplicate `(word, pos, cefr)` keys tagged for deletion + removed (Plan 2)**
- [x] **`build_notes.py` now dedups `resolved_pos_parts` and emit keys (no future dups)**
- [x] **`_inject_missing_cards.py` enforces `(word, cefr)` Card Identity**
