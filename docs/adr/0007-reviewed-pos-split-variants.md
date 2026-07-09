# 0007: Reviewed POS split variants

- Status: Accepted
- Date: 2026-07-05

## Context

Card Identity normally emits one card per `(Word, CEFRLevel, LIST)` and merges
multiple POS labels. Manual review found that `trail|C1|Oxford_5000` and
`torture|C1|Oxford_5000` each contain noun and verb learning units with separate
senses, examples, and collocations. Keeping each word on one card made the
review surface too broad and mixed unrelated recall prompts.

## Decision

Add explicit `noun` and `verb` registry variants for those two identities.
Keep the existing GUID on the noun card because the previous card content was
noun-led, and allocate a new GUID to the verb card. The default multi-POS merge
rule remains unchanged; only identities in the reviewed allowlist may split.

## Consequences

- Production card count increases from 2,452 to 2,454.
- Registry/build validation and the P3B verifier must recognize the exact two
  variant shapes.
- Scheduling history remains attached to the noun cards; verb cards start with
  new GUIDs.
- Future POS splits require explicit review, documentation, and regression
  coverage rather than a general one-card-per-POS rule.
