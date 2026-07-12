# Tools Directory

`tools/` contains maintained command-line adapters, verifiers, and inspectors
used by the current scraper/build/design pipeline.

Filename convention: a leading underscore means a maintained internal command
or release verifier. One-shot phase commands do not remain executable in
`HEAD` after their outputs become canonical.

## Supported CLI

These are maintained entry points for current workflows:

- Build / pipeline: `build_notes.py`, `_run_full_cache.py`, `_validate_jsonl.py`
- Registry / corpus sync: `sync_card_registry.py`, `check_corpus_tags.py`,
  `check_sense_labels.py`, `sync_cambridge_pos_audio.py`
- Integrity gates: `check_audio_gate.py`, `check_awl_integrity.py`,
  `check_deck_cefr.py`, `check_def_before_integrity.py`,
  `check_design_sync.py`
- Release verifiers: `_check_determinism.py`, `_verify_deck_output_p3b.py`
- Review utilities with current data contracts: `import_non_oxford_review.py`,
  `tag_duplicates_for_deletion.py`

## Private / Inspector Tools

These remain in the active workspace because current tests or workflows use
them, but they are not default release gates:

- Parser/CI helpers: `benchmark_parser.py`, `ci_hydrate_parser_fixtures.py`
- Review inspector: `_detect_lexical_loops.py`

Leading-underscore tools are private or specialized, but not automatically
obsolete. If a private tool is imported by tests, called by another maintained
tool, or referenced by current documentation, keep it here.

## Retired One-Shot Commands

One-shot migrations are removed once their payloads live in canonical
`data/curated/` or `data/review/` inputs and current-state regression tests cover
the result. Git history is the audit source for retired executable code; do not
restore an old command and run it against production data without revalidating
its assumptions.

Current registry-driven build flow:

- `python -m tools.sync_card_registry --check`
- `python -m tools.build_notes --dry-run`
- `python -m src.pipeline validate`
- `python -m tools._verify_deck_output_p3b`

When cleaning this directory:

1. Search for references from `src/`, `tests/`, `docs/`, `AGENTS.md`,
   `CONTEXT.md`, and `data/README.md`.
2. Move durable behavior into maintained source or canonical data first.
3. Delete the retired command and replace migration tests with current-state
   regressions.
4. Keep public CLI adapters and current verifier modules at top level, then run
   focused and full tests.
