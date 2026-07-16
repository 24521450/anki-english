# ADR 0005 — Gloss pipeline refactor: `|` encoding, validation gate, M3 re-run

**Applied:** 2026-06-18

> **Superseded for final Definition/Example ownership by ADR 0011 on
> 2026-07-15.** The implementation history and non-semantic source/metadata
> mechanics below remain relevant during decoupling, but production semantic
> content now comes from the promoted Semantic Registry.

> **Historical implementation note (2026-07-12):** this ADR intentionally
> preserves the names of one-shot phase commands that existed when the decision
> was applied. Those executables were retired from `HEAD` after their accepted
> outputs became canonical curated/review data. Recover them from Git history
> only when auditing the original migration.

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

> **HISTORICAL NOTE (2026-06-22, P5D):** the `word count 1-6 total + per-chunk`
> row above was **removed** from `validate_verdict` on 2026-06-22. The
> current gate enforces only structure + headword-leak. See the P5D
> addendum below for the rationale and migration. Keep this row in
> the historical ADR for context, but it does NOT describe current
> gate behavior.

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

---

## Addendum 2026-06-21 (P4B) — Rule-Shape Consistency + Policy-Aware Coverage Audit

### Why "multi `def_before` segments → one gloss" is NOT a defect

Three mechanics in the gloss pipeline legitimately collapse many source
senses into a single gloss word:

1. **Gloss Rule A** — near-synonym senses collapse to one word
   (`ridiculous; nonsensical → ridiculous`).
2. **Gloss Rule B** — same-domain sense variants collapse to one word
   (`plan; organize → plan; organize` collapses if M3 judges them variants).
3. **Gloss Rule C** (safety net) — a domain-restricted sense is kept when
   dropping it would leave the card empty.

So a naive "1-chunk gloss with N-segment `def_before`" detector is
**overinclusive** — it flags both legitimate collapses and true
under-collapses. A 2026-06-19 audit using this naive detector reported
102 "high-risk" rows; the actual rule-shape contradictions were only 24
(of which 26 were P4A's distinct-sense targets, and 24 are P4B's
rule-shape contradictions).

### P4B policy — Rule-Shape Consistency

We add a new term (also in `CONTEXT.md § Rule-Shape Consistency`):

> A `Gloss Verdict` must have a separator/chunk shape consistent with
> its `rule_applied`. The rule encodes the structural promise; the gloss
> must honor it.

| Rule | Required shape |
|---|---|
| `rule_b_pick1`, `concrete_1sense`, `multi_pos_pick1` | one chunk OK |
| `2sense_distinct`, `3sense_distinct`, `rule_b_pick2`, `rule_b_pick2_addendum`, `multi_pos_pick2` | **must have >1 chunk** |
| `2sense_samedomain` | one chunk OK if Rule A applies, else `;` or `|` |
| `pos_aware_gloss` | policy review (one chunk may be intentional) |

### Tools and buckets

P4B ships three read-only / write tools:

- `tools/_apply_p4b_rule_shape_fix.py` — guarded apply for 24
  rule-shape contradictions (P4B scope). Mirrors the P4A apply tool:
  dry-run default, `--apply` writes, aborts on guard mismatch, backups
  audit + TXT before write, regenerates JSONL via `build_notes`.
- `tools/_verify_p4b_rule_shape_fix.py` — asserts the 24 rows are now
  multi-chunk across audit/TXT/JSONL, all 24 pass `validate_verdict`,
  P3B and P4A verifiers still PASS.
- `tools/_audit_gloss_policy_coverage.py` — read-only classification:
  every audit row goes into exactly one of:
  - `allowed_single_gloss` — rule permits one chunk
  - `rule_shape_contradiction` — rule says pick2/distinct but one chunk
  - `policy_review` — `pos_aware_gloss` or `2sense_samedomain` collapsed
    to one chunk (Rule A may justify, M3 + human review required)
  - `metadata_error` — separator / count / validator mismatch
  - `other` — already multi-chunk per rule, no action needed

### Numbers before / after P4B

| Bucket | Before P4B | After P4B |
|---|---:|---:|
| `rule_shape_contradiction` | 24 | 0 |
| `policy_review` (pos_aware_gloss + 2sense_samedomain one-chunk) | 64 | 64 (unchanged) |
| `metadata_error` | 0 | 0 |
| Naive multi-def one-gloss (informational only) | 398 | 374 |

P4B does **not** touch `pos_aware_gloss` or `2sense_samedomain` rows —
those require semantic M3 + human review, not mechanical expansion.

