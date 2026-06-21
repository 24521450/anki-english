# IELTS Academic Vocabulary Deck

IELTS / Academic English Anki deck builder, notes DB, and scraper pipeline.

## Context

This file is a **glossary** for the project — the canonical vocabulary for
talking about the system. Use these terms in code, commits, and docs to avoid
drift. When a new concept emerges, add it here.

**This file is not a spec, a design doc, or a workflow guide.** It does not
contain implementation details, command examples, or stage descriptions. For
those, see:

- `AGENTS.md` — project conventions, commands, layout
- `design/README.md` — visual design system, card rules
- `CONTEXT-FORMAT.md` (if present) — format spec for new entries

## Language

### Note types

**EAVM Note Type**:
The Anki note type for the English Academic Vocabulary Model, generated from EAVM styling and templates.
_Avoid_: Card type, template model

### Inline labels (in the definition text)

**Register Tag**:
A `.register-tag` chip prepended inline to a definition to show register, subject, or domain. Has 4 color variants: `rt-amber` (attitude), `rt-warm` (slang/specialist), `rt-red` (offensive/taboo), `rt-subject` (academic subject). Rendered by `back_template.txt` JS from the `[register, subject]` bracket at the start of each sense.
_Avoid_: Register chip, inline label, marker

**Subject Label**:
A specific type of Register Tag (`.rt-subject`) that names the academic domain of a sense (biology, law, medicine, etc.). 23 subject labels total — see `data/oxford_labels.json` and `design/index.html` vùng 5.
_Avoid_: Topic chip, domain tag

### Word-level labels (in the meta-row)

**Usage Tag**:
A `.usage-tag` chip placed in the meta-row next to the IPA pill. Marks word-level usage restrictions: `old-fashioned`, `old use`, `dialect`, `saying`, `™ trademark`. Distinct from Register Tag (sense-level) — applies to the whole word, not a single sense.
_Avoid_: Restriction tag, register pill

**IPA Pill**:
A `.ipa-text` element with monospace font + pill background, displaying the phonetic transcription. Uses the `Charis SIL` → `Doulos SIL` → `Segoe UI` → `Lucida Sans Unicode` → `Arial Unicode MS` font cascade.
_Avoid_: Pronunciation, phonetic text

**Audio Button**:
A `.audio-btn-wrapper` chip with a Tabler volume icon, in either UK (`.audio-btn-uk`, blue accent) or US (`.audio-btn-us`, red accent) variant. Disabled state uses `.no-audio` (28% opacity, no pointer events).
_Avoid_: Speaker button, sound icon

### Card-level features (footer row)

**Feature Tag**:
A `.feature-tag` chip in a dedicated `.feature-row` at the bottom of the back card. Currently used for `idioms` and `phrasal verbs`. Distinct from Idiom Box — a Feature Tag is the *trigger chip*; the Idiom Box is where the idioms themselves render.
_Avoid_: Bottom tag, footer chip

### Layout components

**Section Box**:
A `.section-box` container with `bg-section` background, `border-subtle` border, and 14px radius. The generic wrapper for any card section. Variants: `.word-family-box` (purple theme), `.idiom-box` (amber theme), `.senses-box` (no padding, used for the L3 grid).
_Avoid_: Card panel, content box

**Sense Row**:
A `.sense-row` grid row with `55fr 45fr` columns — definition on the left, example on the right. Multiple sense rows are stacked in `.senses-box` with 1px dividers. Each row can carry a `.sense-num` badge (① ② ③) when multi-sense.
_Avoid_: Definition row, sense line

**Idiom Box**:
A `.section-box.idiom-box` with amber/yellow theme. Contains an `.idiom-list` of `.idiom-row` items, each with `.idiom-phrase` (the phrase), `.idiom-explanation` (the meaning), and optional `.idiom-examples` (italic usage examples). Triggers when the raw note has an `Idioms` field.
_Avoid_: Phrase box, idiom section

**Word Family Box**:
A `.section-box.word-family-box` with purple theme. Contains `.word-family-content` flex container of `.wf-chip` elements — each chip is a word + a POS sub-tag (`.wf-pos-n`/`.wf-pos-v`/`.wf-pos-adj`/`.wf-pos-adv`/`.wf-pos-phr`/`.wf-pos-prep`). Triggers when the raw note has a `WordFamily` field.
_Avoid_: Word form box, derivation list

**Collocation List**:
A `.collocations-list` flex container of `.collocation-chip` elements. Plain mono chips without category color — semantic load is the chip's text, not its color. Triggers when `Collocations` field is non-empty.
_Avoid_: Phrase list, example list

