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


def _render_collocations(cases: list[str]) -> list[str]:
    template = _template()
    match = re.search(
        r"// 6\. Collocations chips\s*(.*?)\s*// 7\. Feature tags",
        template,
        re.DOTALL,
    )
    assert match is not None

    runner = f"""
function trim(s) {{ return s ? s.replace(/^\\s+|\\s+$/g, '') : ''; }}
const cases = {json.dumps(cases)};
const rendered = cases.map(raw => {{
  const container = {{innerHTML: raw}};
  function getRaw() {{ return raw; }}
  const document = {{getElementById() {{ return container; }}}};
  {match.group(1)}
  return container.innerHTML;
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
    assert _render_collocations(
        [
            "critical factor",
            "critical factor | play a role || ",
        ]
    ) == [
        '<span class="collocation-chip">critical factor</span>',
        (
            '<span class="collocation-chip">critical factor</span>'
            '<span class="collocation-chip">play a role</span>'
        ),
    ]
