# ADR 0015 — Phrase-level bilingual idiom payload

**Status:** accepted; implementation in progress 2026-07-16

## Context

The learner-facing deck contains hundreds of selected idioms, including the
same phrase on more than one card. Oxford and Manual Card Payloads currently
own the English phrase, explanation, and example, while Semantic Registry owns
the reviewed Definition/Example payload. Translating each card occurrence
independently would duplicate review decisions, and a second production
registry would create a competing semantic owner.

## Decision

- Review only idioms selected for active cards. Bilingual Idiom Audit uses one
  row per normalized English phrase plus normalized source explanation and
  records every card occurrence separately for exact coverage.
- Use `vi_equivalent` for a natural Vietnamese proverb, idiom, saying, or fixed
  figurative expression whose meaning is equivalent or clearly related. Exact
  imagery, grammar, and pragmatic scope are not required. For example,
  `get back on the rails` maps to `đâu lại vào đấy`, and `be at odds ...` maps
  to `trống đánh xuôi, kèn thổi ngược`. Use `bilingual_gloss` only when no
  established Vietnamese expression has a clear semantic link or a candidate
  would materially mislead the learner. Each review unit has one canonical
  Vietnamese result.
- Treat `bilingual_gloss` as two concise learner glosses, not as a full
  translation of the source definition. English and Vietnamese each state the
  core meaning naturally in their own language; Vietnamese must not mirror the
  English sentence structure. There is no hard word limit, and a longer gloss
  is justified only when shortening would remove a material condition or
  restriction. Do not repeat visible learning slots such as `somebody` or
  `something` through placeholder subjects, objects, or subordinate clauses;
  use a compact lexical pair when it carries the same core meaning. Canonical
  fallbacks include `an old wives’ tale` as `an old belief that is not true` /
  `quan niệm dân gian sai lầm`, `twist somebody’s arm` as
  `persuade/pressure` / `thuyết phục/nài ép`, `put somebody to the sword` as
  `kill` / `giết`, and `shake/rock the foundations ...` as `seriously weaken
  something at its core` / `làm lung lay tận gốc`.
- Treat unchanged text as an explicit review outcome, never as proof that a row
  was reviewed. Retaining an existing `bilingual_gloss` requires a row-specific
  reason naming a shorter wording considered and the exact material distinction
  it would lose, or an exact user-locked canonical pair. A shared bulk reason
  such as “already concise” cannot close multiple unchanged rows.
- Promote the complete phrase-level ledger into Semantic Registry schema v2.
  Semantic Registry remains the sole production owner and carries structured
  idiom payload per card; missing, pending, uncertain, or stale idioms block
  promotion and production build.
- Preserve the established `Idioms` and Idiom Example Audio grammars. Append
  `IdiomMeaningVI` to the EAVM Note Type, aligned by `$$`, and encode each cell
  as the reviewed display mode plus Vietnamese text. The English source
  explanation remains available as a compatibility fallback when the mode is
  `vi_equivalent`.
- Keep selected examples and their content-addressed UK/US audio unchanged.
  Live migration appends the field through AnkiConnect and verifies existing
  note identities, sibling cards, schedules, templates, and media.

## Consequences

Duplicate phrases are reviewed once without losing card-local order or source
evidence. The audit and promotion workflow becomes larger, but future source
changes cannot silently reuse a stale Vietnamese meaning. Old notes and
templates still show their English explanation, while a complete new payload
renders either Vietnamese only or the reviewed English/Vietnamese pair.
