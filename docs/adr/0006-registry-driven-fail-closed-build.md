# ADR-0006: Registry-driven, fail-closed build contract

- **Status:** Accepted
- **Date:** 2026-07-04
- **Deciders:** project owner
- **Reviewers:** n/a

## Context

The deck builder historically treated generated artifacts as a fallback input
source. That made the build brittle: a missing or stale `anki_notes.txt` could
mask parser gaps, and partial writes could leave the canonical JSONL/TXT pair
out of sync.

The project now maintains canonical registry and manual payload inputs. The
production builder needs a clear contract for what may be emitted, how it is
validated, and how output is published.

## Decision

Adopt a registry-driven build with fail-closed validation:

- `data/curated/card_registry.jsonl` is the canonical inventory for buildable
  cards, identity keys, GUIDs, and routing overrides.
- `data/review/manual_cards.jsonl` carries only manual payload content that
  cannot be reconstructed from source inputs.
- The builder must reject malformed registry/manual input, duplicate identity
  keys, duplicate GUIDs, and unknown overrides instead of skipping cards.
- Validation runs before publish and compares the staged JSONL/TXT pair for
  identity, content, order, audio references, and determinism.
- Publish is transactional: a failed publish must leave the previous canonical
  hashes intact.

## Consequences

- The public build surface no longer depends on generated artifacts as input.
- Missing or malformed canonical data is visible immediately as a build error.
- The build pipeline can be validated in isolation, which makes migration and
  regression testing more reliable.
- Rebuilds remain deterministic because the registry order and GUIDs are part
  of the canonical contract.
