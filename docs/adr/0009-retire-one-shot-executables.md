# ADR 0009 — Retire one-shot executables from HEAD

**Accepted:** 2026-07-12

## Context

Completed data-review phases left hundreds of migration, inspection, and
verification scripts in the active tree. Their accepted payloads already live
in canonical curated/review inputs, while exact migration tests coupled the
current suite to obsolete commands and historical intermediate files.

Keeping the scripts executable made the repository harder to navigate and made
it too easy to run an old mutation against current production data. Deleting
them loses convenient access from `HEAD`, but Git history preserves the exact
implementation and the canonical data preserves the accepted result.

## Decision

- Remove a one-shot command after its output is canonical and current-state
  regression coverage protects the result.
- Do not keep an executable archive in `tools/`.
- Derive production regressions from canonical owner metadata, registry rows,
  and built cards instead of importing migration manifests.
- Keep historical command names in earlier ADRs as time-specific evidence;
  recover their source from Git history when an audit needs it.
- Track only audio reachable from a fresh canonical registry build. Validation
  rejects tracked, unreferenced media so stale alternatives cannot accumulate.

## Consequences

The active tree contains fewer misleading mutation paths and current tests
describe production state. Re-running an old migration now requires an explicit
Git-history recovery and assumption review. Activating a card whose old audio
was pruned may require restoring that media from Git or downloading it again.
