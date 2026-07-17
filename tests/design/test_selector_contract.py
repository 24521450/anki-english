"""Selector Contract checks for EAVM templates.

The drift check guarantees design/index.html and styling.txt match. These tests
cover the other side of the contract: template class names must be backed by
CSS selectors in styling.txt.
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EAVM_DIR = PROJECT_ROOT / "design" / "EAVM"
FRONT_TEMPLATE = EAVM_DIR / "front_template.txt"
BACK_TEMPLATE = EAVM_DIR / "back_template.txt"
PRODUCTION_TEMPLATE = EAVM_DIR / "production_front_template.txt"
STYLING_TXT = EAVM_DIR / "styling.txt"

CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2", "UNCLASSIFIED"}

# Third-party icon classes come from Tabler, not the EAVM CSS.
EXTERNAL_CLASSES = {"ti", "ti-volume", "ti-git-branch", "ti-link", "ti-bookmarks"}

# Dynamic fragments embedded in JS-generated class strings. The concrete values
# are asserted separately via map extraction and CEFR prefix checks.
DYNAMIC_TOKENS = {
    "cefr-badge-{{CEFRLevel}}",
    "divider-{{CEFRLevel}}",
    "registers[t]",
    "pc",
}

CLASS_TOKEN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _template_text() -> str:
    return "\n".join(
        [
            FRONT_TEMPLATE.read_text(encoding="utf-8"),
            BACK_TEMPLATE.read_text(encoding="utf-8"),
            PRODUCTION_TEMPLATE.read_text(encoding="utf-8"),
        ]
    )


def _css_classes() -> set[str]:
    css = STYLING_TXT.read_text(encoding="utf-8")
    return set(re.findall(r"\.([A-Za-z_][A-Za-z0-9_-]*)", css))


def _classes_from_class_attributes(text: str) -> set[str]:
    classes: set[str] = set()
    for match in re.finditer(r'class="([^"]+)"', text):
        classes.update(match.group(1).split())
    return classes


def _classes_from_class_name_assignments(text: str) -> set[str]:
    classes: set[str] = set()
    for match in re.finditer(r"className\s*=\s*'([^']+)'", text):
        classes.update(match.group(1).split())
    return classes


def _classes_from_html_string_literals(text: str) -> set[str]:
    classes: set[str] = set()
    for match in re.finditer(r"'[^']*class=\"([^\"]+)\"[^']*'", text):
        classes.update(match.group(1).split())
    return classes


def _classes_from_js_class_maps(text: str) -> set[str]:
    classes: set[str] = set()

    # corpusMap entries: ['corpus-badge corpus-oxf', 'Oxford 3000'].
    # Scope the scan to that map; other arrays in template JS (for example
    # reviewed spelling variants) are data, not CSS class declarations.
    for map_match in re.finditer(r"corpusMap\s*=\s*\{(.*?)\};", text, re.DOTALL):
        for match in re.finditer(
            r"\['([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+)*)'\s*,",
            map_match.group(1),
        ):
            classes.update(match.group(1).split())

    # registers / posMap entries: 'formal':'rt-amber', 'n':'wf-pos-n'
    for match in re.finditer(r"'[^']+'\s*:\s*'([A-Za-z0-9_-]+)'", text):
        value = match.group(1)
        if value.startswith(("rt-", "wf-pos-")):
            classes.add(value)

    return classes


def _template_classes() -> set[str]:
    text = _template_text()
    classes = set()
    classes.update(_classes_from_class_attributes(text))
    classes.update(_classes_from_class_name_assignments(text))
    classes.update(_classes_from_html_string_literals(text))
    classes.update(_classes_from_js_class_maps(text))
    return {
        cls
        for cls in classes
        if cls
        and cls not in EXTERNAL_CLASSES
        and cls not in DYNAMIC_TOKENS
        and CLASS_TOKEN_RE.match(cls)
        and "{{" not in cls
        and "[" not in cls
        and "]" not in cls
        and "+" not in cls
    }


def test_eavm_template_classes_exist_in_styling():
    """Every static class rendered by EAVM templates has a CSS selector."""
    css_classes = _css_classes()
    template_classes = _template_classes()

    missing = sorted(template_classes - css_classes)

    assert not missing, (
        "EAVM template classes are missing from design/EAVM/styling.txt: "
        + ", ".join(missing)
    )


def test_dynamic_cefr_template_classes_have_all_level_selectors():
    """Mustache CEFR class prefixes must resolve to every supported level."""
    css_classes = _css_classes()

    expected = {
        *(f"cefr-badge-{level}" for level in CEFR_LEVELS),
        *(f"divider-{level}" for level in CEFR_LEVELS),
    }
    missing = sorted(expected - css_classes)

    assert not missing, (
        "Dynamic CEFR template classes are missing CSS selectors: "
        + ", ".join(missing)
    )
