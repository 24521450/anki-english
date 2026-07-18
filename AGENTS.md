# AGENTS.md

IELTS / Academic English Anki deck builder — notes DB + scraper pipeline (Oxford / Cambridge + AWL + Oxford audio).

> **Read first:** [`CONTEXT.md`](./CONTEXT.md) for the project glossary (canonical terms, no implementation details). Come back here for commands, layout, and conventions.

Documentation ownership: `CONTEXT.md` holds current vocabulary;
`docs/adr/` records rationale and trade-offs; `USER_NOTES.md` is chronological
user-request provenance; `data/README.md` owns artifact lifecycle;
`tools/README.md` owns supported workflows; this file owns operations.

## Setup commands

- Install deps: `pip install -r requirements.txt` (then `python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"`)
- Build (editable): `pip install -e .`
- Test: `pytest` — config in `pyproject.toml [tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["."]`
- Environment-specific coverage is marked `external`; run it explicitly with `pytest -m external`.
- Lint: not configured — match existing style, no new lint configs without asking

## Project layout

- `src/` — Python package (per `pyproject.toml [tool.setuptools]` — package skeleton not yet committed)
  - `scraper/` — owned by `scraper` rein: Oxford/Cambridge + AWL data ingestion, audio assets
  - `deck_builder/` — owned by `deck-builder` rein: `.apkg` packaging, EAVM note type generation
  - `config.py` — shared config
- `tests/` — pytest tests, mostly mirrored layout (`tests/scraper/test_x.py` ↔ `src/scraper/x.py`). Non-mirrored layout allowed for cross-cutting infra (e.g. `tests/design/test_design_sync.py`).
- `tools/` — maintained standalone CLIs and shared helpers (not part of the `src/` package). One-shot migrations are removed after their outputs and durable regressions become canonical; recover retired commands from Git history instead of keeping executable archives in `HEAD`.
- `data/` — lifecycle-organized artifacts; `.cache_html/` and `*.bak` are gitignored
  - `sources/` — canonical Oxford and Cambridge scraper outputs
  - `curated/` — production audit overrides
  - `review/` — review verdicts and manual fills consumed by the build
  - `build/` — generated Anki-ready TXT and JSONL notes
- `audio/` — generated headword audio plus content-addressed UK/US Example Audio
- `design/` — Anki card visual design system. **`design/index.html` (vùng 2 card CSS) is the source of truth** — `EAVM/styling.txt` derives from it and is baked into `.apkg`. `tools/check_design_sync.py` enforces the sync.
- `docs/adr/` — Architecture Decision Records. One file per decision, named `NNNN-title.md` (e.g. `0001-lxml-parser-backend.md`). Add a new ADR whenever a decision meets all 3 criteria: hard to reverse, surprising without context, and a real trade-off.
- `vocab_list/` — source word lists (Oxford 3000/5000 markdown, AWL json/yml)
- `update_anki_deck.py` — top-level packager (`data/build/anki_notes.jsonl` → `ielts_deck.apkg`). Owned by `developer` rein.
- `src/pipeline.py` — production-stage orchestrator: `scrape → example-audio → build → validate → deck → import`. Run with `python -m src.pipeline`. Supports `--from=<stage>`, `--to=<stage>`, `--dry-run`, single-stage (`python -m src.pipeline build`). Every non-dry-run execution that includes `deck` automatically appends the `import` stage, including an explicit `--to=deck` or single-stage `deck` command. `--dry-run` never appends a live import.
  - **scrape**: Oxford/Cambridge + AWL ingestion, audio. Keeps all senses / all CEFR entries (raw).
  - **example-audio**: derives final Example/Idiom Example speech from the registry build plan, with main Examples owned by the promoted Semantic Registry, and generates missing Edge TTS media. Run this stage, stage changed `audio/example_*.mp3` in Git, then continue from `build` so release validation can enforce tracked media.
  - **build**: enriches with CEFR resolution + audio refs. **Enforces [Card Identity](./CONTEXT.md), the reviewed [Learner Relevance Filter](./CONTEXT.md), and [Sense Sorting](./CONTEXT.md)**, then replaces the final Definition/Example payload with `data/curated/semantic_registry.jsonl`. The production command fails closed when that registry is missing or invalid. See `design/README.md § Card design rules` for the rule reference.
  - **validate**: checks registry, card identity, JSONL/TXT parity, audio references, and deterministic output before publish.
  - **deck**: bakes `.apkg` via `update_anki_deck.py`.
  - **import**: imports the validated `.apkg` through AnkiConnect and verifies the EAVM note type, byte-exact media, and note GUID coverage through a post-import APKG export. Requires Anki + AnkiConnect to be running; never edits `collection.anki2` directly.
  - Archived one-shot fixers are unsupported and are not wrapped by the pipeline.

