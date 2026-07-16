"""Regression coverage for dictionary links in both EAVM templates."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent.parent
DESIGN_PREVIEW = ROOT / "design" / "index.html"
TEMPLATES = [
    ROOT / "design" / "EAVM" / "front_template.txt",
    ROOT / "design" / "EAVM" / "back_template.txt",
]


def _render_pos_chips(template: Path, raw_pos: str, raw_urls: str) -> list[dict[str, object]]:
    text = template.read_text(encoding="utf-8")
    start = text.index("  function renderPosChips")
    end = text.index("\n\n  // 1. POS chips", start)
    function_source = text[start:end]
    runner = f"""
function trim(s) {{ return s ? s.replace(/^\\s+|\\s+$/g, '') : ''; }}
class Element {{
  constructor(tag) {{
    this.tagName = tag;
    this.children = [];
    this.className = '';
    this.href = '';
    this.target = '';
    this.rel = '';
    this.attributes = {{}};
    this._text = '';
  }}
  set textContent(value) {{ this._text = String(value); this.children = []; }}
  get textContent() {{
    return this._text + this.children.map(function(child) {{ return child.textContent; }}).join('');
  }}
  appendChild(child) {{ this.children.push(child); return child; }}
  setAttribute(name, value) {{ this.attributes[name] = value; }}
}}
const document = {{
  createElement: function(tag) {{ return new Element(tag); }},
  createTextNode: function(value) {{ return {{tagName:'#text', textContent:String(value)}}; }}
}};
{function_source}
const container = new Element('div');
container.appendChild(document.createElement('stale'));
renderPosChips(container, {json.dumps(raw_pos)}, {json.dumps(raw_urls)});
function serialize(node) {{
  return {{
    tag: node.tagName,
    className: node.className,
    text: node.textContent,
    href: node.href,
    target: node.target,
    rel: node.rel,
    ariaLabel: node.attributes ? (node.attributes['aria-label'] || '') : '',
    children: node.children ? node.children.map(serialize) : []
  }};
}}
console.log(JSON.stringify(container.children.map(serialize)));
"""
    result = subprocess.run(
        ["node", "-e", runner],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.stem)
def test_torture_pos_chips_open_exact_oxford_entries(template: Path):
    chips = _render_pos_chips(
        template,
        "noun, verb",
        "https://www.oxfordlearnersdictionaries.com/definition/english/torture_1|"
        "https://www.oxfordlearnersdictionaries.com/definition/english/torture_2",
    )

    assert [(chip["tag"], chip["text"], chip["href"]) for chip in chips] == [
        (
            "a",
            "1noun",
            "https://www.oxfordlearnersdictionaries.com/definition/english/torture_1",
        ),
        (
            "a",
            "2verb",
            "https://www.oxfordlearnersdictionaries.com/definition/english/torture_2",
        ),
    ]
    assert [chip["children"][0]["text"] for chip in chips] == ["1", "2"]
    assert all(chip["target"] == "_blank" for chip in chips)
    assert all(chip["rel"] == "noopener noreferrer" for chip in chips)
    assert [chip["ariaLabel"] for chip in chips] == [
        "Open Oxford entry for noun",
        "Open Oxford entry for verb",
    ]


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.stem)
def test_single_pos_is_rebuilt_as_an_unnumbered_link(template: Path):
    chips = _render_pos_chips(
        template,
        "verb",
        "https://www.oxfordlearnersdictionaries.com/definition/english/adhere",
    )

    assert len(chips) == 1
    assert chips[0]["tag"] == "a"
    assert chips[0]["text"] == "verb"
    assert len(chips[0]["children"]) == 1
    assert chips[0]["children"][0]["tag"] == "#text"
    assert chips[0]["children"][0]["text"] == "verb"


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.stem)
@pytest.mark.parametrize(
    ("raw_urls", "expected_tags"),
    [
        ("|https://www.oxfordlearnersdictionaries.com/definition/english/torture_2", ["span", "a"]),
        ("|", ["span", "span"]),
    ],
    ids=["mixed-missing", "all-missing"],
)
def test_missing_pos_urls_remain_numbered_non_links(
    template: Path, raw_urls: str, expected_tags: list[str]
):
    chips = _render_pos_chips(template, "noun / verb", raw_urls)

    assert [chip["tag"] for chip in chips] == expected_tags
    assert [chip["text"] for chip in chips] == ["1noun", "2verb"]
    assert [chip["children"][0]["text"] for chip in chips] == ["1", "2"]
    assert chips[0]["href"] == ""
    assert chips[0]["ariaLabel"] == ""


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.stem)
def test_legacy_comma_and_slash_pos_parsing_is_preserved(template: Path):
    chips = _render_pos_chips(template, "noun / verb, adjective", "||")

    assert [chip["text"] for chip in chips] == ["1noun", "2verb", "3adjective"]
    assert all(chip["tag"] == "span" for chip in chips)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.stem)
def test_headword_uses_cambridge_link_with_plain_text_fallback(template: Path):
    text = template.read_text(encoding="utf-8")

    assert 'href="{{CambridgeURL}}"' in text
    assert 'target="_blank" rel="noopener noreferrer"' in text
    assert 'aria-label="Open headword in Cambridge Dictionary"' in text
    assert "{{^CambridgeURL}}{{Word}}{{/CambridgeURL}}" in text


def test_region_three_has_exact_interactive_torture_fixture():
    text = DESIGN_PREVIEW.read_text(encoding="utf-8")
    start = text.index('<section class="region" id="vung-3">')
    end = text.index("</section>", start)
    region_three = text[start:end]

    assert 'id="dictionary-link-fixture-torture"' in region_three
    assert 'href="https://dictionary.cambridge.org/dictionary/english/torture"' in region_three
    assert (
        'href="https://www.oxfordlearnersdictionaries.com/definition/english/torture_1"'
        in region_three
    )
    assert (
        'href="https://www.oxfordlearnersdictionaries.com/definition/english/torture_2"'
        in region_three
    )
    assert region_three.count('target="_blank" rel="noopener noreferrer"') >= 3
    assert 'aria-label="Open headword in Cambridge Dictionary"' in region_three
    assert 'aria-label="Open Oxford entry for noun"' in region_three
    assert 'aria-label="Open Oxford entry for verb"' in region_three


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.stem)
def test_complete_template_javascript_is_syntactically_valid(template: Path, tmp_path: Path):
    scripts = re.findall(r"<script>(.*?)</script>", template.read_text(encoding="utf-8"), re.DOTALL)
    js_file = tmp_path / f"{template.stem}.js"
    js_file.write_text("\n".join(scripts), encoding="utf-8")

    result = subprocess.run(
        ["node", "--check", str(js_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