### Why no new ADR

This is a clarification of the existing gloss-pipeline decision (gate
semantics + Rule A/B/C authority), not a new architectural decision. The
Rule-Shape Consistency term is added to CONTEXT.md as a glossary entry,
and this addendum documents the policy-aware audit reasoning.

---

## Addendum 2026-06-21 (P4C) — Policy Review Ledger + Targeted Semantic Fix

### Why a separate review ledger (not edits to the audit master)

The 64 rows that fall into `policy_review` after P4B are *not* automatic
fixes — Rule A (near-synonyms) and Rule C (safety net) genuinely permit
many of them to stay one-chunk. Forcing them all into multi-chunk would
either widen glosses past their actual learner-meaning coverage or
duplicate Rule A's synonym collapses under a different name.

The decision per row is *semantic* (does this single-gloss cover the
IELTS-relevant meaning?) and can't be made by a mechanical rule. It
needs a human or M3 review.

**Decision:** keep review state out of `data/audit_full_deck_v2.jsonl`.
The audit master is the source of truth for production card data —
review metadata doesn't belong there. The Policy Review Ledger
(`data/gloss_policy_review_p4c.jsonl` for the P4C pass) is a separate
JSONL file with one record per reviewed row.

### Ledger schema

```json
{
  "word": "curious", "pos": "adjective", "cefr": "B2",
  "rule_applied": "2sense_samedomain",
  "def_before": "having a strong desire to know about something|strange and unusual",
  "old_gloss": "inquisitive",
  "decision": "keep_single" | "repair_gloss",
  "new_gloss": "inquisitive|strange",   // required iff decision=repair_gloss
  "separator": "|",                      // derived
  "gloss_word_count": 2,
  "reason": "sense 2 'strange' dropped by old gloss",
  "p4c_version": "2026-06-21"
}
```

### Triage outcome (P4C)

64 policy_review rows triaged. Result:
- 7 `repair_gloss` — clear semantic loss the current gloss doesn't cover.
- 57 `keep_single` — current single-gloss reviewed as covering the
  IELTS-relevant meaning (Rule A/C legitimize the collapse, or the
  dominant sense subsumes the others).

The P4C pass explicitly does **not** widen the remaining 57 rows
mechanically. A future P4D or M3 regen pass can revisit them if
auditing shows specific learner confusion.

### New audit buckets

`tools/_audit_gloss_policy_coverage.py` reads the ledger and reports:
- `policy_review_open` — policy_review rows with no ledger row (untriaged). **Hard fail.**
- `policy_review_reviewed_keep` — ledger has `keep_single`. Informational.
- `policy_review_repaired` — ledger has `repair_gloss` and audit reflects it. Informational.
- `allowed_single_gloss` / `rule_shape_contradiction` / `metadata_error` / `other` — unchanged from P4B.

Exit 1 conditions: `rule_shape_contradiction > 0`, `metadata_error > 0`,
or **`policy_review_open > 0`** (the new hard fail).

### Why no new ADR

This is a process change (separate ledger) and a terminology addition
(Policy Review Ledger). The P4B policy-aware audit reasoning is
extended, not replaced. The ledger separation is the right separation
of concerns (production data vs review state) but doesn't change the
gloss-pipeline architecture.

---

## Addendum 2026-06-21 (P5) — Precision Phrase: when a single-word synonym is wrong

### The problem P5 closes

The gloss pipeline permits single-word glosses via Rule A (collapse
near-synonyms) and the `concrete_1sense` / `multi_pos_pick1` /
`rule_b_pick1` rules. This works when the one-word gloss is a true
synonym. It **breaks** when the one-word gloss is a *near-synonym*
that shifts into a different semantic neighborhood.

Two seed examples from P5:

**`mediate → arbitrate`** (verb, C2)
- Def: "to try to end a situation between two or more people or groups
  who disagree by talking to them and trying to find things that
  everyone can agree on | to succeed in finding a solution to a
  problem between people or groups who disagree"
- Old gloss: `arbitrate` (one word, "concrete_1sense" rule, gate=pass)
- Risk: `mediate` and `arbitrate` are a **contrast pair**. A mediator
  helps parties reach agreement; an arbitrator *decides* the dispute.
  Using `arbitrate` as the gloss for `mediate` is a definition error —
  learners who memorize "mediate = arbitrate" will use them
  interchangeably, which is wrong.
- New gloss: `help resolve a dispute` (4 words, phrase form).
- Risk type: `contrast_pair`.