### Bilingual semantic audit and promotion

- `python -m tools.semantic_audit scaffold` creates the canonical pending ledger
  at `data/review/bilingual_semantic_audit.jsonl` from Card Registry, the current
  built notes, and Oxford/Cambridge source records.
- `python -m tools.semantic_audit export-xlsx` creates the editable review view
  at `scratch/bilingual_semantic_audit.xlsx`; `import-xlsx` validates immutable
  fingerprints and writes decisions back transactionally to JSONL.
- `python -m tools.semantic_audit validate --require-complete` is the promotion
  gate across the bilingual semantic, idiom, all-sense Vietnamese, Definition
  concision, Semantic Sense merge, and semantic-policy authorities.
  Pending/uncertain decisions, unapproved repairs, stale fingerprints, missing
  candidate coverage, or unaccounted source senses fail.
- `python -m tools.semantic_audit promote` deterministically writes the complete,
  approved sense and idiom payload to `data/curated/semantic_registry.jsonl`.
  Re-running it from the same ledgers must be byte-identical.
- `python -m tools.idiom_audit scaffold` creates the phrase-level pending
  ledger at `data/review/bilingual_idiom_audit.jsonl` for idioms selected by
  active cards. `export-xlsx` / `import-xlsx` provide a fingerprint-protected
  review view, and `validate --require-complete` is mandatory before promotion.
  `report --output scratch/bilingual_idiom_audit_report.md` lists every review
  exception plus a deterministic 30-row high-confidence sample for sign-off.
  An unchanged `bilingual_gloss` is not automatically reviewed: retaining the
  previous wording requires a row-specific reason that names a shorter wording
  considered and the exact material meaning it would lose, or cites an exact
  user-locked canonical pair. Never bulk-pass unchanged rows.
- `python -m tools.collocation_audit scaffold` creates the two-way,
  fingerprint-bound ledger at `data/review/collocation_audit.jsonl` from active
  cards, Semantic Source Coverage, and Oxford/Cambridge Collocation Evidence.
  `export-xlsx` / `import-xlsx` preserve immutable fingerprints;
  `validate --require-complete` rejects every pending, uncertain, stale,
  unapproved, over-budget, or unaccounted item; `report` produces a review view;
  and `promote` deterministically writes
  `data/curated/collocation_registry.jsonl`. Never treat a scraper candidate as
  approved, bulk-pass unchanged chips, or hand-edit the promoted registry.
- `python -m tools.semantic_audit definition-audit` creates a report-only audit
  in `scratch/` for unusually long, token-heavy, or connector-heavy Definition
  text. The default 12-token trigger is review triage, not a length cap. The
  report may consume an explicit scratch review file via `--reviews`; it never
  writes the canonical ledger or Semantic Registry.
- `python -m tools.semantic_audit definition-review-scaffold` creates the
  fingerprint-bound canonical candidate ledger at
  `data/review/definition_concision_review.jsonl`. Promotion requires exact
  current coverage and approved `keep_explanatory` rows with a genuinely
  shorter or connector-reduced alternative, the exact preserved distinction,
  and row-specific semantic evidence. A required rewrite or split must first be
  applied through the Bilingual Semantic Audit, then the queue must be
  regenerated; a report verdict does not mutate canonical data.
