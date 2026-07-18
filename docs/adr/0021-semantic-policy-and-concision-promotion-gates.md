# ADR 0021 — Semantic policy and concision promotion gates

**Status:** accepted; implemented 2026-07-18

## Context

The all-sense Vietnamese review closed the length-threshold gap described by
ADR 0019, but several recurrence paths remained. A short literal translation
could receive generic approval evidence, an exact user correction could be
lost when a ledger was regenerated, and English concision or possible duplicate
senses could be reported without blocking promotion. Historical report files
also made it too easy to confuse “candidate inspected” with “current canonical
state approved.”

The failures are semantic, not numeric. Definition length, connectors,
Vietnamese overlap, source labels, and historical grouping are useful triage
signals, but none can decide safely whether wording should change or whether a
sense should be removed, split, or merged.

## Decision

- Maintain `data/curated/semantic_policy_locks.jsonl` as the machine-readable
  policy for exact Vietnamese wording, absent Semantic Senses, and retained or
  excluded source mappings. Validate active locks against the Bilingual
  Semantic Audit, promoted Semantic Registry, and built notes.
- Treat four explicit user corrections as required release invariants:
  `compel` → `ép buộc`, `contender` → `đối thủ nặng ký`, `transcribe` →
  `chép lại`, and `venture` → `mạo hiểm, cả gan`. Removing, superseding, or
  changing one requires a new explicit user instruction and a coordinated
  policy/code/data change; absence of a ledger row cannot relax it.
- Require every resolved all-sense Vietnamese Naturalness Review row to carry a
  decision-specific `reason_code` and unique row-specific `semantic_evidence`.
  Evidence for an ordinary row names its final Vietnamese wording, exact
  English sense, and a sense-specific example or source definition. Validation
  removes interpolated headword/final-VI text before detecting generic and
  duplicate residual templates, so shared approval prose cannot masquerade as
  hundreds of independent reviews. A
  `user_lock` verdict additionally cites the exact `lock_id`; non-locked rows
  must not borrow a lock ID. Promotion resolves that ID against the active
  exact-VI policy row, requires matching card/sense/word/final wording, rejects
  duplicate or invented claims, and requires every active exact user lock to be
  claimed exactly once.
- Keep `definition-audit` and `sense-merge-audit` report-only. They may create
  scratch reports and review bundles, but do not mutate canonical ledgers or
  Semantic Registry.
- Add exact-coverage canonical ledgers at
  `data/review/definition_concision_review.jsonl` and
  `data/review/semantic_sense_merge_review.jsonl`. Derive both candidate sets
  from the payload that would be promoted, bind every row to its current
  fingerprint, and reject missing, extra, stale, pending, uncertain, or
  unapproved coverage.
- For a Definition candidate to remain unchanged, require approved
  `keep_explanatory` evidence naming a genuinely shorter or connector-reduced
  alternative, the exact material distinction it would lose, and semantic
  evidence containing the current wording, alternative, and distinction.
  A required rewrite or split stays open until it is applied through a
  Bilingual Semantic Audit review transaction and the queue is regenerated.
- For a current Sense Merge candidate to remain separate, require an approved
  `keep_separate` verdict whose row-specific distinction cites at least two
  affected Semantic Sense IDs. Merge/reword proposals must first be applied to
  the Bilingual Semantic Audit with complete source remapping, after which the
  candidate queue is regenerated.
- Make Semantic Policy, Definition Concision Review, and Semantic Sense Merge
  Review mandatory promotion inputs. Semantic Registry schema v4 records the
  canonical content hash of each alongside the existing semantic, idiom, and
  Vietnamese review hashes.
- Never rewrite, delete, split, merge, keep, or approve a sense automatically
  from length, connector count, source label, translation shape, or semantic
  overlap.

## Consequences

Promotion now fails closed on policy drift and on every current EN-concision or
possible-merge candidate. A regenerated report cannot silently stand in for
canonical review, and generic or interpolated bulk evidence cannot close the
gate. Exact user
wording remains stable across scaffold, promotion, build, and release checks.

The cost is more row-specific review work and an explicit repair/rescaffold
cycle when a candidate truly needs a rewrite, split, merge, or removal. This is
intentional: the system preserves source accounting and Semantic Sense identity
instead of letting a heuristic mutate learner-facing content.

## Alternatives considered

- **Leave Definition and Sense Merge checks report-only:** rejected because a
  known unresolved candidate could still be promoted.
- **Use hard word-count or overlap thresholds:** rejected because legitimate
  technical distinctions can be long or lexically similar, while short literal
  translations can still be unnatural.
- **Rely only on regression tests for the four user corrections:** rejected
  because the decisions also need machine-readable lineage through audit,
  registry, build, and package inputs.
- **Allow generic “keep as is” evidence:** rejected because it neither proves
  row-level review nor records the material distinction being preserved.

## Related decisions

- [ADR 0011 — Bilingual Semantic Registry cutover](./0011-bilingual-semantic-registry-cutover.md)
- [ADR 0017 — Reviewed learner-relevance filtering of senses](./0017-reviewed-learner-relevance-filter.md)
- [ADR 0018 — Reviewed bilingual Lexical Gloss concision](./0018-reviewed-bilingual-lexical-gloss-concision.md)
- [ADR 0019 — All-sense Vietnamese naturalness promotion gate](./0019-all-sense-vietnamese-naturalness-gate.md)
- [ADR 0022 — Package provenance and release guard](./0022-package-provenance-and-release-guard.md)
