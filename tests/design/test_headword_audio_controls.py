from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"
STYLING = ROOT / "design" / "EAVM" / "styling.txt"


def test_headword_audio_uses_derived_media_fields_and_autoplays_only_uk():
    template = TEMPLATE.read_text(encoding="utf-8")

    assert 'id="headword-audio-uk" preload="auto" autoplay' in template
    assert '{{#HeadwordAudioUKSrc}}src="{{HeadwordAudioUKSrc}}"' in template
    assert 'id="headword-audio-us" preload="auto"' in template
    assert 'id="headword-audio-us" preload="auto" autoplay' not in template
    assert '{{#HeadwordAudioUSSrc}}src="{{HeadwordAudioUSSrc}}"' in template
    assert "{{AudioUK}}" not in template
    assert "{{AudioUS}}" not in template


def test_equal_ipa_has_two_accessible_half_width_controls_without_idle_labels():
    template = TEMPLATE.read_text(encoding="utf-8")
    styling = STYLING.read_text(encoding="utf-8")

    assert "if (uk && us && uk === us)" in template
    assert "if (!parts.length)" in template
    assert "ukAudio.getAttribute('src') && usAudio.getAttribute('src')" in template
    assert 'class="ipa-zone ipa-zone-uk"' in template
    assert 'class="ipa-zone ipa-zone-us"' in template
    assert 'aria-label="Play UK pronunciation"' in template
    assert 'aria-label="Play US pronunciation"' in template
    assert ".ipa-zone" in styling
    assert "width: 50%;" in styling
    assert ".ipa-zone-uk { left: 0; }" in styling
    assert ".ipa-zone-us { right: 0; }" in styling


def test_distinct_ipa_pills_keep_visible_accent_labels_and_whole_pill_controls():
    template = TEMPLATE.read_text(encoding="utf-8")

    assert 'class="ipa-chip ipa-chip-uk" data-accent="uk"' in template
    assert 'class="ipa-chip ipa-chip-us" data-accent="us"' in template
    assert '<span class="ipa-label">UK</span>' in template
    assert '<span class="ipa-label">US</span>' in template


def test_headword_playback_tracks_real_lifecycle_and_replays_last_accent_with_r():
    template = TEMPLATE.read_text(encoding="utf-8")

    for event in ("playing", "ended", "pause", "error"):
        assert f"audio.addEventListener('{event}'" in template
    assert "lastHeadwordAccent = accent;" in template
    assert "playHeadwordAudio(lastHeadwordAccent);" in template
    assert "event.key.toLowerCase() !== 'r'" in template
    assert "target.tagName === 'INPUT'" in template
    assert "target.tagName === 'TEXTAREA'" in template
    assert "target.isContentEditable" in template


def test_example_toggle_shares_toolbar_row_and_wraps_right_on_mobile():
    template = TEMPLATE.read_text(encoding="utf-8")
    styling = STYLING.read_text(encoding="utf-8")

    toolbar = template.index('id="pronunciation-toolbar"')
    toggle = template.index('id="example-audio-toolbar"')
    meta = template.index('<div class="meta-row">', toolbar)
    assert toolbar < toggle < meta
    assert ".pronunciation-toolbar > .example-audio-toolbar" in styling
    assert "flex-basis: 100%;" in styling
    assert "justify-content: flex-end;" in styling
