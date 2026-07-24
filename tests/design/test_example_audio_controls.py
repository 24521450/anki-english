from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"
STYLING = ROOT / "design" / "EAVM" / "styling.txt"


def _template() -> str:
    return BACK_TEMPLATE.read_text(encoding="utf-8")


def _extract_function(src: str, func_name: str) -> str:
    match = re.search(rf"function\s+{func_name}\s*\([^)]*\)\s*\{{", src)
    if not match:
        raise ValueError(f"Function {func_name} not found")

    depth = 0
    in_string = None
    escaped = False
    brace_start = match.end() - 1
    for index in range(brace_start, len(src)):
        char = src[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if in_string:
            if char == in_string:
                in_string = None
            continue
        if char in ("'", '"', "`"):
            in_string = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return src[match.start() : index + 1]
    raise ValueError(f"Unmatched braces in function {func_name}")


def _run_node_audio_lifecycle(actions: str) -> list[object]:
    template = _template()
    functions = "\n".join(
        _extract_function(template, name)
        for name in (
            "getExampleAudioSource",
            "clearExampleAudioState",
            "stopExampleAudio",
            "setExampleAudioAccent",
            "playExampleAudio",
            "wireExampleAudio",
        )
    )
    runner = f"""
const makeClassList = () => {{
  const values = new Set();
  return {{
    add: (name) => values.add(name),
    remove: (name) => values.delete(name),
    contains: (name) => values.has(name),
    toggle: (name, force) => force ? values.add(name) : values.delete(name)
  }};
}};
const trigger = {{
  attrs: {{'data-audio-uk': 'uk.mp3', 'data-audio-us': 'us.mp3'}},
  classList: makeClassList(),
  listeners: {{}},
  getAttribute(name) {{ return this.attrs[name] || ''; }},
  addEventListener(name, listener) {{ this.listeners[name] = listener; }},
  click() {{ if (this.listeners.click) this.listeners.click.call(this); }}
}};
const toggle = {{
  classList: makeClassList(),
  attrs: {{'aria-checked': 'false', 'aria-label': 'Example audio accent: UK'}},
  listeners: {{}},
  setAttribute(name, value) {{ this.attrs[name] = value; }},
  addEventListener(name, listener) {{ this.listeners[name] = listener; }}
}};
const accentLabel = {{textContent: 'UK'}};
const toolbar = {{hidden: true}};
global.document = {{
  querySelectorAll(selector) {{
    if (selector === '.example-audio-trigger') return [trigger];
    return [];
  }},
  getElementById(id) {{
    if (id === 'example-audio-toolbar') return toolbar;
    if (id === 'example-accent-toggle') return toggle;
    if (id === 'example-accent-label') return accentLabel;
    return null;
  }}
}};
const players = [];
const playResults = [];
global.Audio = function(src) {{
  this.src = src;
  this.currentTime = 0;
  this.listeners = {{}};
  this.addEventListener = (name, listener) => {{ this.listeners[name] = listener; }};
  this.emit = (name) => {{ if (this.listeners[name]) this.listeners[name](); }};
  this.play = () => playResults.length ? playResults.shift() : Promise.resolve();
  this.pause = () => this.emit('pause');
  players.push(this);
}};
global.window = {{}};
var exampleAudioAccent = 'uk';
var activeExampleAudioTrigger = null;
{functions}
wireExampleAudio();
{actions}
"""
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "-e", runner],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_example_audio_fields_remain_hidden_manual_play_inputs():
    template = _template()

    for field in (
        "ExampleAudioUK",
        "ExampleAudioUS",
        "IdiomExampleAudioUK",
        "IdiomExampleAudioUS",
    ):
        assert f"{{{{{field}}}}}" in template

    assert 'id="headword-audio-uk"' in template
    assert 'id="headword-audio-us"' in template
    assert "autoplay" in template.lower()
    assert 'id="example-audio-toolbar" hidden' in template
    assert 'role="switch" aria-checked="false"' in template
    audio_row = template.index('<div class="pronunciation-toolbar" id="pronunciation-toolbar">')
    toolbar = template.index('id="example-audio-toolbar"')
    assert audio_row < toolbar < template.index('<div class="meta-row">', audio_row)
    assert "Example audio</span>" not in template


