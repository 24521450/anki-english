# ADR 0027 — Atomic reviewed Card Identity split

**Status:** accepted and implemented 2026-07-22

## Context

Card Identity normally permits one card per `(Word, CEFRLevel, LIST)`. A
reviewed semantic split is an exception that changes several coupled
authorities: the original registry identity, a new GUID/variant/deck, Semantic
Sense identities, complete source-sense coverage, and the current projection
used to review collocations and idioms. Editing these documents sequentially
can leave a half-split state that neither the old identity nor the new pair can
reproduce.

The reviewed `denial`, adjective `alien`, and `sensitivity` changes also show
why a generic “one card per sense” operation is wrong. Each requested secondary
card contains a reviewed group of two senses, and `sensitivity` first merges two
source meanings into one primary Semantic Sense. The transformation must encode
the semantic decision rather than infer a partition from sense count or order.

## Decision

- Represent a split as a fingerprint-bound review bundle consumed by
  `tools.card_identity_split apply-review`. The bundle names the current source
  GUID/identity and fingerprints, primary and secondary variants, the new GUID
  and deck override, complete sense transformations, source ownership,
  collocations, and idioms.
- Require every original Semantic Sense to be consumed exactly once by an
  explicit primary/secondary group. A group may retain one existing Semantic
  Sense ID or merge reviewed origins into one effective payload. Allocate new
  deterministic Semantic Sense IDs for the new secondary GUID.
- Account for every relevant Oxford/Cambridge source sense on exactly one side
  and remap it to the resulting Semantic Sense IDs. Never infer coverage from
  order, labels, or matching text.
- Preserve the original GUID on variant `primary`. Require a canonical new GUID,
  a `secondary_*` variant, and an explicit Secondary Senses deck override for
  the second card. Both exact shapes must be present in the reviewed Card
  Identity allowlist before apply.
- Stage and fully validate Card Registry, Bilingual Semantic Audit, and the
  scratch projection before publishing. Recheck input document hashes, fsync
  staged bytes and old-value backups, then persist a state journal before each
  replacement. Roll back an ordinary failure immediately; a later non-dry-run
  invocation recovers an interrupted journal before reading either authority.
  A partially applied shape is never accepted as current state.
- Make reapplication idempotent: an already-applied pair must reproduce the
  exact reviewed state and hashes rather than duplicate either card.
- Do not mutate Semantic Registry, Collocation Registry, or canonical build
  output in this transaction. Regenerate all fingerprint-bound queues, promote
  the reviewed registries, and rebuild after the atomic identity change.
- The 2026-07-22 allowlist additions are:
  - `denial|C1|Oxford_5000`: original GUID ``$|_`hdAC|%`` as `primary`;
    `Jhp@WXA!ga` as `secondary_entitlement_psychological`.
  - adjective `alien|C1|Oxford_5000`: original GUID `Y&tBh??_,}` as `primary`;
    `q?0?C/TI0}` as `secondary_disapproving_space`.
  - `sensitivity|C1|Oxford_5000`: original GUID `fM]>3mcy3=` as `primary`;
    `fXYJ-i~KFJ` as `secondary_art_physical`.

## Consequences

The three reviewed splits preserve existing scheduling history on their primary
GUIDs while giving each secondary learning unit a stable new identity, deck,
and `SecondarySense` tag after rebuild. Source coverage remains complete through
merges and partitions, and a crash cannot silently publish only the registry or
only the semantic review half.

The workflow is deliberately heavier than adding a registry row: every
downstream fingerprint-bound review must be regenerated and completed. Future
splits still require an explicit semantic decision and allowlist update; this
ADR does not establish pagination or automatic per-sense cards.

## Alternatives considered

- **Hand-edit Card Registry and audit in sequence:** rejected because a failure
  between writes creates an unrecoverable mixed authority.
- **Split automatically by source sense order or POS:** rejected because the
  reviewed boundaries may group senses or merge meanings across source rows.
- **Write downstream registries in the same transaction:** rejected because
  their independent review/promotion gates must observe and approve the new
  candidate sets.
- **Allocate a new GUID to both cards:** rejected because the primary card can
  preserve the established note identity and scheduling history.
- **Treat the secondary card as a manual payload only:** rejected because it
  would bypass source coverage and duplicate canonical identity ownership.

## Related decisions

- [ADR 0006 — Registry-driven fail-closed build](./0006-registry-driven-fail-closed-build.md)
- [ADR 0007 — Reviewed POS split variants](./0007-reviewed-pos-split-variants.md)
- [ADR 0011 — Bilingual semantic registry cutover](./0011-bilingual-semantic-registry-cutover.md)
- [ADR 0017 — Reviewed learner relevance filter](./0017-reviewed-learner-relevance-filter.md)
