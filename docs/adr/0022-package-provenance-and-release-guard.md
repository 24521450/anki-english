# ADR 0022 — Package provenance and release guard

**Status:** accepted; implemented 2026-07-18

## Context

Canonical semantic validation alone does not prove that an `.apkg` contains the
current reviewed data, templates, styling, or media. A package filename can stay
the same while any of those inputs change, and a successful earlier import says
nothing about a later rebuild. CI also needs to detect platform-specific
serialization drift without mutating tracked artifacts as part of validation.

The release boundary therefore needs evidence at three different states:
canonical inputs and generated build projections, a concrete package, and a
concrete live import. Treating any one of them as proof of the others permits a
stale package or receipt to pass unnoticed.

## Decision

- After packaging, write a canonical provenance sidecar under
  `scratch/release/`. It binds the raw `.apkg` digest and packaged media-set
  digest to canonical cross-platform content hashes for:

  - build JSONL and TXT;
  - Card Registry and Semantic Registry;
  - Bilingual Semantic Audit, Bilingual Idiom Audit, all-sense Vietnamese
    Naturalness Review, Semantic Policy locks, Definition Concision Review, and
    Semantic Sense Merge Review;
  - Recognition front/back, Production front, Production answer prefix, EAVM
    styling, and `design/index.html`;
  - the packager implementation plus a machine-readable contract containing the
    EAVM model identity, ordered JSON-to-field mapping, template ordinals,
    card-generation requirements, and installed `genanki` version.

- Validate that sidecar against every current input before contacting Anki.
  Repackaging invalidates any earlier verified-import receipt.
- Open the `.apkg` itself and fail closed unless its ZIP inventory, media
  manifest and bytes, SQLite integrity, EAVM model/field/template contract,
  deck, notes, tags, card ordinals, and pristine scheduling state exactly match
  current canonical inputs. Reject non-empty review-log or graveyard tables.
- Run the canonical release guard inside the supported packaging and import
  commands before writing or contacting Anki. The pipeline `validate` stage also
  runs it, so the default workflow and single-stage release commands reject a
  stale or hand-edited Semantic Registry before an `.apkg` can legitimize it.
- Write a verified-import receipt only after AnkiConnect import and the
  note-type, note-count, pristine-new-card, byte-exact live media, and Live GUID
  Proof checks succeed. Matching media filenames are insufficient: retrieve
  every expected file through AnkiConnect, overwrite stale same-name bytes,
  then retrieve and compare independently again. Because `notesInfo` does not
  expose note GUIDs, export the live root deck and verify the SQLite
  GUID-to-identity/card map before writing the receipt. Bind the receipt to the
  exact provenance digest, package digest, verified count, export digest,
  GUID-map digest, and UTC verification time.
- Provide a read-only, fail-closed release guard with three scopes:

  - `python -m tools.release_guard canonical` reproduces the promoted Semantic
    Registry and both build projections in memory, validates the fresh build,
    and requires byte-exact tracked outputs.
  - `python -m tools.release_guard package` validates design sync, current local
    notes/media, the `.apkg`, and its provenance sidecar.
  - `python -m tools.release_guard import` performs the package checks and also
    requires a verified-import receipt for that exact package and expected note
    count.

- Keep all three scopes non-writing and offline with respect to Anki. The import
  scope validates existing evidence; the pipeline import stage remains the only
  operation that contacts Anki and creates the receipt.
- In CI, run the canonical scope on Linux and Windows, build the `.apkg` and
  check package provenance on Linux, and always verify that the tracked checkout
  remains unchanged. Do not run the import scope in CI because there is no live
  Anki collection.

## Consequences

A package can no longer be treated as current merely because it exists or has
the expected name. Changes to semantic decisions, templates, design source,
packager code/contract/dependency, build projections, or media make provenance
validation fail, and a forged/stale archive cannot pass merely because its
sidecar hashes match. A receipt from a previous package cannot authorize a new
import, and release validation itself does not hide drift by regenerating files.

The sidecar and receipt remain ignored release evidence rather than semantic
authorities. Local live releases must retain them long enough to run the
appropriate guard. CI spends additional time reproducing the canonical state on
two operating systems and packaging once, but it now covers the same stale-input
class that caused earlier push/CI and local-import surprises.

## Alternatives considered

- **Hash only `anki_notes.jsonl`:** rejected because TXT parity, review lineage,
  templates, styling, design source, and media can drift independently.
- **Trust the `.apkg` timestamp or filename:** rejected because neither binds
  package contents to canonical inputs.
- **Write a receipt immediately after `importPackage`:** rejected because the
  note type, GUID coverage, count, and media may still be wrong.
- **Read GUIDs from `notesInfo`:** rejected because current AnkiConnect does not
  return that field; an optional-field comparison silently proves nothing.
- **Let the release guard regenerate stale artifacts:** rejected because a
  verifier that mutates state can conceal the exact drift it should report.
- **Run a live Anki import in CI:** rejected because CI has no authoritative
  local collection and must not manufacture live-import evidence.

## Related decisions

- [ADR 0006 — Registry-driven fail-closed build](./0006-registry-driven-fail-closed-build.md)
- [ADR 0010 — Content-addressed Example Audio](./0010-content-addressed-example-audio.md)
- [ADR 0011 — Bilingual Semantic Registry cutover](./0011-bilingual-semantic-registry-cutover.md)
- [ADR 0014 — EAVM Production Card](./0014-eavm-production-card.md)
- [ADR 0021 — Semantic policy and concision promotion gates](./0021-semantic-policy-and-concision-promotion-gates.md)