**Top Bar**:
The header strip of the card with `.top-bar-left` (POS chips + corpus badges) and `.top-bar-right` (CEFR badge). The two halves are separated by `.top-bar-sep` (1px × 14px vertical divider).
_Avoid_: Header, banner

**POS Chip**:
A `.pos-chip` pill for part of speech. Single POS renders as a plain chip; multi-POS renders with `.pos-chip-num` sub-badge (① ② ③) for ordering.
_Avoid_: POS tag, grammar chip

**CEFR Badge**:
A `.top-badge` with `.cefr-badge-{level}` modifier for the 7 levels (A1, A2, B1, B2, C1, C2, UNCLASSIFIED). Color-coded.
_Avoid_: Level badge, difficulty chip

**Corpus Badge**:
A `.corpus-badge` chip with `.corpus-oxf` (Oxford 3000/5000), `.corpus-opal` (OPAL W/S), or `.corpus-awl` (AWL) variant. Sits in the top-bar-left, after `.top-bar-sep`.
_Avoid_: List badge, frequency chip

**Divider**:
A horizontal `.divider` rule. Per-CEFR variants (`.divider-A1` ... `.divider-UNCLASSIFIED`) use a gradient line tinted to the CEFR color.
_Avoid_: Separator, rule

**Sense Count Dots**:
Five 5px circles (`.sense-count-dot`) rendered below the word on the front card when the note has more than one sense. Number of dots = number of senses. Hidden when single-sense.
_Avoid_: Dot indicator, sense preview

**Word Highlight**:
Inline `.word-highlight` span (bold + underline) wrapping occurrences of the headword in the example text. Tinted with the accent-purple color.
_Avoid_: Bold word, headword mark

### Card content rules

**Card Identity**:
A card is uniquely identified by the triple `(Word, CEFRLevel, LIST)`. **Exactly one card per `(Word, CEFRLevel, LIST)` triple** — no more, no less. `LIST` is the primary corpus/list bucket derived from the card's tags via a fixed priority:

```text
Oxford_5000 > Oxford_3000 > AWL > NO_LIST
```

A card carries the highest-priority tag it owns (e.g. a card tagged both `Oxford_5000` and `AWL` resolves to `Oxford_5000`); cards with none of the three list tags resolve to `NO_LIST`. Identity is enforced at the build stage and re-verified by the P3B verifier.

Implications:
- Same word at the same CEFR on different lists produces multiple cards. Example: `firm|noun|B2` lives on `Oxford_3000` and `firm|adjective|B2` lives on `Oxford_5000` — they are two distinct cards even though they share `(firm, B2)`.
- Same word with different CEFR levels still produces multiple cards (e.g. `tackle` at B2 and `tackle` at C1 are two distinct cards).
- Multi-POS words (e.g. `absent` = adjective/verb/preposition, `yield` = noun/verb) live in a single card per `(CEFR, LIST)`, with all POS chips listed in the top-bar — never one card per POS.
- `NO_LIST` is a valid identity bucket for cards with no corpus list tag (e.g. Oxford proper nouns not on any curated list). The identity rule applies uniformly.
- The legacy `(Word, CEFR)` only rule was retired 2026-06-21 because it incorrectly forced merges across genuine list boundaries (e.g. it would have collapsed `firm|adjective|B2|Oxford_5000` into `firm|noun|B2|Oxford_3000` even though they are distinct vocabulary entries from different curricula).
_Avoid_: Card key, card ID, `(word, CEFR)` only (legacy)

**Sense Sorting**:
All CEFR-matching definitions per **card** (per `(Word, CEFRLevel, LIST)` unit) are retained — there is **no per-card def limit**. (The legacy "Sense Cap" of ≤3 defs/card was removed on 2026-06-21 after audit feedback showed high-frequency words were losing critical senses.) Senses are **logically ordered**: first by Oxford's `sensenum_local` (ascending — Oxford's own frequency proxy, lower number = more common), then by example count (descending) as tie-breaker. Idiom defs (sensenum_local=None) sort last. Scraped records keep all senses; sorting is applied only at build.

**Worked example — `tackle`:**
- Oxford has 5 senses: 1 at B2 ("to make a determined effort to deal with...") and 4 at C1 (verb + noun).
- Build stage produces **2 cards** (not 5, not 6):
  - `(tackle, B2, Oxford_5000)` card: 1 sense (the B2 sense)
  - `(tackle, C1, Oxford_5000)` card: 4 senses, ordered by sensenum_local asc — all 4 C1 senses are kept, none dropped