**`solo (noun) → recital`** (C1)
- Def: "a musical composition, or a passage, for a single voice or
  instrument; a performance by one person alone"
- Old gloss: `recital` (one word, "POS_DEF_MISMATCH_fixed" rule)
- Risk: `recital` narrows the sense to a *performance event*. The
  Oxford def covers composition, passage, OR performance by one
  person. A composition or passage is not a recital.
- New gloss: `single-performer music` (2 words, phrase form).
- Risk type: `type_narrowing`.

Both rows passed the gate because `validate_verdict` only checks
shape (separator/count/word-count/headword-leak), not semantic
correctness. The audit policy tool classifies them as
`allowed_single_gloss` — also correct under the existing rules.
P5 closes this gap by adding a `precision_phrase` rule code and a
review ledger.

### The new `precision_phrase` rule

`precision_phrase` joins the `VALID_RULE_CODES` tuple as a
first-class rule. It denotes a single-chunk gloss that uses a concise
phrase (not length-capped — see P5D addendum 2026-06-22 below)
because the single-word synonym would shift into a
nearby contrast word or narrow the headword's semantic type.

`tools/_audit_gloss_policy_coverage.py` adds `precision_phrase` to
`SINGLE_ALLOWED` — one-chunk is the structural expectation, no
separator, no contradiction.

### The Precision Phrase Ledger

`data/gloss_precision_phrase_p5.jsonl` is a separate JSONL file
following the P4C Policy Review Ledger convention. Each row records
either:

- `repair_gloss` — clear semantic loss with a concise phrase (length
  not capped post-P5D 2026-06-22) that captures the headword precisely.
  Updates audit row's `gloss_after`, `rule_applied` (set to
  `precision_phrase`), `separator`, and `gloss_word_count`; updates TXT
  def cell; triggers `build_notes` JSONL regen. Risk-type tag explains
  why the one-word synonym failed (`contrast_pair`, `type_narrowing`,
  `overgeneralized_synonym`, `domain_loss`, `multi_pos_loss`).
- `review_candidate` — heuristic candidate flagged for future human
  review (no audit change). Keeps the candidate visible across scans.
- `keep_current` — single-word gloss reviewed and confirmed as
  adequate (Rule A synonym collapse legit, no precision loss). No
  audit change. Recorded so re-scans don't keep flagging it.

The audit master (`data/audit_full_deck_v2.jsonl`) stays as the
production source of truth. Review decisions live in the ledger; the
audit row gains nothing except the post-repair `rule_applied=precision_phrase`
and `fix_status=p5_precision_phrase_repaired` metadata.

### P5 scope discipline

A naive audit scan flags ~989 single-word glosses at advanced CEFR
(B2/C1/C2/UNCLASSIFIED) as "potential precision-phrase candidates."
P5 deliberately does **not** auto-fix them. Single-word synonyms are
legit when:

- The def_before is one concrete sense with no type-narrowing risk
  (most `concrete_1sense` rows).
- The single word is a true synonym (Rule A collapse is correct).
- The headword is C1+ academic vocabulary where learners benefit from
  the compact single-word form.

P5's first deliverable is a ledger with the **2 confirmed seed
repairs** plus a `review_candidate` list of heuristic discoveries
populated from the full-audit scan. Future passes (P5b, P5c, ...)
triage the review-candidate list one decision at a time. Aggressive
auto-fix is rejected because Rule A collapse is legitimate for most
single-word glosses — the precision-phrase case is the exception,
not the rule.

### Why no new ADR

`precision_phrase` extends the existing rule-code vocabulary
(`VALID_RULE_CODES`) rather than replacing the gloss-pipeline
architecture. The Precision Phrase Ledger mirrors the P4C Policy
Review Ledger pattern (separate JSONL, separate apply/verify tools).
The phrase form was supported by the gate (word count range covered
1-6 at P5 time; P5D 2026-06-22 removed the range entirely — see
addendum below). The only architectural change at P5 time was
adding the rule code and a new ledger — a process addition, not a
structural change.
---

## Addendum 2026-06-22 (P5D) — Remove gloss word-count limits from validator

### Why the limits came off

The validation gate (`validate_verdict` in `src/deck_builder/gloss_llm.py`)
originally enforced 4 rules, including a **word-count range**: total 1-6
content words, plus per-chunk limits (≤6 for `none`, ≤4 for `|`, ≤3 for `;`).
The intent was to keep glosses learner-friendly.

