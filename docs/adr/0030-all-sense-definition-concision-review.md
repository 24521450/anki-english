# ADR 0030 — All-sense Definition Concision Review

**Status:** accepted and implemented 2026-07-24

## Context

Definition length and connector thresholds identified unusually verbose English
wording, but the canonical Definition Concision Review covered only rows that
crossed those heuristics. A short definition could therefore reach production
without an explicit concision judgment, even though unnecessary placeholders,
awkward phrasing, or a missed semantic distinction are not reliably correlated
with token count.

The thresholds remain useful for triage. They are not a safe boundary for
semantic review or an automatic rewriting rule.

## Decision

- Generate the canonical Definition Concision Review over every promoted
  Semantic Sense. Schema v4 records `scope: all` and requires exact current
  sense coverage before promotion.
- Keep the existing length/connector signals as report and work-order triage.
  An untriggered row still requires an approved, fingerprint-bound
  `keep_concise` judgment with row-specific semantic evidence.
- A triggered row may remain unchanged only through `keep_explanatory`, with a
  genuinely shorter or connector-reduced alternative, the exact distinction
  that alternative would lose, and source-grounded evidence.
- Apply every required rewrite or split through Bilingual Semantic Audit,
  regenerate the candidate universe, and review the replacement row. The
  Definition ledger never edits production content directly.
- Review operationally in deterministic batches of at most 100 senses. Batch
  partitioning is a work-allocation mechanism only; the canonical ledger and
  promotion gate still require one exact global candidate set.
- Do not auto-approve rows from token count, unchanged text, or Cambridge
  dictionary presence. Cambridge English–Vietnamese evidence can support a
  judgment but does not replace row-specific review.

## Consequences

No Definition EN is omitted merely because it is short. The common case can be
recorded as `keep_concise`, while the smaller triggered set receives deeper
counterfactual review. Parser, semantic, or Card Identity drift invalidates only
the affected fingerprints when content/evidence remains stable, but completing
the first all-sense ledger requires substantially more review work.

## Alternatives considered

- **Retain threshold-only canonical coverage:** rejected because it treats a
  triage heuristic as proof that every other definition is concise.
- **Impose a hard word cap:** rejected because register, scope, contrast, and
  grammatical conditions sometimes require longer wording.
- **Rewrite every definition automatically:** rejected because concision cannot
  safely override semantic distinctions or source accounting.
- **Let batch files become authorities:** rejected because partial batch state
  could bypass exact global coverage and immutable fingerprints.

## Related decisions

- [ADR 0017 — Reviewed learner relevance filter](./0017-reviewed-learner-relevance-filter.md)
- [ADR 0021 — Semantic policy and concision promotion gates](./0021-semantic-policy-and-concision-promotion-gates.md)
- [ADR 0029 — Cambridge English–Vietnamese evidence snapshot](./0029-cambridge-english-vietnamese-evidence-snapshot.md)