- **Worked example — `firm` (list-aware split)**: the word has 2 distinct cards on different lists at the same CEFR — `(firm, B2, Oxford_5000)` for the adjective sense ("solid|unlikely to change") and `(firm, B2, Oxford_3000)` for the noun sense ("a business or company"). Same `(firm, B2)` is now allowed because the LIST differs.
- **Worked example — `yield` (multi-POS merge)**: a single card `(yield, C1, Oxford_5000)` carries both noun ("output | produce") and verb ("surrender") senses in one row with all POS chips listed in the top-bar — never one card per POS.
- Anti-pattern: 1 card per sense, 1 card per (sense, POS), or N>1 cards for the same `(word, CEFR, LIST)` — all violate Card Identity. Sense Sorting does not paginate.
_Avoid_: Sense Cap (legacy name), Definition limit, max senses, "pagination" (the term itself suggests splitting into multiple cards, which is wrong here)

**CEFR Sense-Level Assignment Rule**:
Per-sense CEFR resolution when the build stage groups senses into cards. Each sense gets an `assigned_cefr` value plus a `cefr_source` label that tells how the value was derived. The labels are critical for audit and human review — they distinguish an Oxford-assigned level from an inferred one.

- **Inputs** (per record): `headword_cefr` (from Oxford 3000/5000, may be `null`); `senses[]` (each with `sense_cefr`, may be `null`).
- **Outputs** (per sense): `assigned_cefr` and `cefr_source`.

**Rule 1 — Sense has its own badge**: if `sense_cefr` is not `null`, use it; `cefr_source = "sense_badge"`.

**Rule 2 — Sense without badge, single-sense word**: if `sense_cefr` is `null` AND `total_senses == 1` AND `headword_cefr` is not `null`, inherit the headword CEFR; `cefr_source = "inherited_single"`.

**Rule 3 — Sense without badge, multi-sense word, another sense has badge**: if `sense_cefr` is `null` AND `total_senses > 1` AND there exists at least one other sense with non-null `sense_cefr`, drop the sense from any card; `assigned_cefr = null`; `cefr_source = "unlisted"`. Rationale: Oxford did not tag this sense at any level in the corpus, so the learner has no signal to anchor it.

**Rule 4 — All senses without badge, multi-sense word**: if `sense_cefr` is `null` AND `total_senses > 1` AND all senses have `sense_cefr == null` AND `headword_cefr` is not `null`:
- Sense index 0 (primary): inherit the headword CEFR; `cefr_source = "inherited_primary"`. Flag for manual review.
- Sense index > 0: `assigned_cefr = null`; `cefr_source = "unlisted"`.

**Rule 5 — Headword also has no CEFR**: if `headword_cefr` is `null`, `assigned_cefr = null`; `cefr_source = "no_data"`. Word is skipped at build (per Skip Rule).

**Note**: Topics C1/C2 tags must NOT be used to infer sense CEFR — they are subject-matter tags, not proficiency signals. The five `cefr_source` values exist precisely so an auditor can tell `sense_badge` (Oxford authoritative) from `inherited_*` (inferred) from `unlisted` / `no_data` (no signal). A reasonable target: ≥95% of cards in the deck should have `cefr_source = "sense_badge"` or `"inherited_*"`; the rest need manual review.
_Avoid_: Hard-coding `cefr = oxford_badge` for all defs (loses discrimination), using topic CEFR to infer sense CEFR (incorrect semantic)

### Three-tier sense-merging pipeline (β + γ)

After `simplify_record` clusters senses by `(cefr_original, pos)`, the **review-band** (β score 0.30–0.70) needs an LLM-as-judge (γ) to decide whether the clustered senses are semantically substitutable. The pipeline has three tiers — each tier handles a different clarity level:

- **Tier 1 — Heuristic (β confident)**: β ≥ 0.70 → **merge** automatically; β ≤ 0.30 → **split** automatically. No LLM needed. About 8172 clusters fall here; these are unambiguous cases Oxford's own definitions make clear.

- **Tier 2 — LLM-as-judge (γ review-band)**: 0.30 < β < 0.70 → export to a compact JSON file, reason about each cluster as an English lexicographer, write back verdicts. The verdict schema is:
  ```
  {cluster_hash, decision: merge|split|unsure, confidence: 0.0-1.0,
   reasoning: "1 sentence", examples_substitutable_pct: 0-100, merged_text: "..." | null}
  ```
  Decision rule: **merge** if a single definition lets the learner understand ≥80–90% of all examples across the senses; otherwise **split**. The 80-90% rule is the user's stated threshold. **unsure** maps to split (conservative). When merging, `merged_text` provides a cleaner single definition than the auto-concat; when splitting, γ may also flag clusters for manual review via low `confidence` (< 0.85). The agent (MiniMax-M3 itself) acts as γ — no external LLM HTTP call. Verdicts are cached by `cluster_hash` (which hashes word + pos + sorted sense texts) so re-runs are free. About 817 clusters fall in this tier from the 5367-record corpus.