- `python -m tools.semantic_audit sense-merge-audit` creates the fingerprint-bound,
  report-only Semantic Sense Merge Audit in `scratch/`. After every candidate is
  reviewed, pass `--reviews`, `--bundle-output`, `--reviewer`, `--reviewed-at`,
  and `--approval approved` to create a canonical-compatible review bundle in
  `scratch/`; apply that bundle through `apply-review`, then regenerate and
  complete the canonical candidate ledgers before validation and promotion.
  Bundle generation remaps every affected source before removing a Semantic Sense.
- `python -m tools.semantic_audit sense-merge-review-scaffold` creates the
  fingerprint-bound canonical candidate ledger at
  `data/review/semantic_sense_merge_review.jsonl`. Promotion requires exact
  current coverage and an approved, row-specific `keep_separate` distinction
  citing at least two affected Semantic Sense IDs. Merge/reword proposals,
  uncertain verdicts, unapplied bundles, generic explanations, and stale rows
  block promotion.
- `python -m tools.semantic_audit vietnamese-audit` creates the report-only
  `DefinitionVI` naturalness queue in `scratch/`. The default eight-token
  threshold is review triage, not a length cap and never an automatic rewrite.
- `python -m tools.semantic_audit vietnamese-review-scaffold --scope all`
  creates the fingerprint-bound canonical review ledger for every promoted
  Semantic Sense at
  `data/review/vietnamese_naturalness_review.jsonl`. Complete its explicit
  `keep_natural` / `keep_explanatory` / `rewrite` decisions, then run
  `python -m tools.semantic_audit apply-vietnamese-review`; stale, incomplete,
  uncertain, or unapproved review state fails before the bilingual semantic
  ledger changes or promotion proceeds. Unchanged text is not automatically
  reviewed; an approved row is reused only while its per-sense fingerprint is
  unchanged, and every new or changed sense must receive a new verdict. Every
  resolved row needs a decision-specific `reason_code` and unique,
  wording-specific `semantic_evidence`; `reason_code=user_lock` additionally
  requires the exact `lock_id`, while non-locked rows must leave `lock_id`
  empty. Ordinary evidence must cite the row's exact English sense and a
  sense-specific example or source definition. Interpolating the headword or
  final VI into shared approval prose is still a bulk pass; normalized generic
  or duplicate templates fail validation.
  `validate --require-complete` and `promote` both require exact coverage from
  this all-sense ledger.
- `python -m tools.semantic_audit vietnamese-review-scaffold --scope long`
  remains available for long-gloss verbosity triage, but cannot satisfy the
  canonical all-sense promotion gate. In this scope, `rewrite` must reduce the
  whitespace-token count; `keep_explanatory` must record a strictly shorter
  wording considered and the exact material distinction it would lose. Merely
  changing punctuation or word order does not close a verbosity finding.
- `data/curated/semantic_policy_locks.jsonl` is the machine-readable release
  policy for exact wording and retained/excluded/absent sense decisions. The
  exact user locks `compel` → `ép buộc`, `contender` → `đối thủ nặng ký`,
  `transcribe` → `chép lại`, and `venture` → `mạo hiểm, cả gan` are release
  invariants. Change any of them only after an explicit user instruction and a
  coordinated code/data update; deleting or superseding a ledger row must not
  relax them silently.
- Since the ADR 0011 cutover on 2026-07-15, Semantic Registry owns production
  Definition/Example content and the promoted bilingual Idiom Box payload. The
  legacy β/γ/M3 and review layers still support source indexing and non-semantic
  metadata during the remaining decoupling; they must not override the promoted
  final semantic payload.

### Change-impact matrix

