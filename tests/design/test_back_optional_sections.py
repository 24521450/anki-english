from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"


def _template() -> str:
    return BACK_TEMPLATE.read_text(encoding="utf-8")


def _extract_function(source: str, name: str) -> str:
    match = re.search(rf"function\s+{name}\s*\([^)]*\)\s*\{{", source)
    assert match is not None

    depth = 0
    quote = None
    escaped = False
    for index in range(match.end() - 1, len(source)):
        char = source[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unmatched braces in {name}")


def _render_optional_sections(fields: dict[str, str]) -> str:
    rendered = _template()
    for field, value in fields.items():
        pattern = re.compile(
            rf"\{{\{{#{re.escape(field)}\}}\}}(.*?)"
            rf"\{{\{{/{re.escape(field)}\}}\}}",
            re.DOTALL,
        )
        rendered = pattern.sub(lambda match: match.group(1) if value else "", rendered)
        rendered = rendered.replace(f"{{{{{field}}}}}", value)
    return rendered


def _render_collocations(cases: list[dict[str, str]]) -> list[dict[str, object]]:
    template = _template()
    functions = "\n".join(
        _extract_function(template, name)
        for name in (
            "trim",
            "collocationSourceMeta",
            "parseCollocationItems",
            "renderCollocations",
        )
    )
    runner = functions + f"""
function escapeHtml(value) {{
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/\"/g, '&quot;');
}}
function TextNode(value) {{ this.value = String(value); }}
function Element(tagName) {{
  this.tagName = tagName;
  this.className = '';
  this.attributes = {{}};
  this.children = [];
}}
Element.prototype.setAttribute = function(name, value) {{ this.attributes[name] = String(value); }};
Element.prototype.appendChild = function(child) {{ this.children.push(child); return child; }};
Object.defineProperty(Element.prototype, 'textContent', {{
  set: function(value) {{
    this.children = [];
    if (value) this.children.push(new TextNode(value));
  }}
}});
function serialize(node) {{
  if (node instanceof TextNode) return escapeHtml(node.value);
  var attrs = node.className ? ' class="' + escapeHtml(node.className) + '"' : '';
  var names = Object.keys(node.attributes);
  for (var i = 0; i < names.length; i++) {{
    attrs += ' ' + names[i] + '="' + escapeHtml(node.attributes[names[i]]) + '"';
  }}
  var children = '';
  for (var j = 0; j < node.children.length; j++) children += serialize(node.children[j]);
  return '<' + node.tagName + attrs + '>' + children + '</' + node.tagName + '>';
}}
const document = {{
  createElement: function(tagName) {{ return new Element(tagName); }},
  createTextNode: function(value) {{ return new TextNode(value); }}
}};
const cases = {json.dumps(cases)};
const rendered = cases.map(item => {{
  const container = new Element('div');
  renderCollocations(item.collocations, item.sources, container);
  return {{
    html: container.children.map(serialize).join(''),
    role: container.attributes.role,
    ariaLabel: container.attributes['aria-label']
  }};
}});
process.stdout.write(JSON.stringify(rendered));
"""
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "-e", runner],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def test_idiom_only_note_omits_the_empty_senses_box():
    rendered = _render_optional_sections(
        {
            "Definition": "",
            "WordFamily": "",
            "Collocations": "",
            "Idioms": "in accordance with :: following a rule",
        }
    )

    assert 'id="senses-container"' not in rendered
    assert 'id="idioms-section"' in rendered


def test_every_non_empty_collocation_renders_as_a_chip():
    rendered = _render_collocations(
        [
            {"collocations": "critical factor", "sources": "curated"},
            {
                "collocations": "on the curriculum|in the curriculum|curriculum development",
                "sources": "oxford|oxford|curated",
            },
        ]
    )

    assert rendered[0] == {
        "html": '<span class="collocation-chip" role="listitem">critical factor</span>',
        "role": "list",
        "ariaLabel": "Collocations",
    }
    curriculum = rendered[1]["html"]
    assert curriculum.count('class="collocation-chip collocation-chip-source-backed"') == 2
    assert curriculum.count('class="collocation-source-marker" aria-hidden="true">OXF</span>') == 2
    assert 'aria-label="on the curriculum; source: Oxford Dictionary"' in curriculum
    assert '<span class="collocation-chip" role="listitem">curriculum development</span>' in curriculum


def test_invalid_source_metadata_falls_back_all_chips_to_curated_style():
    cases = [
        {"collocations": "first phrase|second phrase", "sources": ""},
        {"collocations": "first phrase|second phrase", "sources": "oxford"},
        {"collocations": "first phrase|second phrase", "sources": "oxford|unknown"},
        {"collocations": "first phrase||second phrase", "sources": "oxford|curated|cambridge"},
    ]

    for rendered in _render_collocations(cases):
        html = rendered["html"]
        assert "collocation-chip-source-backed" not in html
        assert "collocation-source-marker" not in html
        assert html.count('class="collocation-chip"') == 2


def test_source_markers_cover_both_dictionaries_and_text_is_not_html():
    [rendered] = _render_collocations(
        [
            {
                "collocations": "Cambridge <img src=x>|both sources",
                "sources": "cambridge|oxford+cambridge",
            }
        ]
    )
    html = rendered["html"]

    assert "Cambridge &lt;img src=x&gt;" in html
    assert "<img src=x>" not in html
    assert '>CAM</span>' in html
    assert '>OXF+CAM</span>' in html
    assert "source: Cambridge Dictionary" in html
    assert "source: Oxford and Cambridge dictionaries" in html