- **Tier 3 — Heuristic (γ uncertain)**: any cluster not covered by a γ verdict falls back to β's verdict (split if β ≤ 0.5, merge if β > 0.5). This is intentionally conservative — a cluster that β put in the review band but γ didn't reach keeps β's caution.

**Why this matters**: the heuristic alone (β) is too strict for English (the 0.5–0.6 band has many senses that are 80% substitutable but not 100%). The LLM alone is too expensive and slow at scale. The 3-tier design uses cheap rules for the easy cases and reserves expensive LLM reasoning for the genuinely ambiguous middle — the same principle as medical triage.

**β-vs-γ correlation from full-run (548 unique verdicts, 2026-06-16)**:
- β ∈ [0.50, 0.60) (n=512): γ merges 39.8% — **β alone in this band is NOT a strong merge signal**
- β ∈ [0.60, 0.70) (n=9): γ merges 44.4% — still not a strong signal
- avg γ confidence 0.90 (all verdicts ≥ 0.8)
- Top risky merges: lowest `examples_substitutable_pct` is 85% (no merge in the dataset is below 80% substitutability)

**Implication for future tuning**: β thresholds of 0.7 (merge) and 0.3 (split) are well-calibrated — the heuristic is right that the 0.5–0.7 zone is ambiguous and needs γ. **Do NOT lower the β merge threshold to 0.5** — that would over-merge 60% of cases that γ actually splits.

_Files: `src/deck_builder/gamma_llm.py` (schema + export), `src/deck_builder/beta_score.py` (β), `src/deck_builder/simplify_senses.py` (orchestrator + 3-tier fallback), `tools/_apply_gamma_verdicts.py` (apply γ overrides)._

### Gloss pipeline

The layer that produces 2-6 word learner-friendly paraphrases of Oxford's
verbose definitions, shown on the back card instead of the full Oxford text.
Decision recorded in [`docs/adr/0005-gloss-pipeline-rendering.md`](./docs/adr/0005-gloss-pipeline-rendering.md).

**Gloss**:
A short (1-6 words total) learner-friendly paraphrase of a single card's def.
May be 1 chunk (1 sense), 2 chunks joined by `|` (distinct senses rendered as separate card rows), or 2 chunks joined by `;` (variants/sub-nuances rendered in 1 row). Stored in the Anki note's `Definition` field as the def column — replaces the long Oxford def at apply time.
_Avoid_: short def, mini definition, paraphrase

**Gloss Verdict**:
A single M3 (the agent itself, not an external LLM HTTP call) decision for one job. Schema: `(gloss, separator, count, rule_applied)` where separator ∈ `{none, '|', ';'}`, count = number of chunks, rule_applied ∈ `VALID_RULE_CODES` (9 granular codes: `rule_b_pick1`, `rule_b_pick2`, `rule_b_pick2_addendum`, `2sense_samedomain`, `2sense_distinct`, `concrete_1sense`, `multi_pos_pick1`, `multi_pos_pick2`, `safety_net`). Schema stored in `GlossVerdict` dataclass in `src/deck_builder/gloss_llm.py`.
_Avoid_: gloss decision, gloss entry

**M3 Rerun**:
The batch script (`tools/_m3_rerun_v2.py`) that re-generates M3 verdicts for the 889 cards whose `def` field changed format after the `|` encoding fix. Re-reads jobs from `data/simplify_diff/gloss_jobs.jsonl` (2,477 jobs total, 889 need re-run), looks up verdict in `M3_VERDICTS` dict, runs validation gate, writes passing verdicts to `data/simplify_diff/gloss_rerun_verdicts.json` and violations to `data/simplify_diff/gloss_rerun_violations.json`. **Critical:** new verdicts must be appended at END of dict (Python dict literal last-wins).
_Avoid_: regenerate verdicts, gloss rebuild

**Gloss Validation Gate**:
The 4-rule automated check in `validate_verdict(word, gloss, separator, count)` in `src/deck_builder/gloss_llm.py`. Returns `list[str]` of violations (empty = pass, never raises). Rules: (1) separator/count/content consistency, (2) word count 1-6 total + per-chunk 1-3 (`;`) / 1-4 (`|`) / 1-6 (none), (3) headword in any chunk (catches self-ref + leak), (4) no-gloss bypass. Defense-in-depth: called from 3 sites (M3 rerun, apply-to-txt, `__post_init__`).
_Avoid_: gate, validator, gloss checker

**Apply-Step Skip**:
A defense-in-depth behavior in `_apply_glosses_to_txt.py`: when a verdict fails the gate at apply time, the corresponding card keeps its original Oxford def instead of the bad gloss. Stops bad data from being written. Outputs `Skipped N verdicts due to gate violations` summary. Distinct from "Skip Rule" in merge layer (which is about records, not verdicts).
_Avoid_: apply skip, gate skip