| Change | Required path | Forbidden shortcut |
| --- | --- | --- |
| Definition EN/VI or examples | Update the fingerprint-bound review input, validate all affected ledgers, promote, rebuild, and run release validation. | Hand-edit Semantic Registry or build outputs. |
| Remove or retain a source sense | Use the reviewed Learner Relevance Filter, account for every source ID, and add/retain stable regression evidence. | Delete by label, length, or specialist heuristic alone. |
| User-locked VI wording | Obtain explicit user instruction, then update the matching policy/code/data contract and regenerate every downstream artifact. | Infer permission from a dictionary/source change or silently supersede the lock. |
| Collocation text/provenance | Update the fingerprint-bound Collocation Audit, account for current chips and mandatory example-linked source evidence, promote, rebuild, and run release validation. | Hand-edit Collocation Registry/build output, auto-promote scraper labels, or mix reviewed and legacy ownership. |
| Parser fixture | Declare it in the clean-checkout fixture manifest with semantic assertions; hydrate through the shared helper. | Read an undeclared ignored cache file from a default test. |
| Generated artifact | Run its documented canonical writer and verify deterministic output contains no unrelated changes. | Treat an output file as an upstream authority. |
| Release/import | Run the CI-equivalent guard, full `pytest`, pipeline validation, package provenance check, and verified AnkiConnect import when live release is in scope. | Import a stale/unverified `.apkg` or edit `collection.anki2`. |

## Architecture context

For non-trivial tasks, read `.understand-anything/knowledge-graph.json` for the structural map (files, layers, tour).

If the file is missing or stale, run `/understand --full` to (re)build it.

Refresh with `/understand --full` after major refactors.

Current refactor target: `src/deck_builder/build_support.py` is the highest
degree deck-builder helper module. If reducing it, start with pure formatting
helpers and keep compatibility re-exports from `build_support.py`; do not begin
by moving `lookup_gloss`, `_resolve_audio_filename`, `resolve_primary_record`,
or source-indexing logic without characterization tests.

## Subagent policy

The primary agent is the coordinator: it chooses the design, keeps cross-cutting
context, merges/reviews results, and runs final verification.

Delegation gate:

- Do small, sequential, or tightly coupled tasks directly.
- Use project-local native subagents in `.codex/agents/` for medium/large tasks
  with clear scope, especially scoped reading, investigation, command/test
  execution, focused edits, review, and concise summaries.
- Use at most 3 delegated agents at once, only for independent workstreams with
  explicit output contracts and non-overlapping write scopes.
- Review only the needed summary, diff, and verification evidence before
  integrating results.

Native subagent roster:

- Project-local native subagents in `.codex/agents/` currently use
  `gpt-5.6-sol` with `model_reasoning_effort = "medium"`. Treat
  `.codex/agents/*.toml` as the source of truth if this summary drifts.

- `scraper-ingestion`: Oxford/Cambridge parsers, merge, scraper audio,
  `tests/scraper/`.
- `deck-builder`: registry build, Card Identity, Sense Sorting, validation,
  publish contracts, `tests/deck_builder/`.
- `design-system`: EAVM templates, `design/index.html`, CSS sync,
  `tests/design/`.
- `pipeline-release`: `src/pipeline.py`, `update_anki_deck.py`,
  `tools/build_notes.py`, packaging/pipeline tests.
- `verification-test`: pytest slices and regression triage; read-only by
  default unless patching is explicitly assigned.
- `data-audit-tools`: audit/check tools, determinism, registry sync,
  audio/AWL/corpus integrity, `tests/tools/`.

Delegation prompts must include objective, relevant context, allowed files,
forbidden files, expected output, and tests to run. Keep a compact handoff for
each active workstream: objective, decisions, changed files, verification
status, and next action. Use MCP Codex workers only as fallback; workers 2-4 are
`gpt-5.4-mini` medium, and workers 5-6 are `gpt-5.5` high for
complex/high-risk review. `.codex/worker-rotation.json` applies only to MCP
fallback.

## Code style

- Python 3.10+ (async-friendly: `aiohttp`)
- Async I/O for scraping + TTS — match the existing pattern, don't mix blocking
- No formal docstring format enforced; brief comments are fine
- For terminology: use terms from [`CONTEXT.md`](./CONTEXT.md). If you introduce a new concept, add it there.

## Testing instructions

- `pytest` only — no new test framework without asking
- Add tests for every new behavior — mirror layout: `tests/scraper/test_x.py` ↔ `src/scraper/x.py`; cross-cutting infra allowed elsewhere (e.g. `tests/design/test_design_sync.py`)
- All tests must pass before commit
- `pythonpath = ["."]` in pytest config → use absolute imports via `src.*`