After the P5 manual review pass, this limit became the loudest blocker:
the user's filled v2 file (`manual_gloss_review_p5_candidates_filled_QA_patched_v2 (1).jsonl`)
contained 8 repairs whose glosses exceeded the 6-word total — not because
the glosses were bad, but because capturing the headword's full multi-sense
content at C1/C2 academic level required more than 6 words.

Concrete examples that the v1 validator rejected but the v2 manual pass
trusted:

| (word, pos, CEFR) | v2 gloss (now accepted) | Words |
|---|---|---:|
| `identification\|noun\|C1` | `proving who or what\|recognizing importance\|ID document\|strong sympathy\|close linking` | 12 |
| `rental\|noun\|C1` | `use fee\|hiring deal\|thing for hire` | 7 |
| `whip\|verb\|C1` | `hit with cord\|move suddenly\|pull suddenly\|mix fast` | 9 |
| `pop\|verb\|C1` | `short sound\|burst\|go quickly\|put quickly\|appear suddenly` | 9 |
| `compromise\|noun, verb\|C1` | `agreement by concession\|lower standards\|put at risk` | 8 |
| `burst\|verb\|C1` | `break open\|move suddenly\|be very full` | 7 |
| `outrage\|noun, verb\|C1` | `shock and anger\|wrong act\|anger greatly` | 7 |
| `overwhelm\|verb\|C1` | `affect too strongly\|defeat completely\|give too much` | 8 |

In each case, the v1 manual pass had to **artificially shorten** the gloss
into a sub-6-word version, even when the full version was more accurate.
That shortening (e.g. `proving who or what|recognizing importance|ID document|strong sympathy|close linking`
→ `proving who or what|recognizing importance|ID document`) was a forced
loss of semantic coverage for the sake of an arbitrary length cap.

### Decision

**Remove the word-count limit from the validator.** Trust the human/M3
verdict on length. The validator keeps the **2 rules** that are
machine-detectable without semantic judgment:

1. **separator/count/content consistency** (incl. empty-chunk detection) —
   catches typos like `declared '|' but actual ';'` and structural bugs
   like `x |` or `x ; ; y`.
2. **headword in any chunk** — catches self-referential glosses (`gloss ==
   headword`), multi-chunk leaks (`x ; accelerate`), and morphological
   variants (`configuration` as gloss for `configure`).

Removed:
- Total content words 1-6 (the `word_count_out_of_range` category).
- Per-chunk word limits (`pick1` ≤6, `|` ≤4, `;` ≤3) — the
  `chunk_word_count[i]` category.

`gloss_word_count` field is **preserved** in audit + ledger rows as
metadata/reporting (helps audit spot outliers), but no longer blocks apply.

### Trade-offs

| Alternative | Why not chosen |
|---|---|
| Keep total cap, raise to 12 words | Same forced-shortening problem at higher CEFR; arbitrary cap remains. |
| Keep cap, add an explicit "academic override" rule | Adds a rule-code path that M3 would have to honor; same trust-the-human problem. |
| Cap stays at 6, but loosen to "soft warn" | Defense-in-depth gate would still skip at apply time (`tools/_apply_glosses_to_txt.py`), so same blocker. |
| Validate semantic correctness (Rule A) | Out of scope — needs synonym DB. M3 + human review handle that (see P4C Policy Review Ledger). |

### Files changed

- `src/deck_builder/gloss_llm.py` — `validate_verdict` now checks only
  structure + headword-leak. Empty-gloss check added (decision='gloss' +
  empty gloss → `empty_gloss` violation).
- `tests/deck_builder/test_validate_verdict.py` — old `TestWordCount`
  class replaced with `TestWordCountLimitsRemoved`; new tests assert that
  the 8 P5D seed fixes (and the seed `additionally -> also`) all pass.
  `TestSeparatorCountConsistency` gained `test_empty_chunk_after_pipe_fails`
  and `test_empty_chunk_between_semicolons_fails` to lock in the empty-chunk
  check (an old gate bug that was masked by the word-count limit; empty
  chunks were silently dropped by `if c.strip()` filter before count).
- `CONTEXT.md` — `Gloss`, `Gloss Validation Gate`, `Precision Phrase` entries
  updated to drop the 1-6 / 2-6 claims and link to this addendum.
- `tools/_verify_p5d_manual_review.py` (new) — verifies the v2 canonical
  decisions file has 988 rows / 344 repair / 644 keep, all repairs pass
  the new validator (zero `word_count_out_of_range` expected), no duplicates.