**Sense Drop Invariant**:
When the gloss for a card has fewer chunks than the example set (e.g. gloss has 2 chunks because M3 dropped sense 3 as a sub-nuance), the template's `def[i]` ↔ `ex[i]` pairing **drops the extra examples silently**. So 2-chunk gloss + 3-chunk ex → card shows 2 sense rows; the 3rd example is dropped, NOT orphaned. The reverse (more gloss chunks than ex) is a bug — gate does not catch this; verified manually. **Pairing invariant: `gloss_count == ex_count` per card.** If mismatched, fix by re-deciding the gloss (drop or extend to match ex).
_Avoid_: example drop, gloss-ex mismatch

**Gloss Rule A — No Synonym Pairs**:
If 2 kept senses are near-synonyms (same concept, different wording), output 1 word only. `ridiculous; nonsensical` → `ridiculous` (collapse). **NOT auto-detectable by the gate** — would need a synonym DB. Verified by M3 + human review. Structural passes through gate (e.g. `absurd: ridiculous; illogical`); semantic review is manual.
_Avoid_: synonym rule, Rule A

**Gloss Rule B — Multi-Sense 3+**:
If the def has 3+ senses: pick 1 gloss if all senses are variants or sub-nuances of the same core concept; pick 2 glosses (`|`) if first 2 cover clearly different domains, usage contexts, or grammatical roles. **NEVER pick 3.** Drop a sense (even if not sub-nuance) if domain-restricted (music, law, finance, medicine) AND unlikely in general IELTS. After picking, apply Rule A or the separator semantics.
_Avoid_: pick rule, 3+ rule, Rule B

**Gloss Rule B Addendum — Physical/Tactile vs Abstract**:
When judging "variants vs different domains" for 3+ sense cluster, treat a **physical/tactile** sense (touching, holding, operating a physical object with hands) as a different domain from an **abstract** sense (managing a situation, an idea, or an emotion) — even if a single gloss word could loosely cover both. Pick 2 in this case. Example: `handle` has "deal with situation" (abstract), "touch/hold object" (physical), "control vehicle" (physical) → abstract + physical = different domains → pick 2 with `|`.
_Avoid_: tactile rule, physical rule, Rule B addendum

**Gloss Rule C — Safety Net**:
If dropping a sense would leave the card with no gloss, keep it regardless of domain restriction. Never produce an empty gloss. Example: `measure` at C1 is the only music-domain sense; Rule B would drop it as niche, but Rule C forces it to stay so the card has content.
_Avoid_: safety net, Rule C

**Rule-Shape Consistency**:
A `Gloss Verdict` must have a separator/chunk shape consistent with its `rule_applied`. The rule encodes the structural promise; the gloss must honor it.

| `rule_applied` | Required shape |
|---|---|
| `rule_b_pick1`, `concrete_1sense`, `multi_pos_pick1` | one chunk allowed (no separator) |
| `2sense_distinct`, `3sense_distinct`, `rule_b_pick2`, `rule_b_pick2_addendum`, `multi_pos_pick2` | **must have more than one chunk** (`|` or `;`) |
| `2sense_samedomain` | one chunk allowed when Rule A collapses near-synonyms; otherwise `;` or `|` may be justified by review |
| `pos_aware_gloss` | policy review (one chunk may be intentional, see P4B addendum) |