### Test slices

- Smoke: `pytest tests/test_config.py tests/test_pipeline.py tests/test_schema_validation.py tests/test_drift_guard.py tests/test_documentation_contracts.py tests/tools/test_sync_card_registry.py`
- Scraper: `pytest tests/scraper`
- Deck builder core: `pytest tests/deck_builder -m "not external"`
- Design: `pytest tests/design`
- Tools: `pytest tests/tools`
- Full: `pytest`
- External coverage is opt-in only: `pytest -m external`

Use the narrowest slice that covers the changed behavior during iteration. Run
full `pytest` before commit/release or after cross-layer changes.

## PR & commit conventions

- **Single-branch project** — commit directly to `main`. No feature branches, no PRs.
- Conventional commits (`feat:` / `fix:` / `docs:` / `refactor:`)
- One concern per commit — don't bundle scraper change with design change
- Run `pytest` before pushing; red build = revert or fix-forward

## Domain-specific notes

### Audio TTS fallback chain
For each `(word, accent ∈ {UK, US})` pair, try in order:
1. Cambridge dictionary audio URL
2. Oxford Learner's audio URL
3. no audio

### Example Audio generation

- Engine: `edge-tts==7.2.8`; UK `en-GB-RyanNeural`, US `en-US-JennyNeural`.
- Fixed synthesis: rate `-5%`, pitch `+0Hz`, volume `+0%`; no API key.
- Only the clean spoken copy is synthesized. Visible Example/Idiom text is unchanged; parenthetical glosses are omitted from speech.
- Files are content-addressed as `audio/example_{uk|us}_{digest}.mp3`, committed to Git, and referenced from the four appended EAVM audio fields.
- Edge is a remote service: deterministic means stable inputs, names, references, and cache reuse. Forced regeneration is not guaranteed byte-identical.
- Example Audio is manual-play only. Do not replace its HTML `<audio src>` references with `[sound:...]`, which would put every clip into Anki's autoplay queue.

### Oxford HTML structural quirks (learned 2026-06-10)
- Oxford HTML uses `hclass` ATTRIBUTE (not `class`) on most elements: e.g. `<li class="sense" hclass="sense" cefr="c2">`. CSS selectors using `hclass=` (e.g. `[hclass='sense']`) often work, but `li.sense` also works for top-level. Some elements use both `class` and `hclass`.
- **pos-g element is a TRAP**: `<pos-g hclass="pos">` markers appear ALL OVER the page (12+ on `sick_1_(adj).html`) — most are in `<span class="arl1">`/`<span class="arl2">` (related-entries links at top of page), NOT in sense blocks. The TRUE POS section boundary is `pos-g` followed by `<ol class="senses_multiple">` or `<ol class="sense_single">` as next sibling (anhe pattern (b) from Phase 7 grill).
- Word-level CEFR badge: `<span class="ox3ksym_c1">` (Oxford 3000) or `<span class="ox5ksym_c1">` (Oxford 5000) at top of page. Distinct from per-sense `def.cefr`. Extracted via regex on class name → field `oxford_badge` in schema v2.
- See `docs/adr/0001-lxml-parser-backend.md` for the lxml-vs-BS4 decision and `docs/adr/0002-multi-pos-merge-bug.md` for the pos-g pitfall.

### Oxford "phrasal verb hub" pages (learned 2026-06-19) — missing def trap
**Pattern:** Some Oxford entry pages contain **zero direct definitions** — they're redirect hubs that just list phrasal verb / phrase sub-pages. Example: `oxford_consist_(verb).html` body is literally:
```
Phrasal Verbs
  consist in   <-- links to /definition/english/consist-in
  consist of   <-- links to /definition/english/consist-of
See consist in the Oxford Advanced American Dictionary
```
No `<... class="def">` tags anywhere. Current parser (`src/scraper/oxford.py`) does NOT recurse into those phrase sub-pages, so the result is `definitions[0].text = null` (or empty string) for the entire entry.

