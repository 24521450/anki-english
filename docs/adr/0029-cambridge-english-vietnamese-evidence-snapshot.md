# ADR 0029 — Cambridge English–Vietnamese evidence snapshot

**Status:** accepted and implemented 2026-07-24

## Context

The semantic review pipeline used Cambridge English definitions but did not
retain a full-deck Cambridge English–Vietnamese artifact. Reviewers therefore
could not reproduce which bilingual entries, translations, or missing
translations were available when learner wording was judged. Fetching pages
ad hoc would also make later review sensitive to network failures, rate limits,
and dictionary drift.

Treating the bilingual dictionary as a production override would be unsafe:
its entry structure does not map one-to-one to Card Identity or Semantic Sense,
some translations are absent, and learning-pattern headwords need explicit
lookup aliases.

## Decision

- Maintain `data/sources/cambridge_english_vietnamese.jsonl` as a deterministic
  canonical source snapshot with one row per normalized lookup.
- Plan exact active Card Identity coverage. Use only explicit aliases for
  learning patterns and explicit supplemental lookups for lexicalized forms;
  do not stem or lemmatize implicitly.
- Preserve entry/POS structure, English definitions, Vietnamese translations,
  examples, stable source IDs, cache-byte fingerprints, and `found` /
  `no_entry` status. Preserve senses whose translation is missing.
- Keep the HTML cache isolated under
  `data/.cache_html/cambridge_english_vietnamese/`. Reuse complete cache pairs
  and fetch with shared pacing plus bounded 429/5xx/network backoff.
- Fail on transient or unexpected HTTP errors, incomplete cache pairs,
  unrecognized page structures, stale fingerprints, or coverage drift. Never
  reinterpret those failures as `no_entry`; a positive dictionary no-result
  response may still record reviewed absence evidence.
- Bind the snapshot into package provenance and the canonical Release Guard.
  Use it as supporting review evidence only; Bilingual Semantic Audit and
  Semantic Registry continue to own production Definition/Example content.

## Consequences

Every active card has durable, reproducible Cambridge bilingual reference data
without granting the scraper authority to rewrite the deck. Card Identity
changes stale exact coverage and require a deterministic snapshot rebuild, but
cached HTML can be reused. A full refresh is slower because respectful pacing
and fail-closed retries are preferred over partial or misclassified data.

## Alternatives considered

- **Fetch Cambridge bilingual pages during each review:** rejected because
  reviews would not be reproducible and transient failures could change the
  evidence set.
- **Store only successful translated senses:** rejected because missing entries
  and missing translations are meaningful coverage facts.
- **Make Cambridge translations production overrides:** rejected because sense
  alignment is not one-to-one and would bypass reviewed semantic ownership.
- **Infer lookups by stemming:** rejected because lexicalized plurals and
  learning-pattern headwords require explicit, reviewable identity.

## Related decisions

- [ADR 0011 — Bilingual Semantic Registry cutover](./0011-bilingual-semantic-registry-cutover.md)
- [ADR 0021 — Semantic policy and concision promotion gates](./0021-semantic-policy-and-concision-promotion-gates.md)
- [ADR 0022 — Package provenance and release guard](./0022-package-provenance-and-release-guard.md)
