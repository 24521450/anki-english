"""Regression tests for always-visible Vietnamese glosses on the back card."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"
STYLING = ROOT / "design" / "EAVM" / "styling.txt"


def _extract_function(src: str, func_name: str) -> str:
    match = re.search(rf"function\s+{func_name}\s*\([^)]*\)\s*\{{", src)
    if not match:
        raise ValueError(f"Function {func_name} not found")
    depth = 0
    in_string = None
    escaped = False
    for index in range(match.end() - 1, len(src)):
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


def _split(cases: list[str]) -> list[dict[str, str]]:
    template = BACK_TEMPLATE.read_text(encoding="utf-8")
    functions = "\n".join(
        _extract_function(template, name)
        for name in ("trim", "splitDefinitionGloss")
    )
    runner = (
        functions
        + "\nconst cases = "
        + json.dumps(cases)
        + ";\nprocess.stdout.write(JSON.stringify(cases.map(splitDefinitionGloss)));"
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


def test_definition_vi_is_appended_and_rendered_as_an_always_visible_line():
    src = BACK_TEMPLATE.read_text(encoding="utf-8")

    assert '<div id="raw-definition-vi-back">{{DefinitionVI}}</div>' in src
    assert "hideVietnameseGloss" not in src
    assert "vi-reveal" not in src
    for class_name in ("sense-en", "sense-vi", "sense-vi-label", "sense-vi-text"):
        assert f'class="{class_name}"' in src
    assert 'lang="vi"' in src


def test_legacy_combined_definition_fallback_handles_nested_parentheses():
    assert _split([
        "officially end a law or system (bãi bỏ)",
        "death (the grave) (cái chết (the grave))",
        "plain English only",
        "empty gloss ()",
    ]) == [
        {"en": "officially end a law or system", "vi": "bãi bỏ"},
        {"en": "death (the grave)", "vi": "cái chết (the grave)"},
        {"en": "plain English only", "vi": ""},
        {"en": "empty gloss ()", "vi": ""},
    ]


def test_vietnamese_gloss_has_distinct_production_css():
    css = STYLING.read_text(encoding="utf-8")

    assert ".vi-reveal" not in css
    for selector in (".sense-en", ".sense-vi", ".sense-vi-label", ".sense-vi-text"):
        assert selector in css
