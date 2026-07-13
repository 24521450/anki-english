from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"
STYLING = ROOT / "design" / "EAVM" / "styling.txt"


def _template() -> str:
    return BACK_TEMPLATE.read_text(encoding="utf-8")


def test_example_audio_fields_are_hidden_inputs_for_manual_controls():
    template = _template()

    for field in (
        "ExampleAudioUK",
        "ExampleAudioUS",
        "IdiomExampleAudioUK",
        "IdiomExampleAudioUS",
    ):
        assert f"{{{{{field}}}}}" in template

    assert "autoplay" not in template.lower()
    assert 'type="button"' in template
    assert 'aria-label="Play UK audio for ' in template
    assert 'aria-label="Play US audio for ' in template


def test_audio_alignment_uses_main_and_idiom_field_grammars():
    template = _template()

    assert "raw.split('|')" in template
    assert "raw.split('$$')" in template
    assert "entries[i].split('|')" in template
    assert "split(/(?:<br\\s*\\/?>){2}/i)" in template


def test_example_audio_is_single_player_and_click_only():
    template = _template()

    assert "addEventListener('click'" in template
    assert "window.__eavmExampleAudio.pause()" in template
    assert "window.__eavmExampleAudio.currentTime = 0" in template
    assert "var player = new Audio(src);" in template
    assert template.index("new Audio(src)") > template.index("addEventListener('click'")


def test_example_audio_controls_have_compact_css():
    css = STYLING.read_text(encoding="utf-8")

    for selector in (
        ".example-line",
        ".example-text",
        ".example-audio-controls",
        ".example-audio-btn",
        ".example-audio-uk",
        ".example-audio-us",
    ):
        assert selector in css
