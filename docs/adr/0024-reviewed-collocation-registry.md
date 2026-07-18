# ADR 0024 — Reviewed dictionary-backed collocation registry

**Status:** accepted and implemented 2026-07-18

## Context

The deck's `Collocations` field was assembled from legacy curated overrides and
manual payloads without per-chip provenance. Oxford and Cambridge often expose
more useful patterns than the displayed list. For example, Oxford evidence for
`curriculum` contains both `on the curriculum` and `in the curriculum`, while
the card showed only the first. Conversely, a source page may contain grammar
frames, truncated collocation-dictionary snippets, or bare labels that are
useful review evidence but are not automatically suitable learner chips.

Without a reviewed authority, the template cannot distinguish a dictionary-
backed phrase from a curated default. Adding source phrases automatically would
also make source-parser drift change production content without a linguistic
decision, while auditing only source candidates would leave existing malformed,
duplicated, or weak chips unaccounted.

## Decision

- Parse structured collocation evidence from Oxford and Cambridge while
  retaining its source, origin, source-sense coordinates, and display text.
- Treat only evidence linked to an example as a mandatory review candidate:
  Oxford example `cf` text and a Cambridge `.lu.dlu` paired with an `.eg` in the
  same example block. Oxford Collocations Dictionary snippets, Cambridge bare
  `.lu`, and Cambridge grammar `.cl` text remain supporting evidence. A
  supporting-only phrase may be promoted only by an explicit item-level review;
  it is never mandatory or promoted merely because the parser found it.
- Maintain a separate, fingerprint-bound Collocation Audit with two-way
  coverage. Every existing displayed chip and every mandatory source candidate
  receives an explicit item-level disposition; no heuristic marks linguistic
  content approved.
- Promote a complete approved audit deterministically into a standalone
  Collocation Registry. It is the sole production owner of learner-facing
  collocation text and provenance after cutover. Card Identity remains owned by
  Card Registry and semantic senses remain owned by Semantic Registry.
- Keep at most five chips per card and reject, rather than truncate, an
  oversized result. Source-backed phrases remain exact separate chips; slash
  compression is permitted only for a reviewed curated/default chip.
- Require source evidence to belong to the card headword (including reviewed
  spelling/plural/learning-pattern equivalences). The cutover's one exact
  derivational exception is Cambridge `trading partner`: its source page is
  headed `trade`, but no other `trade ...` phrase may inherit that exception.
- Order source-backed items with Oxford evidence first, then Cambridge-only
  evidence, followed by retained curated items in their reviewed order. The
  same normalized phrase supported by both dictionaries is one item with
  `oxford+cambridge` provenance.
- Append `CollocationSources` after `IdiomMeaningVI` in the established EAVM
  Note Type. It is pipe-aligned with `Collocations` and uses `oxford`,
  `cambridge`, `oxford+cambridge`, or `curated`. Source-backed chips receive a
  visible OXF/CAM marker as well as a distinct style; missing or invalid legacy
  metadata renders every chip as the neutral curated/default style.
- Do not mix reviewed and legacy ownership card by card. Production continues
  to use the existing payload until the audit is complete; the cutover then
  requires exact active-card registry coverage and fails closed.
- Bind both the Collocation Audit and Collocation Registry into package
  provenance and reproduce the registry at the canonical release boundary.

## Consequences

Dictionary evidence becomes visible and auditable without implying that every
source label is a recommended collocation. A learner can see which chips have
Oxford/Cambridge backing, and `curriculum` can carry both exact Oxford patterns.

The full-deck review is intentionally larger than a source-only enrichment pass:
legacy chips, mandatory candidates, exclusions, rewrites, ordering, and the
five-chip budget all require explicit decisions. A source parser change can
stale affected audit fingerprints and block promotion. This cost is accepted so
new scraper output cannot silently rewrite production cards.

The EAVM migration remains append-only and preserves model identity, note GUIDs,
cards, and schedules. Older notes render safely but cannot claim dictionary
provenance until rebuilt from the reviewed registry.

## Alternatives considered

- **Color every scraper collocation automatically:** rejected because source
  sections include grammar frames, bare labels, and truncated supporting text.
- **Audit only missing source phrases:** rejected because existing chips would
  retain unreviewed duplicates, markup, slash compression, and idiom overlap.
- **Store collocations inside Semantic Registry:** rejected because collocation
  evidence has an independent lifecycle and would unnecessarily invalidate all
  bilingual semantic fingerprints.
- **Allow per-card legacy fallback after cutover:** rejected because a mixed
  authority would hide incomplete review and make release contents ambiguous.
- **Show source only by color:** rejected because provenance must remain visible
  without color perception and available to assistive technology.

## Related decisions

- [ADR 0003 — Collocation artifact filter](./0003-colloc-artifact-filter.md)
- [ADR 0006 — Registry-driven fail-closed build](./0006-registry-driven-fail-closed-build.md)
- [ADR 0011 — Bilingual semantic registry cutover](./0011-bilingual-semantic-registry-cutover.md)
- [ADR 0022 — Package provenance and release guard](./0022-package-provenance-and-release-guard.md)
