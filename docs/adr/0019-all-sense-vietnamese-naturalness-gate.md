# ADR 0019 — All-sense Vietnamese naturalness promotion gate

**Status:** accepted 2026-07-17

**Supersedes:** the promotion-gate scope of ADR 0016. ADR 0016 remains in
force for long-gloss triage, its eight-token review signal, and its prohibition
on automatic rewriting.

## Context

ADR 0016 introduced a fingerprint-bound naturalness review for Vietnamese
definitions with at least eight whitespace-delimited tokens. That workflow
successfully exposed verbose literal translations, but its promotion gate only
covered the long-gloss queue. Short wording could therefore reach production
without an explicit naturalness verdict.

`compel` demonstrated the gap. The Vietnamese payload `ép buộc; khiến trở nên
cần thiết` mirrors both clauses of the English source definition, but the
learner-facing lexical equivalent is simply `ép buộc`. English source coverage
must account for the complete sense; it does not require `DefinitionVI` to copy
every explanatory clause. Cambridge English–Vietnamese supports this wording,
but it is evidence rather than a mandatory transcription source. Synonyms such
as `bắt buộc` or `thúc ép` belong only when they materially improve clarity or
recall, not as padding.

## Decision

- Require an explicit Vietnamese Naturalness Review verdict for every promoted
  Semantic Sense, irrespective of DefinitionVI length.
- Use the canonical `--scope all` scaffold as the promotion-gate ledger. Keep
  `--scope long` and the report-only Vietnamese audit as verbosity triage.
- Record `keep_natural`, `keep_explanatory`, `rewrite`, or an unresolved verdict
  per sense. Pending, uncertain, unapproved, missing, or stale rows block
  promotion.
- Bind verdicts to immutable per-sense fingerprints. Reuse an approved verdict
  when that fingerprint is unchanged; require a fresh verdict only for new or
  changed senses. Unchanged wording without an approved row is not reviewed.
- Author DefinitionVI as a natural, concise Vietnamese lexical equivalent, not
  as a clause-by-clause translation of Definition EN. Preserve source coverage
  through semantic mappings rather than display-text symmetry.
- Continue the stricter ADR 0018 contract for long-gloss findings: a rewrite
  must reduce token count, while `keep_explanatory` must name a strictly shorter
  alternative and the exact material distinction it would lose.
- Keep Cambridge English–Vietnamese as supporting evidence. Reviewers may choose
  another natural Vietnamese wording, and may add synonyms only when useful.

## Consequences

Every promoted Vietnamese sense now has explicit, auditable naturalness
evidence, including short machine-shaped glosses that length heuristics cannot
detect. Stable fingerprints avoid repeatedly reviewing unchanged senses, while
new or changed semantic content fails closed. Review volume increases for the
initial all-sense cutover and for genuinely changed senses thereafter.

The long-gloss queue remains useful for prioritizing compression work, but no
threshold defines production coverage or authorizes automatic rewriting.
Semantic Registry remains the sole production owner; the naturalness ledger is
review evidence and a promotion prerequisite, not a second registry.

## Alternatives considered

- **Keep the naturalness audit report-only:** rejected because reports cannot
  prevent an unreviewed short literal translation from reaching production.
- **Gate only heuristic candidates:** rejected because token counts and wording
  signals cannot reliably distinguish a concise lexical equivalent from a
  mechanically translated clause.
- **Require every Vietnamese gloss to mirror every English clause:** rejected
  because source coverage is a semantic accounting obligation, not a display
  translation format, and this rule produced the `compel` failure.
