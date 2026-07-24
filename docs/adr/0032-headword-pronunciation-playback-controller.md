# ADR 0032: Headword pronunciation playback controller

Status: Accepted

Date: 2026-07-24

## Context

The Recognition answer rendered IPA in the word metadata row and rendered the
established `AudioUK` / `AudioUS` `[sound:...]` fields as separate Anki replay
buttons. This split one Entry-Scoped Pronunciation into unrelated visual
controls, gave the surrounding pill a click affordance that was wider than the
native replay target, and did not expose reliable `playing`, `ended`, `pause`,
or `error` events to the card template.

The redesigned interaction requires UK-only answer autoplay, direct accent
selection from the IPA, an icon visible only during real playback, immediate
UK/US replacement, and `R` replay of the most recently selected accent.
Anki's transformed native replay controls do not provide the template with a
stable media source or playback lifecycle for those requirements.

## Decision

Append `HeadwordAudioUKSrc` and `HeadwordAudioUSSrc` to the existing EAVM Note
Type. Packaging and import derive their values deterministically from the
established `AudioUK` and `AudioUS` `[sound:...]` references. These fields are
media-only template inputs; Entry-Scoped Pronunciation selection, Pronunciation
Selection Locks, the Headword Audio Manifest, and local byte attestation remain
authoritative.

The Recognition back template uses two hidden HTML audio elements and one
card-local playback controller. It autoplays UK, stops the current clip before
switching accent, records the last selected accent for `R`, and clears visual
state on `ended`, `pause`, `error`, or rejected playback.

The Headword Pronunciation Cluster renders:

- distinct UK/US IPA as two labeled, fully clickable pills;
- a shared IPA once in one pill with two 50/50 controls, UK left and US right;
- no shared-pill accent labels or idle speaker icons;
- a temporary speaker icon and accent tint only on the playing control.

The Example Accent Toggle remains independent, shares the same toolbar row at
the far right, and wraps right-aligned below pronunciation on narrow screens.

## Consequences

- The first 26 EAVM fields and model ID remain unchanged; live import performs
  the append-only two-field migration.
- Canonical build JSONL remains the pronunciation authority and does not gain a
  second manually editable filename source.
- Package/archive/import validation must derive the two media fields identically
  from the canonical sound references.
- The template gains deterministic playback state and keyboard behavior but
  owns more JavaScript than the native replay-button approach.
- A package made with the prior field contract is stale and must be rebuilt
  before live import.
