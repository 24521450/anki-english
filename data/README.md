# `data/` artifact layout

This directory stores tracked datasets by lifecycle. Runtime code obtains every
canonical path from `src.config.ProjectPaths`; this file owns each artifact's
authority, writer, and edit policy.

## Artifact ownership

| Path | Authority / role | Canonical writer | Manual edits? |
| --- | --- | --- | --- |
| `sources/oxford.jsonl` | Canonical Oxford parser output; raw senses remain auditable. | `python -m tools._run_full_cache` | No; fix parser/cache inputs or use an explicitly reviewed source repair. |
| `sources/cambridge.jsonl` | Canonical Cambridge parser output. | `python -m tools._run_full_cache` | No. |
| `curated/card_registry.jsonl` | Canonical card identity, GUID, status, and routing inventory. | `python -m tools.sync_card_registry` | No. |
| `curated/semantic_policy_locks.jsonl` | Machine-readable exact-VI and absent/retain/exclude release invariants. | Reviewed semantic-policy workflow | Append reviewed history for ordinary locks. The four required user exact-VI locks need explicit user instruction plus a coordinated code/data change and cannot be silently deleted or superseded. |
| `review/bilingual_semantic_audit.jsonl` | Fingerprint-bound English/Vietnamese sense decisions and complete source coverage. | `python -m tools.semantic_audit scaffold/import-xlsx/apply-review` | Only through a validated review transaction. |
| `review/vietnamese_naturalness_review.jsonl` | All-sense Vietnamese naturalness evidence with row-specific `reason_code` and EN/example-grounded `semantic_evidence`; user-locked rows also cite `lock_id`, while interpolated bulk templates are rejected. | `python -m tools.semantic_audit vietnamese-review-scaffold/apply-vietnamese-review` | Only through a complete validated review. |
| `review/bilingual_idiom_audit.jsonl` | Phrase-level idiom meaning and display-mode decisions. | `python -m tools.idiom_audit scaffold/import-xlsx` | Only through a validated review transaction. |
| `review/collocation_audit.jsonl` | Fingerprint-bound two-way decisions for every current collocation and mandatory example-linked Oxford/Cambridge candidate. | `python -m tools.collocation_audit scaffold/import-xlsx` | Only through a validated review transaction; every item requires an explicit decision. |
| `review/definition_concision_review.jsonl` | Exact-coverage, fingerprint-bound promotion gate for every current English concision candidate. | `python -m tools.semantic_audit definition-review-scaffold` | Only through a complete validated review; required rewrites/splits belong in the Bilingual Semantic Audit first. |
| `review/semantic_sense_merge_review.jsonl` | Exact-coverage, fingerprint-bound promotion gate proving why every current overlap candidate remains separate. | `python -m tools.semantic_audit sense-merge-review-scaffold` | Only through a complete validated review; apply merge/reword bundles to the Bilingual Semantic Audit first. |
| `curated/semantic_registry.jsonl` | Sole production owner of promoted Definition, DefinitionVI, Example, and idiom semantic payload; schema v4 includes all review provenance. | `python -m tools.semantic_audit promote` | Never. |
| `curated/collocation_registry.jsonl` | Sole production owner of ordered collocation chips and pipe-aligned Oxford/Cambridge/curated provenance after cutover. | `python -m tools.collocation_audit promote` | Never. |
| `curated/deck_audit.jsonl` | Legacy/non-semantic curated builder overrides; cannot override Semantic Registry content. | Reviewed curated-data workflow | Reviewed changes only. |
| `review/gamma_verdicts.json` | Cached legacy sense-simplification decisions. | Sense-simplification workflow | No ad-hoc edits. |
| `review/manual_card_fills.json` | Reviewed manual fills preserved across rebuilds. | Manual-fill review workflow | Reviewed changes only. |
| `review/manual_cards.jsonl` | Manual Card Payloads for content not reconstructable from sources. | Manual-card review workflow | Reviewed changes only. |
| `review/non_oxford_non_c2_overrides.jsonl` | Reviewed non-Oxford/non-C2 routing decisions. | `python -m tools.import_non_oxford_review` | No ad-hoc edits. |
| `review/synonym_example_overrides.jsonl` | Reviewed per-example synonym annotations. | Relation review workflow | Reviewed changes only. |
| `review/antonym_example_overrides.jsonl` | Reviewed per-example antonym annotations. | Relation review workflow | Reviewed changes only. |
| `review/antonym_loop_decisions.jsonl` | Reviewed antonym-loop decisions. | Relation review workflow | Reviewed changes only. |
| `review/sense_label_overrides.jsonl` | Reviewed sense-label corrections. | Sense-label review workflow | Reviewed changes only. |
| `build/anki_notes.jsonl` | Generated structured notes consumed by validation and packaging. | `python -m src.pipeline build` | Never. |
| `build/anki_notes.txt` | Generated tab-separated projection of the same note set. | `python -m src.pipeline build` | Never. |

