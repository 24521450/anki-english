# Tools Directory

`tools/` contains maintained command-line adapters, verifiers, and inspectors
used by the current scraper/build/design pipeline.

Filename convention: a leading underscore means internal helper, inspector, or
specialized workflow. It does not automatically mean obsolete. Conversely, a
non-underscore file is not always a public release gate; check the taxonomy
below before automating it.

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

These remain in the active workspace because they are referenced by tests, docs,
or current investigation workflows, but they are not default release gates:

- Parser/CI helpers: `benchmark_parser.py`, `ci_hydrate_parser_fixtures.py`
- Phase-specific applicators: `_apply_*.py`
- Phase-specific verifiers: `_verify_p*.py`
- Inspectors/audits: `_audit_gloss_policy_coverage.py`,
  `_check_gloss_hygiene.py`, `_detect_lexical_loops.py`,
  `_fix_oxford_def_fields.py`, `_full_audit.py`, `_inspect_phrasal_files.py`,
  `_m3_rerun_v2.py`, `_merge_expanded_glosses.py`

Leading-underscore tools are private or specialized, but not automatically
obsolete. If a private tool is imported by tests, called by another maintained
tool, or referenced by current documentation, keep it here.

## Archived / Unsupported

Unsupported one-shot migrations live under `tools/archive/data_migrations/`.
Those files are preserved for audit history only. Do not run them against
current production data unless you first revalidate their assumptions.

Current registry-driven build flow:

- `python -m tools.sync_card_registry --check`
- `python -m tools.build_notes --dry-run`
- `python -m src.pipeline validate`
- `python -m tools._verify_deck_output_p3b`

When cleaning this directory:

1. Search for references from `src/`, `tests/`, `docs/`, `AGENTS.md`,
   `CONTEXT.md`, and `data/README.md`.
2. Move only unreferenced one-shot scripts to `tools/archive/data_migrations/`.
3. Keep public CLI adapters and current verifier modules at top level.
4. Run focused tests after moving anything.
