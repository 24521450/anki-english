"""Regression tests for the Vietnamese-gloss hiding rule in back_template.txt.

The back template JS hides the trailing parenthesis of every Definition chunk
behind a "Hiện nghĩa Việt" button. The rule is **structural** — we wrap any
non-empty trailing paren, regardless of whether the contents contain diacritic
characters. Parens in the middle of a chunk are left untouched.

We replicate the JS regex and replace callback in Python so we can assert on
the output HTML without needing a JS runtime. The implementation in
`design/EAVM/back_template.txt` must stay in sync with `apply_hide_vietnamese`
below.
"""
from __future__ import annotations

import re
from pathlib import Path

BACK_TEMPLATE = Path(__file__).resolve().parent.parent.parent / "design" / "EAVM" / "back_template.txt"

# Mirrors the regex in back_template.txt line ~147.
TRAILING_PAREN_RE = re.compile(r"\s*\(([^()]*)\)\s*$")

# Mirrors the JS replace callback in back_template.txt (hideVietnameseGloss).
def apply_hide_vietnamese(html: str) -> str:
    return TRAILING_PAREN_RE.sub(
        lambda m: (' <button type="button" class="vi-reveal" '
                   "onclick=\"this.className+=' is-open'; this.disabled=true;\">"
                   '<span class="vi-reveal-label">Hiện nghĩa Việt</span>'
                   '<span class="vi-reveal-text">('
                   + (m.group(1).strip())
                   + ')</span></button>')
        if m.group(1).strip()
        else m.group(0),
        html,
    )


def test_liver_ascii_gloss_is_hidden():
    """Acceptance: `liver organ or meat (gan)` shows the reveal button."""
    out = apply_hide_vietnamese("liver organ or meat (gan)")
    assert "vi-reveal" in out
    assert "(gan)" in out  # text still present in DOM
    assert "Hiện nghĩa Việt" in out
    # The English portion stays untouched
    assert out.startswith("liver organ or meat ")


def test_diacritic_gloss_still_hidden():
    """A diacritic-rich Vietnamese gloss like `(đặc điểm)` must still be hidden."""
    out = apply_hide_vietnamese("low-pH chemical (đặc điểm)")
    assert "vi-reveal" in out
    assert "(đặc điểm)" in out
    assert out.startswith("low-pH chemical ")


def test_definition_without_parens_is_untouched():
    """A def with no trailing paren must pass through unchanged."""
    plain = "relating to the belly area"
    assert apply_hide_vietnamese(plain) == plain


def test_mid_sentence_english_paren_is_preserved():
    """A parenthetical English clarification in the middle of a chunk is NOT
    treated as a Vietnamese gloss and must not be wrapped.

    The regex anchors on end-of-string (`$`), so this is structural: only the
    final paren is wrapped. The phrase `(about)` mid-sentence must survive
    intact and not appear inside a `vi-reveal` button.
    """
    chunk = "talking (about) something far away"
    out = apply_hide_vietnamese(chunk)
    # The mid-sentence "(about)" survives untouched
    assert "(about)" in out
    # And it must NOT be inside a reveal button
    assert "vi-reveal-text\">(about)" not in out
    # The trailing "something far away" was not a paren either
    assert out == chunk


def test_empty_trailing_paren_passes_through():
    """An empty `()` at the end must not get wrapped — there's nothing to reveal."""
    chunk = "relating to the belly area ()"
    out = apply_hide_vietnamese(chunk)
    assert "vi-reveal" not in out
    assert out == chunk


def test_regex_matches_back_template_source():
    """The Python regex must mirror the regex in back_template.txt exactly.

    A drift between the two would silently break the rule for live cards
    (Python tests pass, JS still uses old rule). This guards against that.
    """
    src = BACK_TEMPLATE.read_text(encoding="utf-8")
    # Find the literal pattern in the JS source
    expected = r"/\s*\(([^()]*)\)\s*$/g"
    assert expected in src, (
        "back_template.txt is missing the trailing-paren regex; "
        "the structural rule and the test would drift."
    )


def test_has_vietnamese_chars_function_removed():
    """The diacritic-detection heuristic must be gone from the template."""
    src = BACK_TEMPLATE.read_text(encoding="utf-8")
    assert "hasVietnameseChars" not in src, (
        "hasVietnameseChars was the diacritic-based detector; it must be "
        "removed now that the rule is structural."
    )