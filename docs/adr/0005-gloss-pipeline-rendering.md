# ADR 0005 — Gloss pipeline refactor: `|` encoding, validation gate, M3 re-run

**Applied:** 2026-06-18

## Context

The gloss layer in the Anki deck shows 2-6 word learner-friendly paraphrases of
Oxford's verbose definitions, so flashcards load fast and stay focused. Three
problems forced a refactor of the entire gloss pipeline:

1. **`conviction` card bug** — gloss said "guilty verdict | firm belief" but the
   card's example column showed 3 examples (`'Not true!' she said with conviction.`).
   The 2-vs-3 mismatch came from β+γ merging that dropped Oxford's 3rd sense
   (`sincerity`) as a sub-nuance — so the gloss was correct, but the example set
   was wrong. Symptom: learner sees "firm belief" gloss but example about saying
   something with conviction (sincerity sense) — confusing.

2. **M3 hand-typed 889 verdicts with structural bugs** — 89.7% of `rule_b_pick1`
   entries had `gloss == headword` (e.g. `basket` → `'basket'`, `clash` → `'clash'`).
   Plus 82 separator-mismatch typos (`declared '|' but actual ';'` in gloss), 304
   per-chunk word-count violations (chunks >3 words when separator is `;`),
   and 3 headword-in-chunk leaks (`accelerate` → `'speed up; accelerate'`).

3. **No automated check** — every batch M3 produced was a free-form dict edit.
   No gate to catch the structural bugs, no rule enforcement, no audit trail.

## Decision

Three changes, applied together because they're tightly coupled.

### 1. `|` as between-sense separator (was `;`)

The Oxford HTML uses `;` for **two unrelated things**:
- Within a single sense: sub-chunks (`the act of finding sb guilty; the fact
  of having been found guilty` — 1 sense, 2 sub-nuances)
- Between senses: distinct glosses (when rendered to flashcard)

These were conflated. M3 was emitting glosses with `;` and the template parsed
them as if `;` meant between-sense, producing the 2-vs-3 conviction bug.

**Fix:** `|` for between-sense, `;` preserved for within-sense sub-chunks. The
build stage (`tools/build_notes.py`) `DEF_SEPARATOR` and `EX_SEP` changed from
`' ; '` to `'|'`. The `_format_examples(examples, max_n=1)` change ensures
exactly **1 example per sense** so the template's `def[i]` ↔ `ex[i]` index
pairing stays aligned.

### 2. Validation gate (`validate_verdict` in `src/deck_builder/gloss_llm.py`)

4 auto-detectable rules. Return list of violation strings (empty = pass,
non-empty = bad). Never raises — caller decides what to do.

| Check | Catches | Auto-detectable? |
|---|---|---|
| separator/count/content consistency | `declared '|' but actual ';'` (typos) | Yes |
| word count 1-6 total + per-chunk 1-3 (`;`) / 1-4 (`|`) / 1-6 (none) | `>6` words, chunk too long | Yes |
| headword in any chunk | `gloss == headword` self-ref; `; accelerate` leak | Yes |
| no-gloss bypass | decision='no-gloss' skips all checks | Yes |

**Rule A (near-synonym pair) is NOT auto-detectable** — would need a synonym
DB. Verified by M3 + human review. Example: `absurd|adjective|C1: ('ridiculous;
illogical', ';', 2, '2sense_samedomain')` is structurally valid but violates
Rule A semantically.

**Defense-in-depth** — gate is called from 3 sites:
- `GlossVerdict.__post_init__` — warn mode + class counter, never raises
  (backward compat for historical bad verdicts)
- `_m3_rerun_v2.py main()` — raise, skip entry, write to
  `data/simplify_diff/gloss_rerun_violations.json` for audit
- `_apply_glosses_to_txt.py` — warn+skip, keeps original Oxford def for
  that card (defense at apply time, not just generate time)

### 3. M3 re-run for 889 cards