A `rule_b_pick2` verdict with a single-chunk gloss is a **rule-shape contradiction** — the rule says "pick 2" but the gloss has only 1. Caught and fixed by P4B (`tools/_apply_p4b_rule_shape_fix.py`). The reverse — many `def_before` segments collapsing to one gloss — is **not** automatically a bug: Rule A allows near-synonym collapse, Rule B allows same-concept collapse, Rule C forces retention. Use `tools/_audit_gloss_policy_coverage.py` to classify rows into `allowed_single_gloss` / `rule_shape_contradiction` / `policy_review` / `metadata_error` buckets.
_Avoid_: rule-shape mismatch, "1-chunk with multi-def def_before is a bug" (it isn't always — see Rule A/B/C).

**`|` vs `;` separator semantics** (strict):
- `|` (pipe, no spaces) = distinct senses in different domains → rendered as separate rows on the card. The template splits on `|` to pair each chunk with its example.
- `;` (semicolon-space) = senses in the same domain (variants, sub-nuances, related uses) → 1 row, both glosses in the same def slot. The template does NOT split on `;` — the chunk is kept as one definition text.
- `none` (no separator) = single sense → 1 chunk, 1 row.

A common bug: declaring `|` in the verdict but writing `;` in the gloss content. The validation gate catches this as `separator_mismatch`.

**M3** (Gloss Verdict author):
The agent itself (mavis), reasoning as an English lexicographer to produce glosses for a batch of jobs. M3 reads jobs from `data/simplify_diff/gloss_jobs_to_rerun.jsonl`, decides glosses based on the prompt rules, and writes them into `M3_VERDICTS` dict in `tools/_m3_rerun_v2.py`. **M3 is the same agent for all gloss work** — no external LLM HTTP call. Output cached by `cluster_hash` so re-runs are free. (Same M3 also acts as γ-judge in 3-tier sense-merging — see above.)
_Avoid_: LLM judge, gloss generator

### Design system structure

**Design System**:
The visual and structural system covering all Anki card elements — color tokens, typography, components, sample cards, and reference data — defined in `design/index.html` and split into 5 regions.
_Avoid_: Card design, theme, style guide

**Source of Truth**:
`design/index.html` is authoritative for the Anki card CSS. The `EAVM/styling.txt` file is derived from its vùng 2 region and must stay in sync via the drift check. Any CSS change starts in `index.html` first.
_Avoid_: Master file, primary file

**Card CSS Region** (vùng 2):
The bounded CSS section in `design/index.html` between the `ANKI CARD STYLES — must match EAVM/styling.txt exactly` and `END ANKI CARD STYLES` marker comments. The content between these markers must be 1:1 with `design/EAVM/styling.txt` (modulo `/* @preview-only */` markers).
_Avoid_: Card styles, Anki CSS block

**Drift Check**:
The automated comparison between vùng 2 of `design/index.html` and `design/EAVM/styling.txt`, implemented in `tools/check_design_sync.py` (CLI) and `tests/design/test_design_sync.py` (pytest). Exits 0 if in sync, 1 if drift.
_Avoid_: Sync check, CSS validation

**Preview-only Rule**:
A CSS rule in `design/index.html` marked with the `/* @preview-only */` comment on its own line immediately before the rule. Such rules are excluded from the drift check and are not synced into `EAVM/styling.txt` / `.apkg`. Use this for properties that intentionally differ between preview (e.g. fixed width) and production (e.g. fluid width).
_Avoid_: Excluded rule, design-only rule

**Selector Contract**:
Class names in `design/index.html` are immutable across the design and template files. Renaming a selector in `index.html` requires updating all references in `EAVM/front_template.txt` and `EAVM/back_template.txt` as well. Enforced by convention, not by tooling.
_Avoid_: CSS class, hook name

### Data sources

**Oxford Record**:
A word entry in `data/oxford_full.jsonl` produced by scraping Oxford Learner's Dictionary. Carries the full per-def schema (`n`, `sensenum_local`, `is_idiom`, `text`, `examples`, `cefr`) and Oxford-only fields populated (`oxford_lists`, `opal`, `awl`, `register_tags`, `topics`). `source = "oxford"`.
_Avoid_: Oxford scrape entry, OLD record

**Cambridge Record**:
A word entry in `data/cambridge_full.jsonl` produced by scraping Cambridge Dictionary. Carries the same per-def schema as Oxford records but with Oxford-only fields **empty** (`oxford_lists: []`, `opal: null`, `awl: null`, `topics: []`) — Cambridge thuần, không inherit. `register_tags` is parsed from Cambridge's `<span class="usage dusage">` labels (e.g. `formal`, `informal`, `slang`, `specialized`). `source = "cambridge"`.
_Avoid_: Cambridge scrape entry, dictionary entry

**Topic**:
One entry in a record's `topics: list[{name, cefr}]` field. `name` is an Oxford academic-subject tag (e.g. "Difficulty and failure", "War and conflict"); `cefr` is the per-topic CEFR from Oxford's `<span class="topic_cefr">` (one of `A1`–`C2`, or `""` when the page doesn't tag a topic with a level). A word can have the same `name` at multiple CEFRs (e.g. "Education" at B1 in one sense, C2 in another); both pairs are kept. The 23 canonical `name` values live in the labels taxonomy `data/oxford_labels.json → subject_labels`. Cambridge records always have `topics: []` (Cambridge doesn't expose per-topic CEFR).
_Avoid_: subject tag, subject label (legacy term), topic tag

**Idiom Detection**:
The detection of idioms in a record produces two distinct outputs that must not be confused:

1. **Per-def flag** — a `definitions[].is_idiom: bool` marker on the sense that lives inside an idioms block. Does not extract the phrase text; only signals "this def is an idiom". Idioms have `sensenum_local = None` by convention.
2. **Top-level `idioms[]`** — a separate record-level array of `{phrase, pos, text, register_tags, cefr}` entries (e.g. "have the floor", "in the blink of an eye") that carries the phrase text and metadata for the idiom box render.

Oxford idiom detection: walk parent chain from each `<span class="idm">` for `<div class="idioms">` ancestor (sets `is_idiom=True`); for top-level `idioms[]`, read `<span class="idm">` directly into the `phrase` field. Cambridge idiom detection: walk parent chain for `<div class="idiom-body">` or `<div class="phrase-di-body">` ancestor, read the `<h2 class="headword">` in the preceding `<div class="di-title">`.
_Avoid_: Phrase flag, idiom marker

**Phrasal Verb Page**:
A separate Oxford cache file at `oxford_<base>-<particle>_(phrasal_verb).html` (e.g. `oxford_deprive-of_(phrasal_verb).html`) that holds the real definitions for a pattern-heavy verb. The base word's main page (e.g. `oxford_deprive.html`) is a stub that links to this page. Without it, the main word has empty `pos_data` and `idioms` — see **Skip Rule** and **Phrasal Verb Folding**. The `word` field of a phrasal-verb record includes the space (e.g. `"deprive of"`), and `pos` is `["phrasal verb"]`.
_Avoid_: phrasal verb entry, PV page

**Phrasal Verb Folding**:
A merge-layer post-processing step that detects phrasal-verb records (records where `pos_data[0].pos == "phrasal verb"`) and folds their definitions into the main word's record. The main word (e.g. `deprive`) gains a new `pos_data` entry with `pos: "phrasal verb"` and the definitions from the phrasal-verb page. The phrasal-verb record itself is then flagged `_skip: true` with `_skip_reason: "folded-into-main-word: <main-word>"` to prevent duplicate cards. Result: searching the deck for `deprive` shows the card "deprive (verb) = deprive of [phrasal pattern] = tước đoạt", matching how OALD presents it.
_Avoid_: PV merging, fold into main

**Fetcher Cache**:
The on-disk cache that lets a fetcher return previously-fetched HTML without re-hitting the network. Lives in `data/.cache_html/<source>/` (one subdir per source). Each source uses a distinct cache filename prefix to avoid collisions when the same word is scraped from multiple sources:

- **Oxford** (`data/.cache_html/oxford/`): three legitimate forms (see **Polymorphic Cache**) — `oxford_<word>.html`, `oxford_<word>_(<pos>).html`, or `oxford_<word>_<N>_(<pos>).html`. Cache prefix: `oxford_`.
- **Cambridge** (`data/.cache_html/cambridge/`): single form — `cambridge_<word>.html`. Cache prefix: `cambridge_`.

The subdirectory + filename prefix together disambiguate sources. The prefix is wired in `src/scraper/fetch.py` via `HttpFetcher.cache_prefix` (default `""`).
_Avoid_: HTML cache, scrape cache

**Polymorphic Cache**:
The property of a fetcher's cache where the same word may produce multiple files, one per scraping variant the source returned. For the Oxford cache (`data/.cache_html/oxford/`) three forms coexist:

- `oxford_<word>.html` — multi-POS "main page" (Oxford's default URL response); also used when a word has a single entry that isn't categorized. ~70 files expected after dedup (see **Semantic Duplicate**); 263 raw before dedup.
- `oxford_<word>_(<pos>).html` — POS-specific page; canonical form for new scrapes.
- `oxford_<word>_<N>_(<pos>).html` — POS-specific page with disambiguation index N, used when Oxford returns 2+ distinct pages for the same `(word, pos)` pair (e.g. different homonyms). 970 files in the current cache (all preserved by dedup — they have the highest specificity score).

**Important:** the 3 forms are **byte-distinct** (0 SHA-256 collisions across 7,975 files) but NOT all **semantic-distinct** — see **Semantic Duplicate**. Two files can have different bytes (different CSRF tokens, different WOTD widget) but the same dictionary content. Renaming between forms requires checking the target name doesn't already exist.
_Avoid_: POS-suffixed file, indexed cache

**Canonical Redirect**:
The Oxford HTML page contains `<link rel="canonical" href="https://www.oxfordlearnersdictionaries.com/definition/english/<slug>">` in its `<head>`. This is Oxford's authoritative URL for the content the page represents. When a user fetches a non-canonical URL (e.g. `/aggregate` when only one homonym exists), Oxford still serves the page but the `<link rel="canonical">` points to the authoritative URL (e.g. `/aggregate_1`). This means a cache file saved from the non-canonical URL (e.g. `oxford_aggregate_(noun).html`) and a cache file saved from the canonical URL (e.g. `oxford_aggregate_1_(noun).html`) reference the **same authoritative content** — see **Semantic Duplicate**. The canonical slug is the path's last segment (e.g. `/definition/english/aggregate_1` → slug `aggregate_1`).
_Avoid_: authoritative URL, primary URL

**Skip Rule**:
A merge-layer decision (in `src/scraper/merge.py`) that flags a record with `_skip: true` and a human-readable `_skip_reason` when the record would produce no usable Anki card. The Anki builder MUST check `_skip` and skip these records. Two rules exist:

1. **Phrasal-verb-redirect rule**: if `pos_data` is empty AND `idioms` is empty (e.g. the main-word page `oxford_deprive.html` is a stub that links to a separate **Phrasal Verb Page**), set `_skip: true, _skip_reason: "phrasal-verb-redirect: no extractable senses"`. The corresponding phrasal-verb record (e.g. `deprive of`) is folded into the main word per **Phrasal Verb Folding**, restoring the data.

2. **Proper-noun-or-cultural-entry rule**: if `pos_data` is non-empty AND every `pos_data[*].pos == "unknown"` AND `oxford_badge is None` AND `oxford_lists == []` AND no `def.cefr` is non-null on any sense, set `_skip: true, _skip_reason: "proper-noun-or-cultural-entry: no CEFR/oxford-list membership"`. This catches biographies (Buck Rogers, Buddy Holly), TV shows (Casualty, Horizon), rivers/cities (Forth, Independence) and other non-vocabulary entries that Oxford OALD includes. Records with ANY curriculum signal (badge, list, or CEFR) are kept — the rule is intentionally conservative to avoid false positives.

3. **Folded-into-main-word rule**: after **Phrasal Verb Folding**, the original phrasal-verb record is flagged `_skip: true, _skip_reason: "folded-into-main-word: <main-word>"` so the builder doesn't generate a duplicate card.

Records with `_skip: true` are NOT removed from `data/oxford_merged.jsonl` — the audit trail is preserved. The builder reads `_skip` to decide which records to render into `.apkg`. Adding a new rule means: (1) implement the check in `merge.py`, (2) add tests in `tests/scraper/test_merge.py`, (3) add the reason to this entry.
_Avoid_: skip flag, exclude, drop record

**Semantic Duplicate**:
Two cache files that reference the same authoritative content (same `<link rel="canonical">` path) even if their bytes differ. The byte differences are noise from Oxford's page furniture, not the dictionary data:

- **CSRF token** in `<meta name="_csrf" content="...">` — session-specific, regenerated per page load.
- **WOTD widget** (Word of the Day) — Oxford shows a rotating vocabulary word in the sidebar (e.g. "summary" on one scrape, "valid" on another) under `<div class="wotd-box">`.
- **Sidebar promos** — text like "Definitions on the go" or empty `<p></p>` placeholders.

The dictionary content (headword, POS, verb forms, definitions, examples, IPA, audio URLs) is identical between semantic duplicates. Detection: extract `<link rel="canonical">` path from each file's `<head>`, group by that path. Resolution rule: keep the most specific file (has `_N_` index +2, has POS suffix +1; tiebreak by newest `LastWriteTime`); move losers to a backup folder. Verified on 2026-06-10: 1,146 of 7,975 Oxford cache files (14.4%) were semantic duplicates and moved to `data/.cache_html/_dup_backup/`. After dedup: 6,829 files, exactly 1 per canonical URL.
_Avoid_: content duplicate, byte duplicate

## Scraper architecture

**Parser Backend**:
The HTML parsing engine used by the scraper to read Oxford and Cambridge cache files. Currently `lxml.html.fromstring()` + `lxml.Element.cssselect()`. BeautifulSoup4 with the `lxml` parser backend was the prior implementation; it is retained only as a fallback and is no longer used in the production path. Decision recorded in [`docs/adr/0001-lxml-parser-backend.md`](./docs/adr/0001-lxml-parser-backend.md).
_Avoid_: parser, HTML parser, scraper engine

**Forward Query**:
A selector-based traversal that matches descendants in a single pass (`root.cssselect("li.sense")` ≡ BS4 `find_all(class_="sense")`). The dominant operation in the scraper — covers ~95% of all DOM lookups (sense rows, definitions, examples, IPA, POS, etc.). Cheap, cacheable, easy to equivalence-test.
_Avoid_: CSS query, descendant query, selector

**Ancestor Walk**:
A reverse traversal that walks the parent chain from a matched element back to the document root (`el.iterancestors()` for lxml, `len(list(el.parents)) - 1` for BS4 to exclude the `BeautifulSoup` document object). Used in ~5% of cases where a forward query is insufficient — currently 2 sites in idiom detection (per `Idiom Detection`): Oxford `<div class="idioms">` ancestor, Cambridge `<div class="idiom-body">` or `<div class="phrase-di-body">` ancestor.
_Avoid_: parent walk, parent chain, reverse query