- `tools/_apply_p5d_manual_review.py` (new) — applies the v2 decisions,
  delta vs current P5B state: previously-kept v1 decisions whose v2
  verdict flips to `repair_gloss` get a fresh repair; previously-repaired
  v1 decisions whose v2 verdict flips to `keep_current` revert. Audit +
  TXT + P5 ledger all updated; JSONL rebuilt via `tools/build_notes.py`.

### Verification

- `pytest`: 547/547 pass (was 515/515 before P5D; +32 new/updated gate tests)
- `python -m tools._verify_p5_precision_phrase`: PASS
- `python -m tools._verify_p5b_manual_review`: PASS
- `python -m tools._verify_p5d_manual_review`: PASS (new)
- `python -m tools._verify_p4c_policy_review`: PASS
- `python -m tools._verify_p4b_rule_shape_fix`: PASS
- `python -m tools._verify_p4a_coverage_fix`: PASS
- `python -m tools._verify_deck_output_p3b`: PASS
- `python -m tools._check_gloss_hygiene --report --quiet`: PASS
- `python -m tools.build_notes --dry-run`: PASS

### Why no new ADR

This is a tightening of an existing validator (removing one rule class),
not a new architectural decision. The gate's role (defense-in-depth
mechanical check) is unchanged — it just trusts the producer more on length.
The v2 manual pass demonstrates the producer (human review) makes
reasonable length choices; if a future pass shows systematic over-length
glosses that hurt learners, the limit could be re-added with a higher
threshold or made into a soft-warn.

---

## Addendum 2026-06-22 (P6) — `multi_sense_distinct` rule + retire "NEVER pick 3" for distinct multisense

### The problem P6 closes

The legacy Rule B (`rule_b_pick2` / `rule_b_pick2_addendum` / `3sense_distinct`)
hard-capped multi-sense distinct glosses at 2 chunks:

> "If the def has 3+ senses: pick 2 glosses (`|`) ... **NEVER pick 3.**"

This cap was a heuristic for senses that are *variants or sub-nuances*
of the same core concept (where collapsing is correct) — but it
applied equally to senses that are *distinct* (where collapsing would
silently drop learner-meaning coverage).

Three concrete examples that the cap mis-handled:

- **`transcribe|verb|UNCLASSIFIED`** — Oxford sense 1 = "write down",
  sense 2 = "write in a different writing system" (e.g. phonetic
  notation), sense 3 = "rewrite (music) for a different instrument".
  These are 3 distinct acts in different domains (general writing /
  transliteration / music). Cap-2 forced the gloss to `write down`
  only — losing the transliteration and music senses entirely.

- **`grid|noun|C1`** — sense 1 = "pattern of squares" (general),
  sense 2 = "map with square references" (geography), sense 3 =
  "network for distributing electricity" (energy). 3 distinct domains.
  Cap-2 lost either energy OR geography.

- **`betray|verb|C1`** — sense 1 = "give to enemy", sense 2 =
  "break trust", sense 3 = "abandon principles", sense 4 =
  "reveal unintentionally". 4 distinct senses. Cap-2 lost either
  "abandon" or "reveal".

In each case the user-filled v2 patch (P6 input) keeps ALL distinct
senses with `|`, restoring full semantic coverage.

### Decision

**Retire the "NEVER pick 3" cap for distinct multisense cases.** Keep
it for *variant / sub-nuance* cases (where Rule A collapse is correct).

New rule code `multi_sense_distinct`:
- First-class `VALID_RULE_CODES` entry.
- Requires `count >= 2` chunks with `|` separator (no upper cap).
- Supersedes legacy `3sense_distinct` and `4sense_distinct` codes (both
  kept in `VALID_RULE_CODES` for backward compat with historical rows).
- P6 import normalizes new P6 rows to `multi_sense_distinct`. Legacy
  rows keep their existing codes until a future pass migrates them.

### P6 scope

- Input: `C:\Users\admin\Downloads\audit_full_deck_v2_multisense_patched.jsonl`
  (the full audit master with 117 P6-gloss diffs vs current state).
- Output: `data/multisense_harddrop_p6_decisions.jsonl` (117 canonical
  decisions), then guarded apply to audit (117 rows updated) + TXT
  (114 cells updated; 3 deferred keys with no TXT row exist).

3 deferred keys (audit-only):
- `harbor|verb|UNCLASSIFIED`
- `invading|verb|UNCLASSIFIED`
- `shortsighted|adjective|UNCLASSIFIED`

### QA normalizations (8 rows)