The 889 cards whose `def` field changed format (due to encoding fix) needed
fresh verdicts. `tools/_m3_rerun_v2.py` holds the verdict dict, with **all
fixes appended at end of dict** (Python dict literal last-wins — inserting
mid-dict silently shadowed new entries behind old ones, see "Critical
gotcha" below).

**Stats (final):** 889/889 pass gate, 297/297 tests pass.

| Rule | Count |
|---|---:|
| `2sense_distinct` | 270 |
| `rule_b_pick1` | 212 |
| `2sense_samedomain` | 181 |
| `multi_pos_pick1` | 98 |
| `concrete_1sense` | 55 |
| `rule_b_pick2` | 42 |
| `multi_pos_pick2` | 31 |
| `rule_b_pick2_addendum` | 1 |

## Trade-offs

| Alternative | Why not chosen |
|---|---|
| Auto-fix gate (e.g. truncate over-long chunks, replace self-ref with synonym) | Unsafe — auto-truncate can mung meanings (proven in 30-word pilot earlier this session, 7/30 pass). Auto-synonym needs DB. **Gate reports only, M3 decides.** |
| Stricter Rule B (3+ senses always pick 2) | Over-merge would force picking 2 of 3 senses even when 1 covers all. Kept Rule B as "all senses are variants → 1, distinct domains → 2" but with **M3's responsibility to be honest about variant vs distinct**. |
| Gate raises in `__post_init__` | Would crash `load_existing_verdicts()` for the 117 historical self-ref verdicts in the kept 1,588, blocking all Anki rebuild. Warn-mode counter keeps loader working. |
| Match on `hash` for merge | Old `gloss_all_verdicts.json` entries hash differently than new (old hash = pre-encoding def format, new hash = post-encoding). Match on `(word, pos, cefr)` key. |
| Skip step 3 (re-bake `.apkg`) | If user only re-imports `.txt` into existing Anki, no need. If sharing deck or fresh install, .apkg is required. Documented as user-decision. |

## Critical gotcha — Python dict literal "last wins"

When patching a Python dict literal by inserting new entries BEFORE existing
entries with the same key, the existing later entry **silently overrides** the
new one. Edit tool reports success but the value in memory is the OLD one.

**Detection:**
```bash
python -c "import importlib.util as u; s=u.spec_from_file_location('m','...'); \
  m=u.module_from_spec(s); s.loader.exec_module(m); \
  print(m.M3_VERDICTS['your_key|here'])"
```
If printed value differs from what you just edited → shadowed.

**Fix:** Always insert new dict entries just BEFORE the closing `}` of the dict.
Use a one-time script (`tools/_move_fixes.py`) to migrate if needed.

**Cost of this bug:** silent ~10% of all batch-1-4 fixes didn't take effect.
Caught by `tools/_verify_fixes.py` after batch 4 produced only +10 delta (vs
expected +25-40). One-time move script fixed 90+ shadowed entries.

## Files

**Modified:**
- `src/deck_builder/gloss_llm.py` — added `validate_verdict`, expanded
  `VALID_RULE_CODES`, added `__post_init__`, filtered `load_existing_verdicts`
  to drop schema-extra fields
- `tools/build_notes.py` — `DEF_SEPARATOR='|'`, `EX_SEP='|'`,
  `_format_examples(max_n=1)`
- `src/deck_builder/gloss_llm.py` prompt — clarified separator semantics
  (Rule A, Rule B, Rule B addendum, Rule C safety net)
- `tools/_m3_rerun_v2.py` — per-entry skip pattern + `VIOLATIONS_OUT` file
- `tools/_apply_glosses_to_txt.py` — defense-in-depth gate hook

**New:**
- `tests/deck_builder/test_validate_verdict.py` — 23 tests (5 categories ×
  ~5 cases each)
- `tools/_move_fixes.py` — one-time fix for last-wins shadowing
- `data/simplify_diff/gloss_rerun_violations.json` — per-batch violations
  tracked for audit

**Removed (debug scripts, can re-create if needed):**
- `tools/_diag.py`, `tools/_audit_glosses.py`, `tools/_diag_sep.py`,
  `tools/_diag_overlap.py`, `tools/_list_pure_sep.py`,
  `tools/_list_batch[1-9].py`, `tools/_verify_fixes.py`,
  `tools/_final_stats.py`, `tools/_list_streamC[1-3].py`,
  `tools/_list_mp[1-3].py` — debug only, can be moved to `tools/_debug/`
  or deleted

## Verification

- `pytest`: 297/297 pass (was 273 before gate tests, +24 new gate tests)
- `python -m tools._m3_rerun_v2`: 0 violations, 889/889 verdicts
- `python -m tools._apply_glosses_to_txt`: 2,352 cards replaced,
  119 kept original, 117 gate-skipped (historical self-ref in kept
  1,588, outside regen scope)
- Anki spot-check `conviction`: def = "guilty verdict | firm belief",
  ex = 3 chunks, card renders 2 sense rows (ex[2] dropped per
  Sense Cap's ex-drop=def-drop invariant)

## Open question / Known gaps

The 1,588 kept verdicts (pre-fix) have **not been re-audited** for semantic
quality. Three categories tracked in `data/simplify_diff/known_gaps.json`:

1. **134 self-ref / headword-leak** (gate-detectable, 117 narrow + 17 broader):
   auto-detected by gate's headword-in-chunk check, gate-skipped at apply
   time, cards keep Oxford def. Fix: 30-40 min M3 regen pass.

2. **20 2-chunk `;` with ~14 likely Rule A violations** (semantic check):
   visible in `tools/_audit_2chunk.py` output. Spot-check of 8/20 confirmed
   near-synonym pattern (e.g. `aesthetic → 'artistic; beauty-related'`).
   Conservative estimate: 14 cases.

3. **Up to 920 1-chunk verdicts with possible Rule B under-collapse**:
   kept set is 98.7% 1-chunk vs rerun's 40.8% 1-chunk. Gap = 920 verdicts
   that M3 pre-fix may have over-collapsed. Cannot verify without
   re-reading source defs. Estimate: 200-500 actual issues (10-30% of gap).
   Total estimated issues in kept: **148-1068 of 1,588** depending on
   how aggressively we read the chunk-distribution gap.

**Why this matters for ADR accuracy:**
- DO NOT claim "100% of deck has gloss" — 117-134 cards use Oxford fallback
- DO NOT claim "All verdicts pass semantic check" — 148-1068 unverified
- DO claim: "889/889 re-generated verdicts pass structural gate;
  2,352/2,479 cards have replaced glosses; remaining 1,588 kept verdicts
  have not been re-audited for Rule A / Rule B under-collapse"

**Next session P1**: spot-audit 100 random kept verdicts (30 min) to
measure actual violation rate. This is the only honest way to know
whether the kept set is "mostly fine" or "mostly broken".

See `data/simplify_diff/known_gaps.json` for full tracking, audit scripts,
and fix options.

---

## Addendum 2026-06-18 (cont'd) — known_leak bucket + 16-card surgical fix

### `known_leak_unfixed` bucket state (2026-06-18)

After Task A fix:
- `known_leak_unfixed`: 1 (just `pace|unknown,unknown|UNCLASSIFIED` — separate
  scraper task, deferred)
- Will drop to 0 after Task B (pace scraper fix)
- Bucket code retained (not removed) because: (1) zero cost when empty,
  (2) catches future hidden-leak regressions if apply script or
  gloss pipeline change.

### Caveat: no-gloss verdicts MUST clear `gloss` field

When applying `decision="no-gloss"`, also set `gloss=""` in the verdict.
Otherwise the audit's `is_applied` check matches (txt has old phrase,
verdict's old gloss is the same phrase) → `has_hidden_leak` fires →
card goes to `known_leak_unfixed` instead of `skip_fallback`.

**Example burn:** `behalf → "on behalf of"` (no-gloss, headword unavoidable).
- Without clear: audit sees `is_applied=True` (txt "on behalf of" == verdict
  "on behalf of"), then `has_hidden_leak=True` ("behalf" in "on behalf of"),
  → `known_leak_unfixed` (wrong).
- With clear: audit sees `is_applied=False` (txt "on behalf of" != ""), →
  `skip_fallback` (correct).

Fix: `tools/_fix_known_leaks.py` already handles this. Documented here
to prevent re-discovery.

### Final state after Task A (2026-06-18)

| Bucket | Count | Δ from pre-fix |
|---|---:|---:|
| skip_fallback | 119 | +2 (behalf, meantime) |
| unverified_rule_a | 1,445 | 0 |
| pass | 963 | +14 (surgical replaces) |
| known_leak_unfilled | 1 | -16 (pace only remains) |
| not_yet_run | 0 | 0 |

Total: 2,528 records, 297/297 tests pass, no regression.

### Task B (pace scraper fix) — deferred to next session

The single remaining `known_leak_unfilled` card is a scraper bug, not a
gloss issue:

- Card rác: `pace|unknown,unknown|UNCLASSIFIED` with def = "PACE act"
  (Police and Criminal Evidence Act stub, NOT the word "pace" = "speed")
- Real entry: `pace_1_(noun)` Oxford URL → 2 senses both B2, same domain
  (rate of movement + rate at which something happens)
- Expected new card: `pace|noun|B2` with gloss `"speed"` (Rule B pick1, 1 chunk)

When done, `known_leak_unfilled` will be 0 (returns to 4-bucket spec).

### Caveat for Task B: tag rác card TRƯỚC khi scrape

Tag the rác card with `delete` in Anki BEFORE running scraper, to
avoid having 2 `pace` cards in deck simultaneously (race condition
between scrape and delete).

---

## Addendum 2026-06-18 — Apply script disambiguator bug + spot-audit results

### Apply script disambiguator bug (FIXED)

**Failure mode 1 (silent fail, 3 cards):** The apply script's lookup
stripped disambiguator ` (xxx)` from word, so the lookup key for txt card
`counter (argue against)` became `("counter", "verb", "C1")`. The verdict
dict had only the base-word ghost verdict for `counter`, not the
disambiguated streamD verdict. Lookup failed → card kept Oxford def.
**Visible in audit as `skip_fallback`.**

**Failure mode 2 (active corruption, 3 cards):** Same stripped-key
lookup, but the ghost verdict happened to exist with the right (word, pos,
cefr) key. The apply used the ghost verdict's gloss. For `grave (for dead
person)|noun|C1`, the ghost gloss was `burial site` — coincidentally
correct, but the streamD verdict `burial site` was shadowed.
**DANGEROUS: structurally valid gloss, wrong source, marked `pass` in audit.**

**Root cause:** `parts[3].split(' (')[0]` in apply stripped disambiguator
BEFORE lookup. The ghost verdicts for the base word are the trap.

**Fix:** `tools/_apply_glosses_to_txt.py:_lookup_verdict()` —
- Try full key (with disambiguator) FIRST
- If no match AND word has disambiguator AND disambiguated siblings
  exist in dict → return None (force skip_fallback, NEVER match ghost)
- Else fall back to base-word key (safe when no disambiguated siblings)

**Result:** all 6 disambiguated streamD cards now use streamD verdicts.
3 cards moved from `skip_fallback` → `pass` (counter x2, strip narrow).
3 cards stayed `pass` but source is now `streamD` (grave x2, strip remove).

### Spot-audit 100 sample results (2026-06-18)

100 random `unverified_rule_a` verdicts M3-reviewed manually (seed 20260618):
- **98 pass (98%)**
- **2 replace (2%):**
  1. `competitive (adjective, B1)`: gloss `rivalry-driven; ambitious` →
     `wanting to win` (RULE A: near-synonym pair, can't use `competitive`
     as gloss = self-ref, use 2-word paraphrase)
  2. `trigger (verb, C2)`: gloss `traumatize` → `cause distress`
     (GLOSS TOO STRONG: def says upset/anxious, traumatize implies lasting
     trauma)

**Extrapolation to 1,470 remaining unverified_rule_a:** ~30 cards (2%)
likely need fix. Much lower than the 6-10% estimate from 200-batch pilot
(latter was based on looser M3 era with less Rule A discipline).

**No Rule B under-collapse evidence in 100 sample** (98% were 1-chunk for
genuinely 1-sense defs). Earlier 920-verdict gap estimate (kept 1.3%
2-chunk vs rerun 59.2%) was misleading: kept set was selection-biased
toward genuine 1-sense cases.

### Updated numbers (2026-06-18 final)

- skip_fallback: 117 (was 117, no change)
- unverified_rule_a: 1,470 (was 1,588 - 117 self-ref - 2 fixed = 1,470)
- not_yet_run: 0
- pass: 941 (was 939 + 2 fixed)

### Tracker

`data/simplify_diff/known_gaps.json` updated with:
- Actual 2% measured rate (replacing 6-10% estimate)
- 2 specific fixes documented
- Apply script bug documented
- Next session P1: 134 self-ref regen (30-40 min)