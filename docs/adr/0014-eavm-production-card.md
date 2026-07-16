# ADR 0014 — EAVM Vietnamese-to-English Production Card

**Accepted:** 2026-07-16

## Context

The EAVM deck currently gives learners an English-to-meaning Recognition Card.
That direction supports comprehension, but it does not require active retrieval
of the English headword. A second Anki Note Type would duplicate every field,
GUID, and review identity, making synchronization and migration unnecessarily
fragile.

## Decision

- Keep one EAVM Note Type and one canonical Card Registry/Anki note per
  identity. Add a sibling template named `Production (VI -> EN)` at ordinal 1;
  the established Recognition template remains ordinal 0 and is renamed in
  place when necessary.
- Append `ProductionAnswer` after the existing fields. Derive it only after
  semantic, review, relation, routing, and audio transforms have completed by
  stripping a trailing display qualifier from `Word`. Preserve
  Learning-Pattern Headwords and slots exactly.
- Generate a Production Card only when `DefinitionVI`, `Example`, and
  `ProductionAnswer` are non-empty. Render every aligned sense, mask every
  recognized answer occurrence in the examples (and Vietnamese cue), and use
  Anki's native `{{type:ProductionAnswer}}` comparison with normal
  Again/Hard/Good/Easy self-grading. No aliases or custom grading are added.
- Keep Production Cards in the existing routed decks and active by default so
  the current new-card/day limits control introduction. The answer side shows
  the native typing comparison followed by the unchanged Recognition back.
- Migrate live collections through AnkiConnect only: export a scheduled backup
  before mutation, append the field before adding the template, rename/add
  templates without remove-and-recreate operations, preserve existing card
  schedules, and fail closed on incompatible fields, templates, identities,
  or stale eligibility transitions.

## Consequences

Each eligible note gains one active retrieval card without creating duplicate
notes or changing Recognition scheduling. The package and import validators
must account for two template ordinals (`N` Recognition cards and `M`
Production cards), and a live migration needs card-level checks in addition to
the existing note-field verification. Notes without a reviewed Vietnamese
gloss and example remain Recognition-only until their canonical semantic
payload is complete.