**Diagnostic recipe** when a (word, pos) has 0 defs but Oxford has the page:
1. Open `data/.cache_html/oxford/oxford_<word>_(<pos-token>).html` (`pos-token` uses `_` for spaces/composite POS labels)
2. Search for `class="def"` — if 0 hits, it's a hub
3. Search for `Phrasal Verbs` or `Phrases` section — list of related sub-pages
4. Manually patch `data/sources/oxford.jsonl` for that entry, OR fix parser to recurse

**Known affected words** (verb, from 2026-06-19 audit): `consist` (only 1/5,318 — rare). If a word you care about shows 0 defs, check this pattern first before suspecting cache pollution or fold bug.

**Build-pipeline mitigation:** `tools/build_notes.py` now uses canonical registry/manual inputs and fail-closed validation. Do not rely on generated TXT as a source of truth when source JSONL is null; fix the parser or add canonical manual payload instead.

### Oxford rebuild determinism contract (learned 2026-06-13)
**Rebuilding `data/sources/oxford.jsonl` MUST be byte-identical across runs** (same input cache → same output JSONL). Verified by SHA-256 comparison of two consecutive `python -m tools._run_full_cache --oxford-only` invocations.

The contract is enforced at `tools/_run_full_cache.py:127`:
```python
records.sort(key=lambda r: (
    r.get("word") or "",
    (r.get("source_files") or [""])[0],
))
```

**Why this matters:** the merge layer (`src/scraper/merge.py`) uses "first non-null" logic for `oxford_badge`, `audio`, `idioms`, `see_also`. Multi-file words (e.g. `transport` has `(verb)` + `(noun)` homonym pages) have multiple records; the FIRST one in iteration order becomes the "primary" homonym for those display fields. Without the `(word, source_files[0])` composite sort key, `as_completed()` race order from the parallel parser leaks through and the "first" record varies across runs.

**If you change anything in the rebuild path** (`_run_full_cache.py`, `merge.py`, fold phrasal verb), verify determinism by running the rebuild twice and `Get-FileHash ... -Algorithm SHA256` comparing the outputs. If they differ, you've introduced non-determinism — fix it before committing.

See `docs/adr/0003-colloc-artifact-filter.md` § Determinism fix for full context.

### EAVM note type
The Anki note type `English Academic Vocabulary Model` is generated from
`design/EAVM/{front,back}_template.txt` + `styling.txt`. Do **not** hand-edit
fields inside Anki — edit the templates and re-run the packager. See
`design/EAVM/README.md § Lưu ý quan trọng khi chỉnh sửa JavaScript` for the
literal-newline gotcha in template JS.

The EAVM model keeps one canonical note/Card Registry identity and now emits
two sibling cards: ordinal 0 `Recognition` and ordinal 1
`Production (VI -> EN)`. The Production card is generated only when
`DefinitionVI`, `Example`, and the appended `ProductionAnswer` are populated;
it uses native `{{type:ProductionAnswer}}` comparison. `ProductionAnswer` is
field 23 (zero-based index 22), after the established 22 fields, and is
derived from the final displayed `Word` by removing only a trailing display
qualifier. Preserve learning-pattern slots such as `devote sth to sth`.
Production migration is performed by the dedicated AnkiConnect import stage;
never create a second EAVM Note Type or remove/re-add the established
template.

The established first 15 fields and model ID `1607392819` are immutable. New
fields must be appended. Example Audio uses `ExampleAudioUK`, `ExampleAudioUS`,
`IdiomExampleAudioUK`, and `IdiomExampleAudioUS` after `Antonyms`.
`DefinitionVI` follows those four fields. It is pipe-aligned with `Definition`
and drives the always-visible Vietnamese Gloss Line; the established
`Definition` field retains its legacy `EN (VI)` payload for compatibility.
`IdiomMeaningVI` is appended after `SensePOS`. It is `$$`-aligned with the
established `Idioms` field; each populated cell carries the reviewed Idiom
Display Mode and Vietnamese text. Never change the existing `Idioms` or Idiom
Example Audio delimiter grammar.
`CollocationSources` is appended after `IdiomMeaningVI` (field 26, zero-based
index 25) and is pipe-aligned with `Collocations`. Its tokens are `oxford`,
`cambridge`, `oxford+cambridge`, and `curated`. Missing or invalid legacy
metadata must render all collocation chips neutrally rather than infer a source.