The user's patch contained 8 rows whose raw `gloss_after` would fail
`validate_verdict` with `headword_in_definition` (headword token
appears in a chunk as a sub-word). Each was hand-fixed during P6 import
to remove the headword token while preserving semantic content:

| key | raw (fails) | canonical (passes) |
|---|---|---|
| `arrow\|noun\|B2` | `arrow shot from bow\|direction mark` | `bow projectile\|direction mark` |
| `compound\|noun\|B2` | `combined thing\|chemical substance\|compound word` | `combined thing\|chemical substance\|word combination` |
| `democratic\|adjective\|B2` | `people-ruled\|member-equal\|socially equal\|Democratic Party` | `people-ruled\|member-equal\|socially equal\|US party-related` |
| `lens\|noun\|B2` | `curved seeing glass\|camera glass\|contact lens` | `curved seeing glass\|camera glass\|contact eyewear` |
| `patrol\|noun, verb\|C1` | `checking round\|patrol group\|go round checking` | `checking round\|security group\|go round checking` |
| `squad\|noun\|C1` | `police unit\|sports squad\|soldier group` | `police unit\|sports team\|soldier group` |
| `tap\|noun, verb\|B2` | `water valve\|light touch\|touch lightly\|tap rhythm` | `water valve\|light touch\|touch lightly\|rhythmic beat` |
| `top\|verb\|C1` | `exceed\|rank first\|put on top` | `exceed\|rank first\|place above` |

### Files changed

- `src/deck_builder/gloss_llm.py` — `VALID_RULE_CODES` extended with
  `multi_sense_distinct` (and legacy `3sense_distinct` retained).
- `tools/_audit_gloss_policy_coverage.py` — `PICK_RULES` set includes
  `multi_sense_distinct` (PICK_RULES = rules requiring multi-chunk gloss).
- `tools/_full_audit.py` — `KNOWN_RULES` updated to include
  `multi_sense_distinct` and the P5 additions.
- `tools/_import_p6_multisense.py` (new) — guarded import: identifies
  the 117 diffs, applies 8 headword-leak normalizations, recomputes
  separator/word_count, sets `fix_status=p6_multisense_harddrop_repaired`.
- `tools/_apply_p6_multisense.py` (new) — guarded apply by 5-element
  key; aborts on guard mismatch; checks deferred keys against known
  set; updates 117 audit + 114 TXT.
- `tools/_verify_p6_multisense_harddrop.py` (new) — invariant checker.

### Why no new ADR (this is an addendum)

`multi_sense_distinct` extends the existing rule-code vocabulary
(`VALID_RULE_CODES`) and rule-shape classification (`PICK_RULES`) rather
than replacing the gloss-pipeline architecture. The P6 patch is a
targeted user-driven repair (117 keys), not a structural change.

The Rule B "NEVER pick 3" cap was always a heuristic — this addendum
clarifies that it applies only to *variant* senses (where collapsing
is correct), not to *distinct* senses (where collapsing would mislead).
No validator behavior changes; only the rule-code vocabulary and the
shape policy expand.

---

## Addendum 2026-06-22 (P7) — Redundant/Minor Sense Trim + `common_core_trimmed` / `trimmed_multisense` rule codes

### The problem P7 closes

After P6 widened `multi_sense_distinct` to keep all distinct senses
(including 3+ chunks), some rows had **redundant subsenses** that the
v3 patch correctly identified as collapsible:

- **`information`** — Oxford lists both "facts/news" and "data" as
  subsenses under one headword. Oxford's `|` separator put them on
  different chunks, but the learner-meaning is "facts or data" — one
  chunk covers both.

