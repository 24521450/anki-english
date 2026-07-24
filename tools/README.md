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
  `sync_pronunciation_audio.py`, `sync_cambridge_english_vietnamese.py`
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

### Cambridge English–Vietnamese source snapshot

```bash
# Inspect normalized lookup coverage without network or filesystem writes.
python -m tools.sync_cambridge_english_vietnamese plan

# Populate only the isolated ignored cache, then atomically publish the snapshot.
python -m tools.sync_cambridge_english_vietnamese fetch
python -m tools.sync_cambridge_english_vietnamese build --apply

# Read-only canonical and schema checks.
python -m tools.sync_cambridge_english_vietnamese build --check
python -m tools.sync_cambridge_english_vietnamese validate
```

The plan groups active Card Registry requests by normalized lookup headword.
It uses only the reviewed aliases declared in the parser module and the
mandatory `provisions` supplemental request; it performs no stemming or
lemmatization. Each found or positively confirmed `no_entry` lookup produces
one deterministic row with sorted coverage requests. Missing sense
translations remain `translation_status: missing`; transient HTTP failures,
challenge pages, and unrecognized parser shapes fail the command and never
become absence evidence.

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
python -m tools.collocation_audit apply-review \
  --input scratch/collocation_review_part_001.jsonl
python -m tools.collocation_audit validate --require-complete
python -m tools.collocation_audit report
python -m tools.collocation_audit promote
python -m tools.semantic_audit vietnamese-review-scaffold --scope all --replace
python -m tools.semantic_audit definition-review-scaffold --scope all --replace
python -m tools.semantic_audit sense-merge-review-scaffold --replace
python -m tools.semantic_audit validate --require-complete
python -m tools.idiom_audit validate --require-complete
python -m tools.semantic_audit promote
```

`idiom_audit scaffold` builds its default input from the canonical
pre-Semantic-Registry source projection. This preserves exact Oxford/Cambridge
source explanations and prevents a previously promoted learner gloss from
becoming a new source fingerprint. Pass `--notes <path>` only when an explicit
card projection is required for a fixture or a controlled migration.

`apply-review` consumes a complete row bundle produced from the same scaffold.
It checks each row's immutable `input_fingerprint`, source evidence, current
items, and mandatory candidates, then validates the live projection before an
atomic write. Use it for parallel JSONL review patches; stale or partially
edited rows are rejected. When a promoted-note projection is used as the
scaffold input, unchanged rows may reuse only exact reviewed final text and
provenance; source-ID-only churn is migrated by stable evidence keys, while
new or changed evidence/candidates remains pending for explicit review.

Definition Concision Review defaults to `--scope all` and must cover every
promoted Definition-bearing Semantic Sense before promotion. Use `--scope long`
only for threshold-based triage; that narrower ledger cannot pass promotion.
Already-short wording closes with an approved `keep_concise` decision and
row-specific semantic evidence. `keep_explanatory` still requires a genuinely
shorter alternative plus the exact material distinction it would lose.

Large canonical review ledgers can be handled as deterministic batches of at
most 100 unresolved rows. Every manifest repeats the canonical review summary,
so it remains fingerprint-bound and can be applied as a partial patch:

```bash
# Definition Concision Review batches.
python -m tools.semantic_audit definition-review-create-manifests
python -m tools.semantic_audit apply-definition-review \
  --input scratch/definition_review_manifests/manifest_001.jsonl --dry-run
python -m tools.semantic_audit apply-definition-review \
  --input scratch/definition_review_manifests/manifest_001.jsonl

# Vietnamese Naturalness Review batches (ledger only; does not change Bilingual Audit).
python -m tools.semantic_audit vietnamese-review-create-manifests
python -m tools.semantic_audit apply-vietnamese-review-patch \
  --input scratch/vietnamese_review_manifests/manifest_001.jsonl --dry-run
python -m tools.semantic_audit apply-vietnamese-review-patch \
  --input scratch/vietnamese_review_manifests/manifest_001.jsonl
```

Use `--max-rows N` to choose a smaller batch (`1 <= N <= 100`) and `--replace`
to reproduce an existing manifest directory. Rows for one GUID stay in the
same manifest unless that GUID alone exceeds the selected limit. Creation
rejects a stale or invalid canonical candidate set. Patch application rejects a changed summary,
unknown or duplicate candidates, stale fingerprints, and edits to immutable
context fields; a patch outside the same 1–100-row limit is also rejected. It
validates the complete current candidate universe before atomically updating
the canonical review ledger. The Vietnamese patch command
intentionally leaves `data/review/bilingual_semantic_audit.jsonl` unchanged.
After every Vietnamese batch is resolved, run the existing
`apply-vietnamese-review` workflow to enforce completeness and apply approved
rewrites to the Bilingual Semantic Audit.

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
final VI; generic and duplicate normalized templates fail the gate. The five
exact user locks are `compel` → `ép buộc`, `contender` → `đối thủ nặng ký`,
`contend with sb/sth` → `đối phó`, `transcribe` → `chép lại`, and `venture` →
`mạo hiểm, cả gan`; changing one requires an explicit user instruction and
coordinated code/data update. Reports and XLSX files never become production
authority merely because a reviewer opened or edited them.

### Collocation workflow

The Collocation Audit is two-way: it accounts for every current displayed chip
and every mandatory Oxford/Cambridge candidate. Audit v3 includes
example-linked evidence, Cambridge bare `.lu`/standalone `.cl`, and
non-truncated Oxford snippets containing the headword or regular plural. Other
supporting evidence remains visible but does not become production content
automatically. Every item needs an explicit
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

After `scaffold`, use `create-manifests` to partition unresolved work by whole
GUID across exactly three deterministic workers; `validate-manifests` rejects
stale or modified assignments. A v2 ledger is deliberately reset to pending,
and complete validation rejects review reasons that differ only by interpolated
surface/evidence identifiers.

### Phrasal-verb routing workflow

`python -m tools.phrasal_verb_audit scaffold` reconstructs the
fingerprint-bound routing queue from active Card Registry identities, parent
`phrasal_verb_links`, and independently hydrated Oxford target records.
`export-xlsx` and `import-xlsx`
provide a protected review view; immutable target URLs, source identities,
structural collisions, and fingerprints cannot be edited there.
`validate --require-complete` rejects pending, uncertain, stale, unapproved, or
structurally inconsistent routes. An approved `distinct_secondary` route also
forbids the routed phrase from remaining as a final chip on its parent card.
The review ledger is the routing authorization; the XLSX file and scraper data
are evidence, not production authorities.

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
