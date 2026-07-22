# ADR 0025 — POS-scoped Oxford OPAL membership

**Status:** accepted and implemented 2026-07-19

## Context

Oxford exposes OPAL Written and Spoken badges on entry pages, but the parser's
`_extract_opal` function returned `None` unconditionally. The canonical cache
contains 1,307 labelled pages that consolidate into 1,221 Oxford Records, while
every record previously stored `opal: null`.

A scalar or word-level union is not sufficient. Oxford can mark both W and S,
and merged records can contain differently labelled POS pages. A word-level
union would currently add false OPAL tags to the verb cards for `reference`,
`total`, and `trace`. Sense-less base-entry hubs such as `derive` still carry a
valid verb badge even though their definitions live on a folded phrase page.

## Decision

- Store Oxford OPAL membership as `null` or a POS-keyed object. Each non-empty
  value is exactly `['W']`, `['S']`, or `['W', 'S']` in W-before-S order.
- Detect the first entry headword's `opal_written` / `opal_spoken` attributes
  and its scoped `.webtop > .symbols` badges. Do not treat unrelated page
  symbols as entry evidence.
- Scope a page's membership to its parsed POS sections. If a labelled hub has
  no sections, use the first direct `.webtop > span.pos` entry label.
- Merge and phrasal-verb folding union memberships independently per POS and
  serialize them deterministically.
- Apply OPAL tags after review/manual/semantic and corpus transforms using the
  card's final source lemma and POS. Remove stale OPAL tokens first, then emit
  `OPAL_W` followed by `OPAL_S`. Non-Oxford cards receive neither.
- Fail closed when active same-word/POS homonym candidates disagree rather
  than guessing. Maintain a cache-versus-JSONL guard for full local rebuilds.

## Consequences

`accordingly` and every other cached Oxford entry now retain source OPAL
membership without leaking it across POS. Multi-POS cards receive the union of
their selected POS memberships, and learning-pattern aliases such as
`derive from` can inherit the reviewed base-verb membership.

The Oxford source schema changes from an unused nullable scalar to a structured
map, requiring canonical regeneration of `data/sources/oxford.jsonl` and the
build projections. The full-cache audit remains a local post-rebuild gate
because ignored dictionary HTML is not present in clean CI.

## Alternatives considered

- **Keep a scalar `W`/`S`:** rejected because 457 current records carry both.
- **Store a record-level `['W', 'S']` union:** rejected because it over-tags
  sibling POS cards.
- **Store OPAL only inside `pos_data`:** rejected because labelled hub pages
  have no direct sense sections.
- **Infer OPAL from Oxford 3000/5000:** rejected because these are independent
  list memberships.

## Related decisions

- [ADR 0002 — Multi-POS merge bug](./0002-multi-pos-merge-bug.md)
- [ADR 0006 — Registry-driven fail-closed build](./0006-registry-driven-fail-closed-build.md)
- [ADR 0008 — Learning-pattern headwords](./0008-learning-pattern-headwords.md)
