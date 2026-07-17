# ADR 0016 — POS-scoped idiom ownership

**Status:** accepted; implemented 2026-07-17

## Context

Oxford exposes idioms inside individual noun, verb, adjective, and other entry
pages. The scraper previously stored those idioms in one record-level list and
the merge layer discarded the owning entry boundary. The deck builder then
attached the same list to every CEFR/POS card for that spelling. For example,
Oxford lists `blow your top` under `stack` noun because `blow your stack` is a
North American variant, while the `stack` C2 verb entry owns `stack it`. The
old build placed both on the verb-only card.

## Decision

- Store the owning Oxford entry POS on each `idioms[]` item.
- Preserve `(phrase, POS)` identities when merging source records.
- Filter idioms to the active card POS before ranking and applying the
  two-idiom display limit.
- Deduplicate the displayed phrase after POS filtering so a multi-POS card does
  not show the same phrase twice when Oxford owns it under multiple entries.
- Require idiom POS in the canonical Oxford source schema and rebuild the
  source artifact from cache.
- Treat phrase-to-card relevance as a source/build concern. Bilingual Idiom
  Audit reviews the semantic and Vietnamese payload only after ownership
  selection.

## Consequences

Cards no longer inherit idioms merely because another Oxford entry shares the
same spelling. Correct POS filtering can remove old occurrences and expose the
next eligible Oxford idiom, so the phrase-level audit, Semantic Registry,
Example Audio plan, package, and live Anki collection must be regenerated
together. The source schema becomes stricter, and legacy Oxford records without
idiom ownership must be rebuilt before production use.
