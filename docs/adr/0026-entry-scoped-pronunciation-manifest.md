# ADR 0026 — Entry-scoped pronunciation locks and media manifest

**Status:** accepted and implemented 2026-07-22

## Context

Oxford and Cambridge pages can expose several homographs, parts of speech, and
dictionary editions under one spelling. The earlier source records collapsed
those entries into top-level UK/US IPA and audio fields, while build overrides
and inherited filenames could select a different entry. A card could therefore
show Cambridge audio with IPA from another homograph, or retain a plausible
filename whose bytes no longer represented the selected URL.

The request to align the complete deck's IPA with its dictionary audio makes
the unit of selection important: IPA and audio must come from the same source
entry and accent. Learning-Pattern Headwords add another ambiguity because a
display phrase may intentionally resolve a different exact source headword.
Remote dictionary downloads also cannot promise byte-identical regeneration,
so reproducibility needs a local byte authority after selection.

## Decision

- Source schema v3 preserves a `pronunciations` list for Oxford and Cambridge.
  Each item records source file, dictionary/entry identity and rank, entry
  headword, POS, and UK/US payloads. An accent payload keeps IPA and audio URL
  from that same entry.
- Treat the legacy top-level IPA/audio fields as compatibility data only. The
  production resolver considers complete same-entry accent pairs and never
  combines fields from different entries or chooses a candidate from a media
  filename.
- Resolve an exact normalized source headword. Rank Cambridge before Oxford,
  then dictionary rank, exact entry headword, and POS match. Do not stem,
  lemmatize, or search fuzzy aliases implicitly.
- Store every ambiguous selection, explicit source-headword alias, and reviewed
  absence in `data/curated/pronunciation_selection_locks.jsonl`, keyed by Card
  GUID and accent. A `select` lock binds the complete candidate and candidate-
  set fingerprint; `no_pronunciation` records reviewed absence. Changed source
  candidates stale the lock and fail closed.
- Generate `data/sources/headword_audio_manifest.jsonl` with
  `tools.sync_pronunciation_audio`. Each row is keyed by selection fingerprint
  and binds the full dictionary/entry/headword/POS identity plus a separate
  media fingerprint, source, parent word, accent, IPA, URL, filename, byte
  count, and SHA-256. Distinct entry selections may share a file only when the
  media fingerprint, filename, and byte attestation are exact. Download into
  staging, validate the media, then publish files and manifest transactionally.
- Make production build reconstruct every selection from source entries and
  locks, bind it to the manifest, and verify the local media bytes. Production
  requires exact coverage and fails closed when either authority is missing,
  stale, or contains an unused row. Narrow legacy bypasses exist only for
  isolated test fixtures.
- Keep `--attest-existing` migration-only: it may adopt a valid base-name MP3
  only when the selected URL exactly matches the source record's legacy
  top-level URL. It never changes candidate selection. Resume only a staging
  directory whose filenames match the current plan.

## Consequences

Headword IPA and audio now share a traceable dictionary-entry identity for each
accent. Homograph and POS choices become reviewable, Learning-Pattern aliases
are explicit, and a stale same-name MP3 is detected by bytes rather than trusted
by its path.

Source rebuilds can invalidate locks and require review. First-time sync may
download many files and depends on remote rate limits. The remote response is
not guaranteed byte-identical under forced regeneration; deterministic release
means stable selection plus the tracked manifest and verified local bytes.

## Alternatives considered

- **Always use Cambridge's top-level IPA/audio:** rejected because a top-level
  fold loses entry/POS identity and can choose the wrong homograph.
- **Pair Cambridge IPA with an existing audio filename:** rejected because the
  filename neither proves source entry nor media bytes.
- **Implicitly lemmatize every display headword:** rejected because it can
  silently redirect ordinary words and phrases; source aliases require review.
- **Redownload on every build:** rejected because builds would depend on a
  remote service and could not prove byte-stable package media.
- **Hash only filenames in release provenance:** rejected because same-name
  stale media is an observed failure mode.

## Related decisions

- [ADR 0006 — Registry-driven fail-closed build](./0006-registry-driven-fail-closed-build.md)
- [ADR 0008 — Learning-pattern headwords](./0008-learning-pattern-headwords.md)
- [ADR 0010 — Content-addressed example audio](./0010-content-addressed-example-audio.md)
- [ADR 0022 — Package provenance and release guard](./0022-package-provenance-and-release-guard.md)
