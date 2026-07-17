# ADR 0017 — Reviewed learner-relevance filtering of senses

**Status:** accepted; implemented 2026-07-16

## Context

Sense Sorting deliberately removed the old numeric sense cap because that cap
discarded useful high-frequency and academic meanings. The Bilingual Semantic
Audit later interpreted “keep all distinct senses” literally and restored some
meanings that had already been reviewed out, including the computing sense of
`domain` and the plant-propagation sense of `cutting`. It also promoted narrow
business jargon for `agile` that the learner does not want on the card.

A numeric cap cannot solve this: frequency order and number of senses do not
tell us whether a meaning is useful. Automatically deleting every source sense
labelled `specialized`, `business`, or another domain would also remove common
IELTS and academic meanings such as treaty `protocol`, chemical `synthesis`,
biological `colonize`, and grammatical `finite`.

## Decision

- Keep every Oxford/Cambridge sense in the raw source artifacts.
- Add an explicit Learner Relevance Filter to the reviewed semantic path before
  Sense Sorting. A reviewer may remove a narrowly occupational, marginal,
  regional, institutional, or domain-specific sense when at least one useful
  learner meaning remains.
- Treat source domain and `specialized` labels as triage signals only. No label
  or lexical heuristic may delete production content automatically.
- Require a removal bundle to name stable semantic sense IDs. In the same
  transaction, every source that targeted a removed sense must be remapped to a
  retained broader sense or explicitly excluded with a non-empty reason.
- Reject unknown IDs, duplicate removals, dangling source targets, and any
  attempt to remove the final semantic sense on a card. Recompact retained sense
  order deterministically.
- After this reviewed filter, Sense Sorting remains a pure no-cap ordering rule:
  every remaining learner-relevant CEFR sense is retained.

The initial review removes the requested `agile` business senses and restores
the earlier `domain` and `cutting` exclusions. It also removes reviewed niche
uses for military `detach`, glitch music, inflection `paradigm`, chapel
subtypes, the humorous comforts use of `civilization`, the golf calculation
for `handicap`, sports-uniform `strip`, and music-arrangement `transcribe`.
Borderline but broadly useful academic or learner senses remain, including
biology `colonize`, treaty `protocol`, chemical `synthesis`, grammar `finite`,
phonetic `transcribe`, and the explicitly reviewed motorsport sense of `rally`.

## Consequences

Cards can stay focused without reintroducing a blind cap. Source evidence and
the reason for every omission remain auditable, and later scaffold or promotion
runs cannot silently restore the reviewed senses. The trade-off is continuing
human judgment: the filter cannot be safely generalized from dictionary domain
labels alone.
