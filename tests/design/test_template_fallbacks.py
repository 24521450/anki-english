from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK = ROOT / "design" / "EAVM" / "back_template.txt"
PRODUCTION = ROOT / "design" / "EAVM" / "production_front_template.txt"


def _before_script(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("<script>", 1)[0]


def test_recognition_senses_have_a_readable_definition_example_fallback():
    source = _before_script(BACK)

    match = re.search(
        r'<div class="section-box senses-box" id="senses-container">(.*?)</div>\s*'
        r'\{\{/Definition\}\}',
        source,
        re.DOTALL,
    )
    assert match is not None
    fallback = match.group(1)
    assert "{{Definition}}" in fallback
    assert "{{Example}}" in fallback


def test_production_has_no_visible_fallback_before_the_script_masks_the_cue():
    source = _before_script(PRODUCTION)

    match = re.search(
        r'<div class="production-senses" id="production-senses"[^>]*>(.*?)</div>\s*'
        r'</div>\s*</div>\s*\n\s*<div class="production-type-shell">',
        source,
        re.DOTALL,
    )
    assert match is not None
    fallback = match.group(1)
    assert not fallback.strip()
    assert "{{DefinitionVI}}" not in fallback
    assert "{{Example}}" not in fallback
