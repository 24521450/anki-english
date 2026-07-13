"""Regression tests for always-visible Vietnamese glosses on the back card."""
from pathlib import Path


BACK_TEMPLATE = Path(__file__).resolve().parent.parent.parent / "design" / "EAVM" / "back_template.txt"
STYLING = Path(__file__).resolve().parent.parent.parent / "design" / "EAVM" / "styling.txt"


def test_definition_renders_without_vietnamese_reveal_wrapper():
    src = BACK_TEMPLATE.read_text(encoding="utf-8")

    assert "hideVietnameseGloss" not in src
    assert "vi-reveal" not in src
    assert "Hiện nghĩa Việt" not in src
    assert "'<div class=\"sense-def\">' + parseDef(def) + '</div>'" in src


def test_vietnamese_reveal_css_is_removed():
    css = STYLING.read_text(encoding="utf-8")

    assert ".vi-reveal" not in css