### Anki package import workflow

The pipeline's `import` stage is the supported live update path. It calls
AnkiConnect `importPackage` with the generated `.apkg`, then verifies the note
type fields, canonical GUID coverage, and referenced media. GUID coverage is
proved from a post-import AnkiConnect APKG export because `notesInfo` does not
return GUIDs; never treat a missing `notesInfo.guid` field as success. Every successful
non-dry-run workflow containing `deck` automatically continues into `import`;
`python -m src.pipeline import` remains available for a standalone re-import.
Anki and AnkiConnect must be running, and the workflow must fail visibly if the
import or post-import verification fails. Never edit `collection.anki2`
directly.

Packaging writes `scratch/release/ielts_deck.provenance.json`, binding the
`.apkg`, packaged media set, build JSONL/TXT, Card Registry, Semantic Registry,
all semantic review/policy ledgers, all Recognition/Production template inputs,
EAVM styling, `design/index.html`, the machine-readable EAVM packager contract,
the packager implementation, and the installed `genanki` version. Repackaging
invalidates any previous verified-import receipt. Both packaging and import run
the canonical release guard before crossing their release boundary; import then
validates package provenance before contacting Anki and writes
`scratch/release/ielts_deck.verified-import.json` only after the live
post-import checks succeed.

Run the read-only release boundary that matches the work:

- `python -m tools.release_guard canonical` — reproduce Semantic Registry and
  both build projections from current canonical inputs without writing them.
- `python -m tools.release_guard package` — validate design sync, current local
  inputs/media, the `.apkg` archive's exact SQLite/model/note/card/media
  contents, and its provenance sidecar.
- `python -m tools.release_guard import` — run the package checks and require a
  verified-import receipt for that exact package and expected note count.

The live import verifier compares the bytes of every referenced Anki media file
with the tracked source, overwrites a same-name stale file before independently
verifying it again, and requires every newly created Recognition and Production
card to be pristine. It then exports the root deck, prefers
`collection.anki21` over the compatibility `collection.anki2`, rejects
unsupported `collection.anki21b`, and checks the exact GUID-to-identity/card
map before writing the receipt. Matching filenames or note counts are not
sufficient, and GUID text is not considered verified until the export proof
succeeds.

The guard never promotes, builds, packages, contacts Anki, or fixes state. CI
runs the canonical scope on Linux and Windows, and builds then checks package
provenance on Linux; the import scope remains a live-release check because CI
has no Anki collection.

### Anki deletion/update workflow
When deleting or merging notes in the local Anki app, use AnkiConnect if
available. Do not edit `collection.anki2` directly.

Required workflow:
1. Query and verify the exact target note/card by `nid`, GUID, word, POS, and CEFR.
2. Add tag `delete` to the note that will be removed.
3. Export the affected deck to `scratch/` as the pre-delete audit artifact.
4. Delete through AnkiConnect (`deleteNotes`).
5. Verify the deleted `nid` no longer resolves, `tag:delete` is clear for that target, and the kept note/card is correct.
6. Export the affected deck again to `scratch/` as the post-delete artifact.
7. Sync repo/pipeline so the deleted card is not rebuilt or re-imported.

Do not require manual deletion in the Anki UI when AnkiConnect is available.
Do not delete without a delete-tag audit/export first.

### Design system sync
`design/index.html` (vùng 2) is the **source of truth** for the card CSS.
`design/EAVM/styling.txt` is auto-baked into `.apkg` and **must** stay in sync
with `index.html`. Enforce via:

- `python -m tools.check_design_sync` — CLI, exit 0/1
- `pytest tests/design/` — pytest version, share core parser