- **`judgment`** — process ("the act of judging") vs result ("the
  opinion formed"). Both are learner-relevant under the same
  learner-meaning "an opinion or decision". One chunk.

- **`attack`** — noun ("offensive act") vs verb ("to assault"). Same
  learner-meaning "to assault / an assault". One chunk.

- **`puppy`** — "young dog" — single learner-meaning, no real
  distinction.

These are NOT distinct-multisense cases (P6) — they are **subsenses
that share the same learner-meaning**. Forcing them into separate
chunks would overstate learner-meaning coverage.

The v3 patch also contained **metadata-only drift** (98+ rows where
`rule_applied` flipped back from `multi_sense_distinct` to legacy
labels like `3sense_distinct` / `4sense_distinct` / `2sense_distinct`
without any gloss change). P7 ignores these — they would silently undo
the P6 widening policy.

### Decision

**Two new rule codes** to cover the redundant-sense case:

- **`common_core_trimmed`** — single-chunk collapse of redundant
  subsenses. Triggered by: countable/uncountable, process/result,
  noun/verb, subtype/core variants. `separator = none` (single
  chunk).

- **`trimmed_multisense`** — multi-chunk (2+ with `|`) after redundant
  senses trimmed. Used when distinct senses remain but some subsenses
  were dropped. `separator = |` typically.

**Normalize rules**: the v3 patch carried raw labels like
`3sense_distinct`, `4sense_distinct`, `5sense_distinct`, and even
`common_core_trimmed` raw. P7 ignores v3's `rule_applied` and
**recomputes** the canonical rule from the new `separator`:

- `separator = none` → `common_core_trimmed`
- `separator = |` or `;` → `trimmed_multisense`

This is the inverse of P6 (which used `rule_after = multi_sense_distinct`
unconditionally). The separator is the authoritative signal; the rule
is derived.

**Do NOT import v3 rule backdrift**: 98+ rows where v3 had a different
`rule_applied` but the SAME `gloss_after` are explicitly skipped.
The P6 `multi_sense_distinct` rule stays in place on those rows; v3's
revert to `3sense_distinct` is metadata noise that would silently
narrow the P6 policy.

### Worked examples

- **`information|noun|UNCLASSIFIED`**: 1 chunk → `common_core_trimmed`.
- **`judgment|noun|C1`**: 1 chunk → `common_core_trimmed`.
- **`attack|noun|verb|C1`**: 1 chunk → `common_core_trimmed`.
- **`puppy|noun|B2`**: 1 chunk → `common_core_trimmed`.
- **`gut|noun|C1`**: 4 chunks (intestines | stomach organs | courage |
  instinct) → `trimmed_multisense`. Originally v3 had `5sense_distinct`
  with 5 chunks; the v3 patch's own 5th chunk (`belly`) was redundant
  with `intestines`/`stomach organs`, so the canonical form keeps 4.

### P7 scope

- Input: `C:\Users\admin\Downloads\audit_full_deck_v2_multisense_patched_v3 (1).jsonl`
  (full audit master with 59 P7-gloss diffs vs current state).
- Output: `data/redundant_sense_trim_p7_decisions.jsonl` (59 canonical
  decisions), then guarded apply to audit (59 rows updated) + TXT
  (59 cells updated; 0 deferred).

### Known metadata mismatch in v3

`transportation|noun|B2`: v3 says `gloss_word_count = 3` but actual is
2 (for `moving people/goods`). P7 recomputes from the canonical gloss,
ignoring v3's metadata mismatch.

### Files changed

- `src/deck_builder/gloss_llm.py` — `VALID_RULE_CODES` extended with
  `common_core_trimmed` and `trimmed_multisense`.
- `tools/_audit_gloss_policy_coverage.py` — `PICK_RULES` includes
  `trimmed_multisense`; `SINGLE_ALLOWED` includes `common_core_trimmed`.
- `tools/_full_audit.py` — `KNOWN_RULES` includes both new codes.
- `tools/_import_p7_decisions.py` (new) — guarded import: filters
  gloss-only diffs (skips 2428 metadata-only), recomputes separator
  + rule, recomputes word_count, sets
  `fix_status = p7_redundant_sense_trimmed`.
- `tools/_apply_p7_redundant_sense_trim.py` (new) — guarded apply by
  5-element key; aborts on guard mismatch.
- `tools/_verify_p7_redundant_sense_trim.py` (new) — invariant checker.

### Why no new ADR (this is an addendum)

`common_core_trimmed` and `trimmed_multisense` extend the existing
rule-code vocabulary rather than replacing the gloss-pipeline
architecture. The trim logic is human-driven (P7 applies a user-
patched v3 file's decisions, not an automatic classifier), so this
is a process addition (new rule codes + apply tool), not a structural
change.

## Addendum 2026-06-23 (P8) - Convention Taxonomy + Miserable Hotfix

### Why split precision_phrase and multi_sense_distinct

P5 introduced precision_phrase (one-chunk phrase form to avoid contrast
loss), and P6 introduced multi_sense_distinct (catch-all for 2+ distinct
senses with |). After 7 passes, both rules covered too much ground
for QA to pattern-match without re-reading the gloss:

- precision_phrase was applied to genuinely different scenarios:
  one-word glosses that the M3 rejected for **type narrowing**
  (parameter → condition or limit), for **contrast pair avoidance**
  (mediate → help resolve a dispute), and for **single-chunk phrases
  of any length**. Three different intents under one rule code.
- multi_sense_distinct was applied to 2-sense, 3-sense, 4-sense, and
  5-sense rows. The actual sense count matters for downstream QA
  (e.g. flashcard layout decisions on sense count).

P8 splits these into sharper, learner-meaning-driven codes.

### The new taxonomy (single chunk)

- **word_gloss** - one-word gloss, single chunk. Crisp capture.
- **phrase_gloss** - short phrase, single chunk. The P5
  precision_phrase successor for most non-facet cases.
- **facet_phrase** - single-chunk or-joined facet. Both sides are
  same-sense wordings, not distinct domains. separator = none.

### The new taxonomy (multi chunk)

- **2sense_distinct / 3sense_distinct / 4sense_distinct /
  5sense_distinct** - pipe-separated distinct senses, named by the
  actual chunk count. Replaces the catch-all multi_sense_distinct
  with concrete counts. P6 rows migrate post-P8.
- **2sense_distinct_with_facet / 3sense_distinct_with_facet** -
  pipe-separated distinct senses where **one** sense is itself a
  same-sense facet phrase joined by or. **Always
  review_needed: true** because internal or in a multi-sense
  gloss is QA-sensitive.

### Why internal or can be valid as a same-sense facet

In consent|noun, verb|C1, the first Oxford sense is
permission to do something, especially given by somebody in authority
and the second is agreement about something. These are two wordings
for the **same core concept** (the noun sense is "permission/agreement"
in one go). Rendering as permission or agreement|give permission
preserves the facet while keeping the multi-sense top-level separator
clear. Without the _with_facet rule, the only options would be:

1. **Drop the facet** - lose the permission/agreement nuance, gloss
   becomes just permission|give permission which under-specifies
   the noun.
2. **Promote to 3-sense** - render as permission|agreement|give
   permission, but permission and agreement aren't really
   distinct senses; they're two phrasings of the same one. The 3-sense
   gloss misleads the learner into thinking there are 3 distinct
   concepts.

The _with_facet rule is the right middle path. It carries
review_needed: true because the heuristic detector (separating
same-sense facets from distinct senses) is not 100% reliable; human
QA confirms the facet claim.

### Why miserable is NOT a facet case

miserable|adjective|B2 Oxford has TWO numbered B2 senses:
"very unhappy or uncomfortable" and "making you feel very unhappy or
uncomfortable". These are **distinct** (one is the FEELING, one is the
CAUSE) - not same-sense facets. The cause-sense uses
"making you feel" which is structurally different from the
feeling-sense. So:

- Top-level separator MUST be | (distinct senses).
- rule_applied MUST be 2sense_distinct, NOT 2sense_distinct_with_facet.
- The internal or in the original defs ("unhappy or uncomfortable")
  is Oxford's source convention, not a same-sense facet marker.

The P8 hotfix:
- def_before becomes
  very unhappy or uncomfortable|making you feel very unhappy or
  uncomfortable (pipe, not ; - Oxford HTML's ; is the
  list-of-senses separator at HTML level, not the def_before
  convention).
- gloss_after becomes very unhappy|very unpleasant (was
  very unhappy|very bad or inadequate, which carried a hidden
  nested or inside a pipe-separated gloss - that's a P8 anti-pattern).

### Migration impact

- **457 audit rows migrated** out of 2487.
- **102 P6 rows** (multi_sense_distinct) migrated to specific
  Nsense_distinct / _with_facet codes.
- **326 P5 rows** (precision_phrase) migrated to
  word_gloss / phrase_gloss / facet_phrase / Nsense_distinct.
- **0 deprecated rules remain in audit** post-apply.
- **3 _with_facet rows** carry review_needed: true:
  casualty, consent, portray.

### Backward compat

- precision_phrase and multi_sense_distinct REMAIN in
  VALID_RULE_CODES for backward compat with historical rows
  (some P5/P6 decisions files still reference them).
- _audit_gloss_policy_coverage PICK_RULES / SINGLE_ALLOWED keep
  the old codes in their sets but the audit has 0 of them post-apply.
- KNOWN_RULES in _full_audit.py extended with the 7 new codes.

### Why no new ADR (this is an addendum)

The P8 pass is a vocabulary refinement + 1 hotfix, not a structural
change to the gloss pipeline architecture. The split into
word_gloss/phrase_gloss/facet_phrase is a rename-and-clarify; the
Nsense_distinct codes are a count-tag specialization; the _with_facet
codes are a structural annotation. No validator changes, no card-layout
changes, no schema changes. Process addition (new codes + apply tool)
rather than architecture change.