def test_accent_control_exposes_one_current_accent_switch():
    template = _template()

    assert 'id="example-accent-toggle" role="switch"' in template
    assert 'aria-checked="false"' in template
    assert 'aria-label="Example audio accent: UK"' in template
    assert template.count('class="example-accent-label"') == 1
    assert '<span class="example-accent-label" id="example-accent-label">UK</span>' in template
    assert 'role="radiogroup"' not in template
    assert 'role="radio"' not in template
    assert 'class="example-accent-option' not in template


def test_single_switch_toggles_label_state_and_selected_audio_source():
    states = _run_node_audio_lifecycle(
        """
const initial = [accentLabel.textContent, toggle.attrs['aria-checked'], toggle.classList.contains('is-us')];
toggle.listeners.click.call(toggle);
const selectedUs = [accentLabel.textContent, toggle.attrs['aria-checked'], toggle.classList.contains('is-us')];
trigger.listeners.click.call(trigger);
const usSource = players[0].src;
players[0].emit('playing');
toggle.listeners.click.call(toggle);
const selectedUk = [accentLabel.textContent, toggle.attrs['aria-checked'], toggle.classList.contains('is-us')];
console.log(JSON.stringify([initial, selectedUs, usSource, selectedUk, window.__eavmExampleAudio]));
"""
    )

    assert states == [
        ["UK", "false", False],
        ["US", "true", True],
        "us.mp3",
        ["UK", "false", False],
        None,
    ]


def test_single_switch_has_one_sliding_labeled_thumb():
    css = STYLING.read_text(encoding="utf-8")

    audio_row = re.search(r"\.pronunciation-toolbar\s*\{([^}]*)\}", css, re.DOTALL)
    toggle = re.search(r"\.example-accent-toggle\s*\{([^}]*)\}", css, re.DOTALL)
    label = re.search(r"\.example-accent-label\s*\{([^}]*)\}", css, re.DOTALL)

    assert audio_row is not None
    assert "padding: 0 84px;" in audio_row.group(1)
    assert toggle is not None
    assert "width: 70px;" in toggle.group(1)
    assert "height: 32px;" in toggle.group(1)
    assert "box-sizing: border-box;" in toggle.group(1)
    assert label is not None
    assert "width: 30px;" in label.group(1)
    assert "height: 24px;" in label.group(1)
    assert "transition: transform 150ms ease;" in label.group(1)
    assert ".example-accent-toggle.is-us .example-accent-label { transform: translateX(34px); }" in css
    assert "grid-template-rows" not in toggle.group(1)
    assert ".example-accent-option" not in css
    assert ".example-accent-label { transition: none; }" in css


def test_whole_example_sentence_is_the_audio_trigger():
    template = _template()

    assert "function exampleAudioLine(" in template
    assert 'class="example-line example-audio-trigger"' in template
    assert 'class="idiom-example example-line example-audio-trigger"' in template
    assert 'role="button" tabindex="0"' in template
    assert '<button type="button" class="example-line example-audio-trigger"' not in template
    assert '<button type="button" class="idiom-example example-line example-audio-trigger"' not in template
    assert 'data-audio-uk="' in template
    assert 'data-audio-us="' in template
    assert "exampleAudioLine('\\u201c' + exLine" in template
    assert "'idiom-example'" in template
    assert "example-audio-btn" not in template
    assert "exampleAudioControls" not in template


def test_example_audio_trigger_supports_keyboard_activation():
    states = _run_node_audio_lifecycle(
        """
let prevented = false;
trigger.listeners.keydown.call(trigger, {key: ' ', preventDefault() { prevented = true; }});
const spaceSource = players[0].src;
trigger.listeners.keydown.call(trigger, {key: 'Escape', preventDefault() { throw new Error('unexpected'); }});
const afterEscape = players.length;
trigger.listeners.keydown.call(trigger, {key: 'Enter', preventDefault() {}});
console.log(JSON.stringify([prevented, spaceSource, afterEscape, players.length]));
"""
    )

    assert states == [True, "uk.mp3", 1, 2]


