from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"
STYLING = ROOT / "design" / "EAVM" / "styling.txt"
DESIGN_PREVIEW = ROOT / "design" / "index.html"


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


def _render(cases: list[dict[str, object]]) -> list[str]:
    template = BACK_TEMPLATE.read_text(encoding="utf-8")
    escape_start = template.index("  function escapeHtml(")
    escape_end = template.index("  function extractAudioSource(", escape_start)
    functions = "\n".join(
        [
            _extract_function(template, "trim"),
            template[escape_start:escape_end],
            _extract_function(template, "exampleAudioLine"),
            _extract_function(template, "parseIdiomMeaningVi"),
            _extract_function(template, "renderIdioms"),
        ]
    )
    runner = (
        functions
        + "\nconst cases = "
        + json.dumps(cases, ensure_ascii=False)
        + ";\nprocess.stdout.write(JSON.stringify(cases.map((item) => "
        + "renderIdioms(item.idioms, item.meaningVi, item.uk || [], item.us || []))));"
    )
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "-e", runner],
        env=env,
        timeout=15,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def _idiom_rows(html: str) -> list[str]:
    return html.split('<div class="idiom-row">')[1:]


def test_mixed_modes_keep_phrases_and_preserve_example_audio_alignment():
    [html] = _render(
        [
            {
                "idioms": (
                    "nothing ventured, nothing gained :: taking risks can lead to success :: "
                    "You should try. $$ "
                    "shake/rock the foundations of something | shake/rock something to its foundations "
                    ":: seriously weaken something at its core :: The scandal <em>shook</em> the institution."
                ),
                "meaningVi": (
                    "vi_equivalent :: Không vào hang cọp, sao bắt được cọp con $$ "
                    "bilingual_gloss :: làm lung lay tận gốc"
                ),
                "uk": [["venture-uk.mp3"], ["foundation-uk.mp3"]],
                "us": [["venture-us.mp3"], ["foundation-us.mp3"]],
            }
        ]
    )
    equivalent, bilingual = _idiom_rows(html)

    assert "nothing ventured, nothing gained" in equivalent
    assert "taking risks can lead to success" not in equivalent
    assert 'class="idiom-explanation"' not in equivalent
    assert "Không vào hang cọp, sao bắt được cọp con" in equivalent
    assert 'data-audio-uk="venture-uk.mp3"' in equivalent
    assert 'data-audio-us="venture-us.mp3"' in equivalent

    assert "shake/rock the foundations of something | shake/rock something to its foundations" in bilingual
    assert '<div class="idiom-explanation">seriously weaken something at its core</div>' in bilingual
    assert "làm lung lay tận gốc" in bilingual
    assert "The scandal <em>shook</em> the institution." in bilingual
    assert 'data-audio-uk="foundation-uk.mp3"' in bilingual
    assert 'data-audio-us="foundation-us.mp3"' in bilingual


def test_missing_or_globally_misaligned_metadata_uses_legacy_english_for_every_idiom():
    idioms = "first phrase :: first meaning :: example one $$ second phrase :: second meaning :: example two"
    missing, misaligned = _render(
        [
            {"idioms": idioms, "meaningVi": ""},
            {"idioms": idioms, "meaningVi": "vi_equivalent :: nghĩa thứ nhất"},
        ]
    )

    for html in (missing, misaligned):
        assert html.count('class="idiom-explanation"') == 2
        assert "first meaning" in html
        assert "second meaning" in html
        assert 'class="idiom-vi"' not in html


def test_unknown_or_empty_metadata_cell_falls_back_without_invalidating_valid_siblings():
    unknown, empty = _render(
        [
            {
                "idioms": "first phrase :: first meaning $$ second phrase :: second meaning",
                "meaningVi": "unknown :: nghĩa sai $$ vi_equivalent :: nghĩa hợp lệ",
            },
            {
                "idioms": "first phrase :: first meaning $$ second phrase :: second meaning",
                "meaningVi": "bilingual_gloss :: $$ vi_equivalent :: nghĩa hợp lệ",
            },
        ]
    )

    for html in (unknown, empty):
        first, second = _idiom_rows(html)
        assert '<div class="idiom-explanation">first meaning</div>' in first
        assert 'class="idiom-vi"' not in first
        assert "second meaning" not in second
        assert "nghĩa hợp lệ" in second


def test_phrase_english_and_vietnamese_are_plain_text_but_example_html_is_preserved():
    [html] = _render(
        [
            {
                "idioms": (
                    "safe <b>phrase</b> :: meaning <script>alert(1)</script> :: "
                    "Example keeps <em>reviewed markup</em>."
                ),
                "meaningVi": "bilingual_gloss :: nghĩa <img src=x onerror=alert(2)>",
            }
        ]
    )

    assert "safe &lt;b&gt;phrase&lt;/b&gt;" in html
    assert "meaning &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "nghĩa &lt;img src=x onerror=alert(2)&gt;" in html
    assert "Example keeps <em>reviewed markup</em>." in html
    assert "<script>alert(1)</script>" not in html


def test_template_css_and_preview_expose_the_idiom_translation_contract():
    template = BACK_TEMPLATE.read_text(encoding="utf-8")
    css = STYLING.read_text(encoding="utf-8")
    preview = DESIGN_PREVIEW.read_text(encoding="utf-8")

    assert '<div id="raw-idiom-meaning-vi-back">{{IdiomMeaningVI}}</div>' in template
    for class_name in ("idiom-vi", "idiom-vi-label", "idiom-vi-text"):
        assert f'class="{class_name}"' in template
        assert f".{class_name}" in css
    assert ".sense-vi,\n.idiom-vi" in css
    assert ".sense-vi-label,\n.idiom-vi-label" in css
    assert ".sense-vi-text,\n.idiom-vi-text" in css

    for exact_copy in (
        "nothing ventured, nothing gained",
        "Không vào hang cọp, sao bắt được cọp con",
        "shake/rock the foundations of something | shake/rock something to its foundations",
        "seriously weaken something at its core",
        "làm lung lay tận gốc",
    ):
        assert exact_copy in preview