Selector class names in `index.html` are **immutable contracts** — renaming
breaks every template that references them. To mark a rule as preview-only
(don't sync to `.apkg`), add `/* @preview-only */` on its own line immediately
before the rule. See `design/README.md` for the full workflow.

### Card design rules
Three hard rules enforced in the reviewed semantic/build path that turns raw
notes into Anki-ready rows. The scraper keeps all senses / all CEFR entries.

1. **Learner Relevance Filter**: the Bilingual Semantic Audit may explicitly
   remove a narrowly specialist or marginal sense when a useful learner meaning
   remains. Source labels only create review candidates; they never trigger an
   automatic deletion. Every affected source sense must be remapped or excluded
   with a reason, and the card may not become empty.
2. **Sense Sorting** (replaces the legacy Sense Cap, removed 2026-06-21):
   all remaining learner-relevant CEFR-matching definitions are retained. Senses are ordered
   by `sensenum_local` (ascending, Oxford's frequency proxy), then by example
   count (descending) as tie-breaker. **No per-card def limit** — every sense
   in the reviewed production payload is kept.
3. **Card Identity**: 1 CEFR level = 1 card by default. Multi-POS words (e.g.
   `absent` = adjective/verb/preposition) live in a single card per CEFR, with
   all POS chips listed in the top-bar. Same word with different CEFR levels
   produces multiple cards. Reviewed identity variants currently cover the
   `converse|UNCLASSIFIED` homonyms plus the reviewed noun/verb split for
   `trail|C1`; `torture|C1` is a reviewed POS merge and is not a precedent for
   new splits. See `CONTEXT.md`.

See `design/README.md § Card design rules` for the full rationale.

### Sense Sorting & Card Identity gotcha (learned 2026-06-13, refactored 2026-06-21)
**Original lesson:** misreading "max 3 definitions per card" as "excess senses
get split into multiple cards of ≤3 each" (i.e. "pagination") produced a
false-positive audit claiming 99.6% of `(word, CEFR)` duplicates were legitimate
pagination. **WRONG.** Both the legacy Sense Cap and the current Sense Sorting
**never paginate**. The reviewed Learner Relevance Filter may explicitly remove
a niche sense, but Sense Sorting itself only orders and retains its input.
All 490 observed duplicates were bugs that needed dedup.

**Post-2026-06-21 reminder:** the cap was removed, but the "no pagination"
invariant is unchanged. Sense Sorting never splits senses into multiple cards.

**How to avoid this:**
- When a CONTEXT.md rule could be interpreted two ways, verify against the
  **actual upstream source** (Oxford HTML page, Cambridge page, etc.) before
  drawing conclusions from the data.
- Sense Sorting's worked example is in CONTEXT.md § Sense Sorting — read it
  FIRST before writing audit scripts that look for "pagination patterns".
- Card Identity is strict: **exactly one** card per identity unless the key is
  an explicitly documented reviewed identity variant. Unreviewed duplicates
  are bugs.

### Data freshness
`vocab_list/` is the seed. The scraper re-validates against live pages to catch
new examples, IPA changes, and CEFR re-classifications.

### Scraper cache isolation (DO NOT break)
Each source's fetcher must use a **distinct cache filename prefix** so they
don't silently collide. Wired in `src/scraper/fetch.py` via
`HttpFetcher.cache_prefix` (default `""`):

- Oxford: `cache_prefix=""` → writes `<word>.html`
- Cambridge: `cache_prefix="cambridge_"` → writes `cambridge_<word>.html`

**Why this matters:** a 2026-06-08 audit found the entire Oxford cache
(13,208 files) had been silently overwritten with Cambridge content because
both sources used `<word>.html`. The 32 records that had `cambridge_cefr`
fill from the legacy `_fetch_cambridge_cefr.py` were the visible symptom
(`oxford_full.jsonl` reported CEFR like C2 for "ambiguous" where live Oxford
has none). Fix landed in commit that introduced `cache_prefix`; new fetchers
must follow the same pattern.

**Diagnostic recipe when in doubt:** sample 50 random words from the file
and compare recorded `cefr` against live `<source URL>` for each. If
mismatches cluster on a specific source, suspect cache pollution.

## Security

- Never commit scraped HTML that contains user data (current sources are public dictionaries — fine)
- `.cache_html/`, `*.apkg`, `data/*.bak` are gitignored — keep it that way
- Any paid-service API keys go in `.env` (gitignored), never in code
