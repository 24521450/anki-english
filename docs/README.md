# Documentation

`docs/` is the project decision log. Keep current domain language in
`CONTEXT.md`; use this directory for durable decisions that explain why the
codebase is shaped the way it is.

## Layout

- `adr/` - Architecture Decision Records. These explain decisions that are hard
  to reverse, surprising without context, and involve a real trade-off. Do not
  move or renumber ADRs casually because `AGENTS.md`, `CONTEXT.md`, and old tools
  may cite them.

## Cleanup Rules

Before deleting or moving a document, search for references from `AGENTS.md`,
`CONTEXT.md`, `src/`, `tests`, and `tools/`.

Do not add execution reports by default. If a one-shot migration needs durable
context, either fold the current terminology into `CONTEXT.md` or write an ADR
when the decision meets the ADR bar.

Completed one-shot executables do not remain in `HEAD`. Preserve the accepted
result in canonical data and current-state regression tests; use Git history
when the original migration implementation is needed for an audit.
