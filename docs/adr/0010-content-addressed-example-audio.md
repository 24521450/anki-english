# ADR 0010 — Content-addressed Example Audio

**Accepted:** 2026-07-13

## Context

The deck needs UK and US speech for every main Example and Idiom Example.
Embedding Edge TTS calls inside the transactional build would mix remote I/O
with canonical artifact publication. Word-, GUID-, or ordinal-based filenames
would also drift when cards or senses are reordered. Standard Anki sound tags
would enqueue every example clip for autoplay.

Edge voices are remote services. Repeating the same request can return MP3
bytes with a different hash, even when the text and effective settings are
unchanged.

## Decision

- Pin `edge-tts==7.2.8` and use `en-GB-RyanNeural` / `en-US-JennyNeural` at
  rate `-5%`, pitch `+0Hz`, and volume `+0%`.
- Derive Example Audio after all build overrides and relation annotations, but
  generate it in a separate resumable pipeline stage before publication.
- Name each clip from a versioned hash of its cleaned spoken text and complete
  synthesis contract. Reuse existing valid media and never refresh it merely
  because the remote service can be called again.
- Commit all reachable Example Audio. Release validation rejects missing,
  untracked, malformed, or stale tracked clips.
- Append four fields to the established EAVM model; keep its ID and original
  field ordinals unchanged.
- Store example references as HTML audio elements and expose explicit UK/US
  controls. Headword sound tags retain their existing playback behavior.
- Import releases through AnkiConnect `importPackage`; direct collection DB
  editing remains prohibited.

## Consequences

References and filenames are deterministic and card reordering does not create
new media. A clean checkout can reproduce the same logical deck, while the
committed cache preserves the exact reviewed MP3 bytes. The repository grows
by roughly one hundred MiB. Updating a voice, cleaner, or synthesis setting
creates a new namespace of files and prunes the now-unreachable old namespace
only after successful generation.
