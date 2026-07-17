# ADR 0018 — Reviewed bilingual Lexical Gloss concision

**Status:** accepted; implemented 2026-07-17

## Context

The semantic review path can preserve the correct meaning while still copying
the shape of a source definition into the card. This produced grammatically
valid but needlessly explanatory glosses. For example, the first retained sense
of `transcribe` carried a long Vietnamese enumeration instead of the lexical
wording `chép lại, chuyển tự`. Its naturalness review changed punctuation and
flow but did not compress the meaning, so the existing queue and approval fields
were not enough to prevent recurrence.

A hard word limit would be unsafe: legal, scientific, grammatical, and
contrastive senses sometimes need an explicit condition. The problem is not
length by itself, but unreviewed source-shaped wording when an established
shorter equivalent preserves the same learner meaning.

## Decision

- Treat each learner-facing English and Vietnamese meaning as a **Lexical
  Gloss**. Author the two languages independently and use source definitions as
  semantic evidence rather than display copy.
- Prefer the shortest familiar dictionary wording that preserves every material
  condition, restriction, register distinction, and contrast. Clear Hán–Việt or
  technical terms are valid when they are more precise and learnable than an
  explanatory clause.
- Keep length signals heuristic. The Definition Sense Audit queues English at a
  default twelve whitespace tokens in addition to its character and connector
  signals; the Vietnamese queue retains its default eight-token signal. Neither
  threshold is a production cap or an automatic rewrite rule.
- In the Vietnamese long-gloss workflow, an approved `rewrite` must reduce the
  whitespace-token count. An approved `keep_explanatory` decision must record a
  strictly shorter wording considered and the exact material distinction that
  wording would lose. Generic statements such as “preserves nuance” do not
  satisfy the review contract.
- A punctuation-only or word-order-only change does not close a verbosity
  finding when a concise lexical equivalent exists. Equal-length naturalness
  repairs may still be made through the general Bilingual Semantic Audit, but
  they do not count as lexical compression.
- Preserve Semantic Sense identity, source coverage, examples, POS, Card
  Identity, and pipe alignment. Never merge distinct senses merely to shorten a
  card, and never delete a specialist sense through this audit; use the reviewed
  Learner Relevance Filter for that decision.
- Keep all linguistic decisions human/ChatGPT-reviewed and fingerprint-bound.
  Audit heuristics must never generate or approve production wording.

## Consequences

The review process now exposes the counterfactual behind every retained long
Vietnamese gloss and rejects cosmetic rewrites such as the earlier
`transcribe` decision. The broader English queue catches token-heavy wording
that character-only heuristics missed. Review work increases because legitimate
long glosses need a concrete preservation reason, but no hard word cap or
automatic semantic shortening is introduced.
