# Tools Directory

`tools/` contains maintained command-line adapters, verifiers, and inspectors
used by the current scraper/build/design pipeline.

## Current Top-Level Tools

Top-level files are intentionally still part of the active workspace. They fall
into three groups:

- Pipeline adapters: `_run_full_cache.py`, `build_notes.py`, `_validate_jsonl.py`
- Canonical registry/build tools: `sync_card_registry.py`, `build_notes.py`, `check_sense_labels.py`
- Active checks/verifiers: `check_*.py`, `_verify_*.py`, `_check_*.py`
- Maintained inspectors or review helpers referenced by tests, docs, or source:
  `_audit_gloss_policy_coverage.py`, `_detect_lexical_loops.py`,
  `_fix_oxford_def_fields.py`, `_full_audit.py`, `_m3_rerun_v2.py`,
  `_merge_expanded_glosses.py`, `download_duden_a1_audio.py`,
  `sync_cambridge_pos_audio.py`,
  `tag_duplicates_for_deletion.py`

Leading-underscore tools are private or specialized, but not automatically
obsolete. If a private tool is imported by tests, called by another maintained
tool, or referenced by current documentation, keep it here.

## Archive

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