def test_audio_alignment_uses_main_and_idiom_field_grammars():
    template = _template()

    assert "raw.split('|')" in template
    assert "raw.split('$$')" in template
    assert "entries[i].split('|')" in template
    assert "split(/(?:<br\\s*\\/?>){2}/i)" in template


def test_accent_is_card_local_defaults_to_uk_and_is_not_persisted():
    template = _template()

    assert "var exampleAudioAccent = 'uk';" in template
    assert "setExampleAudioAccent('uk');" in template
    assert "localStorage" not in template
    assert "sessionStorage" not in template
    assert "accent !== 'uk' && accent !== 'us'" in template
    assert "toggle.classList.toggle('is-us', isUs)" in template
    assert "toggle.setAttribute('aria-checked', isUs ? 'true' : 'false')" in template
    assert "label.textContent = accent.toUpperCase()" in template


def test_toolbar_only_appears_when_an_audio_trigger_exists():
    template = _template()

    no_triggers = template.index("if (!triggers.length) return;")
    reveal = template.index("toolbar.hidden = false")
    assert no_triggers < reveal


def test_example_audio_is_single_player_and_switch_stops_playback():
    template = _template()

    assert "function stopExampleAudio()" in template
    assert "player.pause()" in template
    assert "player.currentTime = 0" in template
    assert "window.__eavmExampleAudio = null" in template
    assert template.index("stopExampleAudio();", template.index("function setExampleAudioAccent")) < template.index(
        "exampleAudioAccent = accent"
    )
    assert "var src = getExampleAudioSource(this, exampleAudioAccent);" in template
    assert "var player = new Audio(src);" in template
    assert "playExampleAudio(this, src);" in template


def test_playing_color_follows_audio_start_and_end_events():
    states = _run_node_audio_lifecycle(
        """
trigger.listeners.click.call(trigger);
const beforePlaying = trigger.classList.contains('is-playing');
players[0].emit('playing');
const whilePlaying = trigger.classList.contains('is-playing');
players[0].emit('ended');
const afterEnded = trigger.classList.contains('is-playing');
console.log(JSON.stringify([beforePlaying, whilePlaying, afterEnded]));
"""
    )

    assert states == [False, True, False]


def test_pause_and_error_restore_the_normal_example_color():
    states = _run_node_audio_lifecycle(
        """
trigger.listeners.click.call(trigger);
players[0].emit('playing');
players[0].emit('pause');
const afterPause = trigger.classList.contains('is-playing');
trigger.listeners.click.call(trigger);
players[1].emit('playing');
players[1].emit('error');
const afterError = trigger.classList.contains('is-playing');
console.log(JSON.stringify([afterPause, afterError]));
"""
    )

    assert states == [False, False]


def test_repeated_click_restarts_and_stale_events_do_not_clear_new_playback():
    states = _run_node_audio_lifecycle(
        """
trigger.listeners.click.call(trigger);
players[0].emit('playing');
trigger.listeners.click.call(trigger);
const afterRestartClick = trigger.classList.contains('is-playing');
players[1].emit('playing');
players[0].emit('ended');
const afterStaleEnd = trigger.classList.contains('is-playing');
console.log(JSON.stringify([players.length, players[0].src, players[1].src, afterRestartClick, afterStaleEnd]));
"""
    )

    assert states == [2, "uk.mp3", "uk.mp3", False, True]


def test_rejected_play_request_clears_the_active_player():
    states = _run_node_audio_lifecycle(
        """
playResults.push(Promise.reject(new Error('blocked')));
trigger.listeners.click.call(trigger);
setImmediate(() => console.log(JSON.stringify([
  window.__eavmExampleAudio === null,
  trigger.classList.contains('is-playing')
])));
"""
    )

    assert states == [True, False]


def test_selected_accent_source_has_no_cross_accent_fallback():
    function_js = _extract_function(_template(), "getExampleAudioSource")
    attributes = {"data-audio-uk": "uk.mp3", "data-audio-us": "us.mp3"}
    runner = f"""
{function_js}
const attrs = {json.dumps(attributes)};
const trigger = {{ getAttribute: (name) => attrs[name] || '' }};
console.log(JSON.stringify([
  getExampleAudioSource(trigger, 'uk'),
  getExampleAudioSource(trigger, 'us'),
  getExampleAudioSource(trigger, 'ca')
]));
"""
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "-e", runner],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == ["uk.mp3", "us.mp3", ""]


