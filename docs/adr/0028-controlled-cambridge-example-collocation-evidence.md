# ADR 0028 — Controlled Cambridge example collocation evidence

**Status:** accepted and implemented 2026-07-22

## Context

Cambridge places many `.cl` labels inside example blocks, but the scraper
previously flattened every `.cl` as supporting grammar evidence and discarded
its example coordinates. Cambridge also demonstrates reusable patterns in
ordinary definition examples without marking them as `.lu` or `.cl`; for
`portion`, repeated examples support the exact frame `portion of`.

Promoting arbitrary example n-grams would create noisy, parser-driven content.
Keeping only marked labels would continue to omit clear dictionary evidence.
The existing Collocation Audit v2 approvals were also generated from repeated
prose templates, so they could not establish item-level review under the new
candidate universe.

## Decision

- Parse `.cl` nested in `.eg` as `cambridge_example_cl`, preserving exact
  example, container, and item coordinates. A standalone `.cl` remains
  `cambridge_grammar_cl`.
- Derive `cambridge_example_pattern` only from an existing displayed surface:
  expand explicit slash tokens, remove at most one trailing `sth`, `sb`,
  `something`, or `somebody`, require a whole-word contiguous example match,
  and require the headword or its regular plural. Do not generate arbitrary
  n-grams or ingest Cambridge collocation-corpus pages.
- Queue every example-linked item, Cambridge bare `.lu`, standalone `.cl`, and
  non-truncated Oxford snippet containing the headword/plural for explicit
  review. Scraper presence is never approval.
- Cut the audit schema to v3 and reset v2 review state. Complete validation
  rejects duplicate reasons and reasons that become identical after replacing
  row surfaces/evidence IDs.
- Partition unresolved review work deterministically by whole GUID across
  exactly three fingerprint-bound manifests.

## Consequences

`portion of` now carries both Oxford and Cambridge evidence without retaining a
learner placeholder. Parser/source drift stales the affected fingerprint and
requires review again. The candidate queue is larger and the previous complete
v2 ledger becomes pending; release remains blocked until every v3 item is
individually resolved and promoted.

## Alternatives considered

- **Keep `.cl` supporting-only:** rejected because it discards exact example
  ownership already present in Cambridge HTML.
- **Mine arbitrary example n-grams:** rejected because phrase boundaries would
  be heuristic and noisy.
- **Reuse v2 approvals:** rejected because their repeated templates do not
  demonstrate row-specific review of the expanded evidence universe.

## Related decisions

- [ADR 0003 — Collocation artifact filter](./0003-colloc-artifact-filter.md)
- [ADR 0024 — Reviewed dictionary-backed collocation registry](./0024-reviewed-collocation-registry.md)
