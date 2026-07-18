# Documentation

`docs/` is the project decision log. Documentation ownership is deliberately
split so stale chronology cannot masquerade as current policy:

- `CONTEXT.md` owns current project vocabulary.
- `docs/adr/` owns durable rationale and trade-offs.
- `AGENTS.md` owns operational commands and change-impact guidance.
- `data/README.md` owns artifact authority, writers, and lifecycle.
- `tools/README.md` owns supported CLI workflows.
- `USER_NOTES.md` preserves chronological user-request provenance only.

## Layout

- `adr/` — Architecture Decision Records. These explain decisions that are hard
  to reverse, surprising without context, and involve a real trade-off. Do not
  move or renumber ADRs casually because `AGENTS.md`, `CONTEXT.md`, and old tools
  may cite them.

Current semantic/release guardrail decisions:

- [ADR 0017](./adr/0017-reviewed-learner-relevance-filter.md) — reviewed,
  source-accounted learner relevance filtering.
- [ADR 0018](./adr/0018-reviewed-bilingual-lexical-gloss-concision.md) and
  [ADR 0019](./adr/0019-all-sense-vietnamese-naturalness-gate.md) — bilingual
  Lexical Gloss concision and all-sense Vietnamese review.
- [ADR 0021](./adr/0021-semantic-policy-and-concision-promotion-gates.md) —
  durable semantic locks plus canonical Definition/Sense promotion gates.
- [ADR 0022](./adr/0022-package-provenance-and-release-guard.md) — package,
  verified-import, and read-only release boundaries.
- [ADR 0023](./adr/0023-canonical-guid-and-live-export-proof.md) — canonical
  GUID storage, same-name media repair, and post-import export proof.

## Cleanup Rules

Before deleting or moving a document, search for references from `AGENTS.md`,
`CONTEXT.md`, `src/`, `tests`, and `tools/`.

Do not add execution reports by default. If a one-shot migration needs durable
context, either fold the current terminology into `CONTEXT.md` or write an ADR
when the decision meets the ADR bar.

Completed one-shot executables do not remain in `HEAD`. Preserve the accepted
result in canonical data and current-state regression tests; use Git history
when the original migration implementation is needed for an audit.

`tests/test_documentation_contracts.py` rejects duplicate ADR numbers,
non-portable or broken maintained-document links, duplicate design README
bodies, and undocumented file artifacts exposed by `ProjectPaths`.