Card Registry—not either build output—is the authority for stable GUIDs. Build
JSONL and TXT are replaceable projections and must remain semantically aligned.

Supporting data:

- `schema/` contains source-record JSON schemas.
- `oxford_labels.json` and `oxford_symbols.json` contain Oxford taxonomies.
- `.cache_html/{oxford,cambridge}/` contains ignored fetcher caches.
- `scratch/release/*.provenance.json` binds an exact `.apkg` to all canonical
  package inputs and media; `*.verified-import.json` additionally binds the
  exact package to a completed live verification and the post-import APKG
  export's archive/GUID-map hashes and note/card counts. The exported
  `live_guid_proof_*.apkg` is ignored audit evidence, never a semantic
  authority. Other `build/.staging/`, `scratch/`, backups, logs, and reports are
  disposable or ignored workspace artifacts.

## Lifecycle

```text
sources + Card Registry + reviewed semantic/collocation ledgers + policy locks
                         |
                         v
        semantic_audit + collocation_audit promote
                         |
                         v
       curated semantic + collocation registries
                         |
                         v
               pipeline build/validate
                         |
                         v
             build/anki_notes.{jsonl,txt}
                         |
                         v
       package + provenance + verified import receipt
```

## Supported workflows

```bash
# Rebuild source datasets from isolated local caches.
python -m tools._run_full_cache

# Validate and promote reviewed semantics and collocations.
python -m tools.semantic_audit definition-review-scaffold --replace
python -m tools.semantic_audit sense-merge-review-scaffold --replace
python -m tools.semantic_audit validate --require-complete
python -m tools.idiom_audit validate --require-complete
python -m tools.semantic_audit promote
python -m tools.collocation_audit validate --require-complete
python -m tools.collocation_audit promote

# Compute notes without writing outputs, then validate production state.
python -m tools.build_notes --dry-run
python -m src.pipeline validate

# Read-only release checks; use import only after a live verified import.
python -m tools.release_guard canonical
python -m tools.release_guard package
python -m tools.release_guard import
```

## Contracts

- Same canonical inputs must produce byte-identical source,
  semantic/collocation registry, and build artifacts.
- Review state is fingerprint-bound; missing, pending, uncertain, unapproved,
  or stale coverage fails closed.
- The Collocation Audit may be checked against either its captured pre-
  promotion chips or the exact promoted Collocation Registry projection; no
  other post-build collocation state is considered fresh.
- Length, connector, label, overlap, and translation-shape signals only create
  review candidates; they never rewrite, delete, split, or merge a sense.
- The exact user locks `compel` → `ép buộc`, `contender` → `đối thủ nặng ký`,
  `transcribe` → `chép lại`, and `venture` → `mạo hiểm, cả gan` remain release
  invariants until the user explicitly instructs a coordinated change.
- Source definitions are evidence. Only promoted Semantic Registry content may
  populate learner-facing Definition/Example fields.
- Every package provenance sidecar binds both build projections, Card,
  Semantic, and Collocation Registries, every semantic/collocation review and
  policy ledger, every EAVM Recognition/Production template input, packaged
  styling, `design/index.html`,
  the packager implementation and EAVM/genanki contract, the `.apkg`, and its
  media set. Repackaging invalidates the old import receipt.
- Never hand-edit generated registries or build outputs to fix a card. Change
  the authoritative reviewed input and regenerate downstream artifacts.
- New maintained data paths must be exposed by `ProjectPaths` and documented in
  the ownership table above.

## Source schema notes

Each source file contains one JSON object per line. Oxford and Cambridge share
the general record shape: headword metadata plus `pos_data`, definitions,
examples, IPA, audio, labels, idioms, and provenance. `sensenum_local` preserves
Oxford order inside a POS section; null commonly identifies an idiom or
phrasal-verb sense and is not by itself an error.

Every definition also carries `collocation_evidence`, including an empty list
when no evidence was found. The evidence preserves source/origin coordinates;
only Oxford example `cf` and Cambridge example-paired `.lu` entries are
mandatory Collocation Audit candidates. Snippets, bare `.lu`, and grammar `.cl`
remain supporting evidence.
