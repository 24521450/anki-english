# Tools Directory

`tools/` contains maintained command-line adapters, verifiers, and inspectors
used by the current scraper/build/design pipeline.

Filename convention: a leading underscore means a maintained internal command
or release verifier. One-shot phase commands do not remain executable in
`HEAD` after their outputs become canonical.

## Supported CLI

These are maintained entry points for current workflows:

- Build / pipeline: `build_notes.py`, `_run_full_cache.py`, `_validate_jsonl.py`
- Semantic review and promotion: `semantic_audit.py`, `idiom_audit.py`
- Registry / corpus sync: `sync_card_registry.py`, `check_corpus_tags.py`,
  `check_sense_labels.py`, `sync_cambridge_pos_audio.py`
- Integrity gates: `check_audio_gate.py`, `check_awl_integrity.py`,
  `check_deck_cefr.py`, `check_def_before_integrity.py`,
  `check_design_sync.py`
- Release verifiers: `release_guard.py`, `_check_determinism.py`,
  `_verify_deck_output_p3b.py`
- Clean-checkout CI fixture hydration: `ci_hydrate_parser_fixtures.py`
- Review utilities with current data contracts: `import_non_oxford_review.py`,
  `tag_duplicates_for_deletion.py`

### Semantic workflow

```bash
python -m tools.semantic_audit scaffold
python -m tools.semantic_audit export-xlsx
python -m tools.semantic_audit import-xlsx
python -m tools.idiom_audit scaffold
python -m tools.idiom_audit export-xlsx
python -m tools.idiom_audit import-xlsx
python -m tools.semantic_audit vietnamese-review-scaffold --scope all --replace
python -m tools.semantic_audit definition-review-scaffold --replace
python -m tools.semantic_audit sense-merge-review-scaffold --replace
python -m tools.semantic_audit validate --require-complete
python -m tools.idiom_audit validate --require-complete
python -m tools.semantic_audit promote
```

`definition-audit`, `vietnamese-audit`, and `sense-merge-audit` write report-only
triage views in `scratch/`; their length, connector, overlap, and wording-shape
signals never authorize an automatic rewrite, deletion, split, or merge. The
three `*-review-scaffold` commands above write the canonical fingerprint-bound
promotion ledgers. Definition promotion candidates require approved
row-specific concision evidence. Remaining Sense Merge candidates require an
approved `keep_separate` distinction that cites at least two Semantic Sense IDs;
apply an actual merge/reword bundle to the Bilingual Semantic Audit and refresh
the scaffold instead of approving an unapplied proposal.

Every resolved all-sense Vietnamese row requires a decision-specific
`reason_code` and unique, wording-specific `semantic_evidence`; a `user_lock`
row also requires its exact `lock_id`. Ordinary evidence cites the exact EN
sense and one sense-specific example or source definition. A shared sentence
does not become row-specific merely because it interpolates the headword or
final VI; generic and duplicate normalized templates fail the gate. The four exact user locks are `compel` →
`ép buộc`, `contender` → `đối thủ nặng ký`, `transcribe` → `chép lại`, and
`venture` → `mạo hiểm, cả gan`; changing one requires an explicit user
instruction and coordinated code/data update. Reports and XLSX files never
become production authority merely because a reviewer opened or edited them.

### Release workflow

```bash
# Reproduce current promoted/build state without writes.
python -m tools.release_guard canonical

# After packaging, verify the APKG and its provenance sidecar.
python -m tools.release_guard package

# After a live AnkiConnect import, verify its bound receipt.
python -m tools.release_guard import
```

The release guard is read-only: it does not promote, build, package, contact
Anki, or repair files. Package provenance binds the `.apkg` and media set to
both build projections, Card Registry, Semantic Registry, every semantic
review/policy ledger, all Recognition/Production template inputs, EAVM styling,
`design/index.html`, the packager implementation, and the machine-readable EAVM
model/field/card contract plus `genanki` version. Packaging and import first run
the canonical guard, so mutually inconsistent authorities cannot be hidden by a
freshly rewritten provenance sidecar. Package scope also opens the archive and
checks its exact ZIP inventory, media bytes, SQLite integrity, EAVM model,
notes, generated card ordinals, decks, and pristine card state. A successful
live import additionally repairs same-name stale media, hashes every retrieved
Anki media file, verifies new Recognition/Production cards are pristine, and
exports the live deck to prove the SQLite GUID-to-identity/card map. The receipt
binds the exact provenance/package digest, verified note count, export archive
digest, and canonical GUID-map digest; repackaging invalidates the old receipt.

CI runs `canonical` on Linux and Windows, then builds and checks `package`
provenance on Linux. `import` is a local live-release boundary because CI has no
Anki collection.

## Private / Inspector Tools

These remain in the active workspace because current tests or workflows use
them, but they are not default release gates:

- Parser inspector: `benchmark_parser.py`
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
