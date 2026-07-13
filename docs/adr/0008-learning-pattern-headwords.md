# 0008: Learning-pattern headwords

- Status: Accepted
- Date: 2026-07-05

## Context

The cards for `derive` and `deprive` are learned through required prepositional
patterns. Displaying only the bare lemma hides the unit that the examples and
collocations actually test. Renaming the Word field normally changes Card
Identity and can also remove Oxford-list membership because vocab lists use the
base lemma.

## Decision

Display the reviewed cards as `derive from`, `deprive of`, and
`devote sth to sth`, preserve their
existing GUIDs, and store the renamed identities in the Card Registry and
Manual Card Payloads. Corpus Deck Routing maps those display phrases back to
`derive`, `deprive`, and `devote` for source, audio, and list lookup.
`devote sth to sth` keeps the required object position visible; the contiguous
form `devote to` is not used. `deprive of` and `devote sth to sth` use POS
`phrasal verb`; `derive from` retains `phrasal verb, verb` because its card
contains both intransitive and transitive patterns.

## Consequences

- The learner sees the required particle in the headword without losing Anki
  scheduling history.
- Oxford_5000 routing remains based on the base lemma.
- Phrase promotion remains a reviewed allowlist decision. Repeated
  prepositions in Collocations are not sufficient evidence for automatic
  headword renaming.
