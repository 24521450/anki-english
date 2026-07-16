# ADR 0013 — Dictionary link provenance

**Accepted:** 2026-07-16

## Context

The EAVM headword and POS Chips need external dictionary links. Cambridge has
a stable headword route, but Oxford can publish separate canonical pages for
each POS or homonym. Cache filenames do not reliably encode those pages: the
cached verb file for `torture` maps to the canonical `torture_2` URL, while the
noun maps to `torture_1`. After Oxford records are merged, one record-level URL
cannot represent every POS safely.

The EAVM model ID and its first 15 fields are immutable. The live model may be
at any valid historical prefix while appended fields are being migrated.

## Decision

- Extract Oxford's canonical URL from cached HTML and retain it on each
  `pos_data` block. Never infer an Oxford suffix from POS order or filename.
- Resolve card links through the promoted Semantic Registry's stable Oxford
  Source Sense IDs. Use a unique `(source lemma, POS)` URL only when reviewed
  sense provenance has no URL; missing or ambiguous POS links remain inactive.
- Build the Cambridge English URL from the normalized source lemma, including
  the existing Learning-Pattern Headword aliases and disambiguator stripping.
- Append `CambridgeURL` and pipe-aligned `OxfordPOSURLs` after `DefinitionVI`.
  Render real external anchors on both card faces without renaming established
  selector classes.
- Treat any existing EAVM field list that is an exact canonical prefix of at
  least the immutable 15 fields as migratable. Append missing fields and reject
  reordered or foreign layouts.

## Consequences

Multi-POS cards such as `torture` can link each chip to the correct Oxford page,
and reviewed homonym variants do not collapse to a word-only guess. Cards with
incomplete provenance degrade to visible non-clickable POS Chips instead of
opening a wrong entry. Source rebuilds remain deterministic because canonical
URLs come from cached inputs, and live Anki updates continue through the
explicit import stage rather than direct collection edits.
