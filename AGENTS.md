# AGENTS.md

IELTS / Academic English Anki deck builder — notes DB + scraper pipeline (Oxford / Cambridge + AWL + Oxford audio).

> **Read first:** [`CONTEXT.md`](./CONTEXT.md) for the project glossary (canonical terms, no implementation details). Come back here for commands, layout, and conventions.

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
- `audio/` — generated audio files (UK/US per word)
- `design/` — Anki card visual design system. **`design/index.html` (vùng 2 card CSS) is the source of truth** — `EAVM/styling.txt` derives from it and is baked into `.apkg`. `tools/check_design_sync.py` enforces the sync.
- `docs/adr/` — Architecture Decision Records. One file per decision, named `NNNN-title.md` (e.g. `0001-lxml-parser-backend.md`). Add a new ADR whenever a decision meets all 3 criteria: hard to reverse, surprising without context, and a real trade-off.
- `vocab_list/` — source word lists (Oxford 3000/5000 markdown, AWL json/yml)
- `update_anki_deck.py` — top-level packager (`data/build/anki_notes.jsonl` → `ielts_deck.apkg`). Owned by `developer` rein.
- `src/pipeline.py` — production-stage orchestrator: `scrape → build → validate → deck`. Run with `python -m src.pipeline`. Supports `--from=<stage>`, `--to=<stage>`, `--dry-run`, single-stage (`python -m src.pipeline build`).
  - **scrape**: Oxford/Cambridge + AWL ingestion, audio. Keeps all senses / all CEFR entries (raw).
  - **build**: enriches with CEFR resolution + audio refs. **Enforces [Card Identity](./CONTEXT.md) and [Sense Sorting](./CONTEXT.md)** — splits by CEFR, retains all CEFR-matching senses (no per-card def cap), orders by sensenum_local asc. See `design/README.md § Card design rules` for the rule reference.
  - **validate**: checks registry, card identity, JSONL/TXT parity, audio references, and deterministic output before publish.
  - **deck**: bakes `.apkg` via `update_anki_deck.py`.
  - Archived one-shot fixers are unsupported and are not wrapped by the pipeline.

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
  `gpt-5.6-terra` with `model_reasoning_effort = "medium"`. Treat
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

- Smoke: `pytest tests/test_config.py tests/test_pipeline.py tests/test_schema_validation.py tests/test_drift_guard.py tests/tools/test_sync_card_registry.py`
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
Two hard rules enforced at the **build stage** (the stage that turns raw notes
into Anki-ready rows). The scraper is allowed to keep all senses / all CEFR
entries — filtering happens at build, not at scrape.

1. **Sense Sorting** (replaces the legacy Sense Cap, removed 2026-06-21):
   all CEFR-matching definitions are retained on the card. Senses are ordered
   by `sensenum_local` (ascending, Oxford's frequency proxy), then by example
   count (descending) as tie-breaker. **No per-card def limit** — every sense
   the (word, CEFR) group carries is kept.
2. **Card Identity**: 1 CEFR level = 1 card by default. Multi-POS words (e.g.
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
**never paginate** — senses are either dropped (legacy) or all retained (current).
All 490 observed duplicates were bugs that needed dedup.

**Post-2026-06-21 reminder:** the cap was removed, but the "no pagination"
invariant is unchanged. Sense Sorting adds senses but never splits them into
multiple cards.

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
