# ADR 0016 — Reviewed Vietnamese Definition naturalness

**Status:** accepted; implemented 2026-07-16

**Amended by:** [ADR 0018](./0018-reviewed-bilingual-lexical-gloss-concision.md),
which adds the explicit compression/counterfactual contract for candidates in
the long-gloss queue.

**Superseded by:** [ADR 0019](./0019-all-sense-vietnamese-naturalness-gate.md)
for promotion-gate coverage. The naturalness principles and long-gloss triage
rationale here remain applicable.

## Context

The Bilingual Semantic Audit verifies Vietnamese semantic equivalence, but an
equivalent translation can still be awkward for a learner when it mirrors an
English explanatory clause word for word. The promoted examples
`contender → người hoặc đội có cơ hội thắng trong một cuộc thi` and
`venture → mạo hiểm đi đâu, làm hoặc nói điều gì` are correct in substance yet
less natural than compact Vietnamese dictionary wording. A hard word limit
would create the opposite error by forcing genuinely useful explanations to
lose distinctions.

## Decision

- Build a deterministic review queue from every promoted `DefinitionVI` with
  at least eight whitespace-delimited tokens. The threshold is triage only,
  never a production length limit.
- Record one explicit decision per queued semantic sense:
  `keep_explanatory`, `rewrite`, or `uncertain`. A rewrite must include its
  reviewed Vietnamese text, reason, reviewer, date, approval, and immutable
  source fingerprints.
- Treat Cambridge English–Vietnamese as supporting evidence. Reviewers may use
  another natural Vietnamese wording when it preserves the reviewed English
  sense more clearly.
- Apply only a complete, non-stale review transactionally to the Bilingual
  Semantic Audit. The apply step may replace only the selected
  `definition_vi`; it must preserve English definitions, examples, source-sense
  mappings, Cambridge provenance, Card Identity, and idiom payload.
- Keep Semantic Registry as the sole production semantic owner. The
  naturalness ledger is review evidence and an input to the existing semantic
  promotion path, not a second production registry.
- Do not auto-translate or auto-rewrite candidates. Heuristic flags and length
  metrics only prioritize human review, and the release path has no live
  dictionary-network dependency.

## Consequences

Long but useful Vietnamese explanations can be explicitly retained, while
literal translations are shortened without silently narrowing their senses.
Fingerprint checks make later source or promotion changes fail visibly instead
of reapplying an obsolete wording. The additional ledger and review step add
maintenance cost, but production ownership and downstream Definition/Example
alignment remain unchanged.