def test_complete_back_template_javascript_is_syntactically_valid(tmp_path):
    match = re.search(r"<script>\s*(.*?)\s*</script>", _template(), re.DOTALL)
    assert match is not None
    js_file = tmp_path / "back_template.js"
    js_file.write_text(match.group(1), encoding="utf-8")

    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "--check", str(js_file)],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0


def test_example_audio_controls_have_global_toggle_and_invisible_trigger_css():
    css = STYLING.read_text(encoding="utf-8")

    for selector in (
        ".example-line",
        ".example-text",
        ".example-audio-toolbar",
        ".example-accent-toggle",
        ".example-accent-label",
        ".example-audio-trigger",
    ):
        assert selector in css

    assert ".example-audio-toolbar[hidden] { display: none; }" in css
    audio_row = re.search(r"\.pronunciation-toolbar\s*\{([^}]*)\}", css, re.DOTALL)
    assert audio_row is not None
    assert "position: relative;" in audio_row.group(1)
    toolbar = re.search(r"\.pronunciation-toolbar > \.example-audio-toolbar\s*\{([^}]*)\}", css, re.DOTALL)
    assert toolbar is not None
    assert "position: absolute;" in toolbar.group(1)
    assert "right: 0;" in toolbar.group(1)

    assert ".example-accent-option" not in css
    assert ".example-audio-trigger:hover" not in css
    assert "cursor: pointer;" in css
    trigger = re.search(r"\.example-audio-trigger\s*\{([^}]*)\}", css, re.DOTALL)
    assert trigger is not None
    assert "display: block;" in trigger.group(1)


def test_main_example_font_size_matches_definition():
    css = STYLING.read_text(encoding="utf-8")

    definition = re.search(r"\.sense-def\s*\{[^}]*font-size:\s*([^;]+);", css, re.DOTALL)
    example = re.search(r"\.sense-ex\s*\{[^}]*font-size:\s*([^;]+);", css, re.DOTALL)

    assert definition is not None
    assert example is not None
    assert definition.group(1) == "15.5px"
    assert example.group(1) == definition.group(1)
    trigger = re.search(r"\.example-audio-trigger\s*\{([^}]*)\}", css, re.DOTALL)
    assert trigger is not None
    assert "font-size: inherit;" in trigger.group(1)


def test_playing_example_uses_the_card_cefr_color_without_hover_color():
    template = _template()
    css = STYLING.read_text(encoding="utf-8")

    assert '<div class="anki-card-container" data-cefr="{{CEFRLevel}}">' in template
    expected_colors = {
        "A1": "#5eead4",
        "A2": "#67e8f9",
        "B1": "#93c5fd",
        "B2": "#c4b5fd",
        "C1": "#fcd34d",
        "C2": "#fda4af",
        "UNCLASSIFIED": "#c4c7c7",
    }
    for level, color in expected_colors.items():
        assert (
            f'.anki-card-container[data-cefr="{level}"] '
            f"{{--example-playing-color: {color};}}"
        ) in css

    assert ".example-audio-trigger.is-playing" in css
    assert ".example-audio-trigger.is-playing .example-text *" in css
    assert "color: var(--example-playing-color);" in css
    assert "transition: color 120ms ease;" in css
    assert ".example-audio-trigger .example-text * { transition: color 120ms ease; }" in css
    assert ".example-audio-trigger:hover" not in css

    word_highlight = re.search(r"\.word-highlight\s*\{([^}]*)\}", css, re.DOTALL)
    assert word_highlight is not None
    assert "text-decoration: underline;" in word_highlight.group(1)
    assert "text-decoration-color: rgba(167, 139, 250, 0.45);" in word_highlight.group(1)
    assert ".example-audio-trigger { transition: none; }" in css
    assert ".example-audio-trigger .example-text * { transition: none; }" in css
