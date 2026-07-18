# ADR 0023 — Canonical GUID storage and live export proof

**Status:** accepted; implemented 2026-07-18

## Context

The original Card Registry bootstrap read a legacy Anki TSV export with a raw
tab split. Python/Anki's CSV writer had legitimately wrapped GUIDs containing
`#` in ASCII double quotes, but the bootstrap treated those quote delimiters as
part of the GUID. This left 237 active canonical GUIDs with outer quotes even
though the live Anki collection stored the unquoted values. A filename/count
comparison did not expose the identity drift.

The earlier live verifier also inspected `note.get("guid")` from AnkiConnect
`notesInfo`. That API does not return a GUID, so the conditional comparison was
a no-op whenever the field was absent. Directly opening the user's live
`collection.anki2` would expose the value but violates the supported Anki
boundary and risks collection corruption.

The same release audit found an analogous media problem: Anki can retain an
older file when a new package contains the same filename. Presence therefore
does not prove byte identity.

## Decision

- Card Registry stores only canonical Anki base91 GUID text. Empty values,
  whitespace, outer quote delimiters, invalid characters, and duplicates fail
  validation.
- Legacy bootstrap may remove exactly one matching pair of outer ASCII double
  quotes before validation. It must reject an invalid result or a collision
  after normalization. Apostrophes, repeated quote layers, and quotes embedded
  in the GUID are not normalized heuristically.
- Build TXT uses a real CSV/TSV writer and strict reader so delimiter quoting is
  decoded at the serialization boundary rather than copied into identity data.
- Live GUID verification uses a post-import `exportPackage` call through
  AnkiConnect. The verifier reads the exported SQLite `notes.guid` column and
  requires exact EAVM model, GUID-to-Card-Identity, fields, tags, deck, and card
  ordinal coverage.
- Modern exports may contain both `collection.anki21` and a compatibility
  `collection.anki2`; prefer `.anki21` and use `.anki2` only when `.anki21` is
  absent. Reject `collection.anki21b` until its format has an explicit parser;
  never fall back to a possibly empty compatibility database in that case.
- The verified-import receipt schema records the post-import phase, exported
  archive digest, canonical GUID-map digest, collection format, note count, and
  card count. No receipt is written if export or inspection fails.
- Media synchronization retrieves existing referenced media and overwrites
  missing or same-name stale bytes. Final verification retrieves the media
  again independently before the GUID export and receipt.

## Consequences

Canonical identities now match the live collection without preserving CSV
syntax as data. Bootstrap remains narrowly compatible with the known legacy
defect, while all established registries fail closed instead of silently
rewriting malformed GUIDs.

Live release takes longer and writes an ignored APKG proof artifact under
`scratch/release/`, because byte-level media verification and deck export are
real I/O boundaries. In exchange, note count, field equality, or a missing
optional API field can no longer masquerade as GUID proof. The workflow still
never opens or edits the user's live collection database directly.

CI cannot perform the live export without Anki, so it exercises synthetic
`.anki2`/`.anki21` archives, unsupported-format rejection, receipt validation,
and GUID normalization/collision regressions. The live `import` release guard
validates the resulting receipt locally.

## Alternatives considered

- **Keep quoted GUIDs as historical identity:** rejected because they are CSV
  delimiters, not the values stored by Anki, and would create duplicate notes.
- **Strip arbitrary quote-like characters everywhere:** rejected because valid
  base91 GUID characters are identity data; only the observed outer ASCII pair
  is a safe bootstrap repair.
- **Trust stable note IDs or note count:** rejected because neither proves the
  Anki GUID used for package merge behavior.
- **Read the live collection database directly:** rejected because AnkiConnect
  export is the supported read boundary and avoids touching an open collection.
- **Trust same-name media:** rejected because the live failure demonstrated
  that Anki may retain older bytes under the canonical filename.

## Related decisions

- [ADR 0006 — Registry-driven fail-closed build](./0006-registry-driven-fail-closed-build.md)
- [ADR 0010 — Content-addressed Example Audio](./0010-content-addressed-example-audio.md)
- [ADR 0022 — Package provenance and release guard](./0022-package-provenance-and-release-guard.md)
