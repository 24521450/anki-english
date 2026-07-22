# Tools Directory

`tools/` contains maintained command-line adapters, verifiers, and inspectors
used by the current scraper/build/design pipeline.

Filename convention: a leading underscore means a maintained internal command
or release verifier. One-shot phase commands do not remain executable in
`HEAD` after their outputs become canonical.

## Supported CLI

These are maintained entry points for current workflows:

- Build / pipeline: `build_notes.py`, `_run_full_cache.py`, `_validate_jsonl.py`
- Semantic/collocation review and promotion: `semantic_audit.py`,
  `idiom_audit.py`, `collocation_audit.py`
- Registry / corpus sync: `sync_card_registry.py`, `check_corpus_tags.py`,
  `check_sense_labels.py`, `sync_cambridge_pos_audio.py`,
  `sync_pronunciation_audio.py`
- Integrity gates: `check_audio_gate.py`, `check_awl_integrity.py`,
  `check_deck_cefr.py`, `check_def_before_integrity.py`,
  `check_design_sync.py`, `check_oxford_opal.py`
- Release verifiers: `release_guard.py`, `_check_determinism.py`,
  `_verify_deck_output_p3b.py`
- Clean-checkout CI fixture hydration: `ci_hydrate_parser_fixtures.py`
- Review utilities with current data contracts: `import_non_oxford_review.py`,
  `tag_duplicates_for_deletion.py`, `card_identity_split.py`

### Oxford source integrity

```bash
python -m tools._run_full_cache --oxford-only
python -m tools._validate_jsonl
python -m tools.check_oxford_opal
python -m tools._check_determinism --build
```

`check_oxford_opal` independently compares raw headword OPAL markers in every
referenced cache page with the POS-scoped metadata in `sources/oxford.jsonl`.
It fails on missing cache files, missing/extra/mismatched membership, or an
OPAL-labelled page not accounted for by the JSONL. The ignored cache is not
available in clean CI, so this full-cache guard is run after local rebuilds.

### Headword pronunciation workflow

```bash
# Read-only exact entry-scoped selection/download plan.
python -m tools.sync_pronunciation_audio

# Download missing selected media transactionally and write the byte manifest.
python -m tools.sync_pronunciation_audio --apply
```

The resolver consumes source schema v3 `pronunciations`, keeps each accent's IPA
and audio URL from one entry, and ranks Cambridge before Oxford followed by
dictionary/headword/POS specificity. Ambiguous, explicitly aliased, and absent
requests are bound by `curated/pronunciation_selection_locks.jsonl`; an implicit
lemma or an existing filename never selects a candidate. The generated
`sources/headword_audio_manifest.jsonl` binds each selection fingerprint to its
full entry identity and media fingerprint as well as URL, IPA, filename, byte
count, and SHA-256. Entry-only source drift safely reuses an existing file only
when the media fingerprint and byte attestation remain exact; production also
rejects manifest rows outside the active selection set. Use `--attest-existing`
only for a reviewed migration and `--resume-staging` only with the staging
directory produced by the same current plan.

### Semantic and collocation workflows

```bash
python -m tools.semantic_audit scaffold
python -m tools.semantic_audit export-xlsx
python -m tools.semantic_audit import-xlsx
python -m tools.idiom_audit scaffold
python -m tools.idiom_audit export-xlsx
python -m tools.idiom_audit import-xlsx
python -m tools.collocation_audit scaffold
python -m tools.collocation_audit export-xlsx
python -m tools.collocation_audit import-xlsx
python -m tools.collocation_audit validate --require-complete
python -m tools.collocation_audit report
python -m tools.collocation_audit promote
python -m tools.semantic_audit vietnamese-review-scaffold --scope all --replace
python -m tools.semantic_audit definition-review-scaffold --replace
python -m tools.semantic_audit sense-merge-review-scaffold --replace
python -m tools.semantic_audit validate --require-complete
python -m tools.idiom_audit validate --require-complete
python -m tools.semantic_audit promote
```

An identity split is a separate reviewed transaction, not a semantic scaffold
side effect:

```bash
python -m tools.card_identity_split apply-review --input scratch/<bundle>.jsonl --dry-run
python -m tools.card_identity_split apply-review --input scratch/<bundle>.jsonl
```

The bundle must bind current source/card fingerprints and fully define the
primary/secondary variants, sense/source partition, collocations, idioms, new
GUID, and secondary deck. The command publishes Card Registry and Bilingual
Semantic Audit through a durable journal with old-value backups and emits a
scratch projection. An ordinary failure rolls back immediately; the next
non-dry-run invocation recovers a hard-interrupted transaction before reading
the authorities. Re-run dry-run after success to prove idempotency, then
regenerate every canonical review queue and downstream registry/build artifact.

On Windows PowerShell 5.1, keep review payloads in the UTF-8 files consumed by
these commands; do not pipe Vietnamese text to a native process with the
default ASCII `$OutputEncoding`. If a pipe is unavoidable, set both encodings
first:

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding
```

The Idiom Audit rejects replacement-like `?` characters and `U+FFFD` in
editable review text, while allowing legitimate terminal question marks.

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

### Collocation workflow

The Collocation Audit is two-way: it accounts for every current displayed chip
and every mandatory example-linked Oxford/Cambridge candidate. Supporting
snippet, bare-label, and grammar evidence remains visible to the reviewer but
does not become production content automatically. Every item needs an explicit
approved disposition with a surface-specific reason (and source evidence IDs
when the decision is source-backed); pending, uncertain, stale, unaccounted,
over-five, or invalid source-compressed results fail promotion. `promote` writes
the Collocation Registry deterministically; neither the XLSX view nor scraper
output is a production authority. After promotion, the release guard accepts
the exact registry projection in built notes as the expected post-promotion
state; a different text/source projection or a changed source/idiom input still
fails freshness.

Evidence matching is exact-surface first. Only if no exact row exists may a
regular singular/plural change of the card headword match (for example,
`generous portion` backed by `generous portions`). Provenance remains per final
chip; do not slash-compress a source-backed phrase together with a curated
phrase or let the curated half suppress its OXF/CAM marker.

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
both build projections, Card Registry, Semantic Registry, Collocation Registry,
every semantic/collocation review and policy ledger, all Recognition/Production
template inputs, EAVM styling,
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
