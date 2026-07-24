# ADR 0031 — Fingerprint-bound Collocation migration across regenerated source IDs

**Status:** accepted and implemented 2026-07-24

## Context

The Cambridge POS-scoping correction regenerated source-sense and evidence IDs
for many records. At the same time, built notes contained the already-promoted
Collocation Registry projection rather than the pre-review chips captured by
the Collocation Audit. A naïve scaffold therefore reopened thousands of
unchanged decisions, while copying the old ledger would hide genuinely added
or removed evidence.

## Decision

The Collocation scaffold recognizes a promoted card as an audit baseline only
when its identity, collocation text, and collocation provenance exactly match
the existing row's `final_items`. For those rows, it matches current items and
mandatory candidates by their immutable text/provenance plus a stable evidence
key containing every evidence field except regenerated `evidence_id` and
`source_sense_id`. It copies only the prior editable review state and rebuilds
all evidence IDs from the fresh source projection.

New or changed candidate/evidence sets remain pending. A final item is retained
only when every source-backed evidence key and every reviewed current/candidate
dependency survives; otherwise its owners reopen. Complete row bundles may be
applied with the fingerprint-bound `collocation_audit apply-review` command,
which validates immutable inputs and the live projection before an atomic
write.

## Consequences

Parser identity churn no longer creates a false full-deck review queue, while
linguistic source changes still require explicit decisions. Migration is
deterministic and auditable, but a source change can intentionally reopen a
smaller set of affected chips and finals. The canonical audit and Collocation
Registry remain the only authorities; scratch bundles never become production
data directly.

## Alternatives considered

- **Copy the old audit or registry wholesale:** rejected because it would
  silently carry decisions for new, removed, or re-scoped evidence.
- **Ignore source fingerprints globally:** rejected because source drift would
  no longer fail closed.
- **Re-review every row after any parser change:** rejected because it
  confuses regenerated identifiers with changed linguistic evidence and creates
  an unnecessary full-deck queue.
