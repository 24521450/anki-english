# Documentation

`docs/` is the project audit trail. Keep current domain language in `CONTEXT.md`;
use this directory for durable decisions and historical reports.

## Layout

- `adr/` - Architecture Decision Records. These explain decisions that are hard
  to reverse, surprising without context, and involve a real trade-off. Do not
  move or renumber ADRs casually because `AGENTS.md`, `CONTEXT.md`, and old tools
  may cite them.
- `reports/` - execution reports from cleanup, migration, or feature work. These
  are historical evidence, not the current source of truth.

## Cleanup Rules

Before deleting or moving a document, search for references from `AGENTS.md`,
`CONTEXT.md`, `src/`, `tests`, and `tools/`.

If a report only explains a one-shot migration, keep it under `reports/` unless
it is clearly duplicated by an ADR or `CONTEXT.md`.
