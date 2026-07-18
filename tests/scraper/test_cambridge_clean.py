"""Tests for clean see_also + collocations + examples in Cambridge parser.

These tests verify the parser correctly:
  1. Strips artifact words ("Synonyms", "formal", "UK") from see_also
  2. Drops grammar-blob xref blocks (no usable headwords)
  3. Extracts collocations from <span class="lu dlu"> in <span class="dexamp">
  4. Strips collocation prefix from example text (only full sentences remain)

Golden fixture: cambridge_violation.html (real cache file).
"""
from __future__ import annotations

import pytest  # noqa: E402
from lxml import html as lxml_html  # noqa: E402

from src.scraper.cambridge import _extract_see_also, parse_cambridge  # noqa: E402
from tools import ci_hydrate_parser_fixtures as fixture_catalog  # noqa: E402


@pytest.fixture(scope="module")
def violation_record():
    """Parse cambridge_violation.html — has Synonyms header + colloc+example merged."""
    fixture = fixture_catalog.special_fixture("cambridge-violation-cleaning")
    raw = fixture_catalog.special_fixture_path(fixture["id"]).read_bytes()
    return parse_cambridge(raw, source_files=[fixture["filename"]])


# -----------------------------------------------------------------------------
# Test 1: see_also strips artifacts
# -----------------------------------------------------------------------------

def test_see_also_strips_artifacts(violation_record):
    """After fix, see_also must not contain 'Synonyms' or 'UK' or 'formal'."""
    see_also = violation_record.get("see_also", [])
    # Spec expectation: ["infraction", "misdemeanour"]
    assert "Synonyms" not in see_also, f"see_also contains 'Synonyms' header: {see_also}"
    assert "UK" not in see_also, f"see_also contains 'UK' register label: {see_also}"
    assert "formal" not in see_also, f"see_also contains 'formal' register label: {see_also}"
    # Real entries should be present
    assert "infraction" in see_also
    assert "misdemeanour" in see_also


# -----------------------------------------------------------------------------
# Test 2: see_also drops grammar blob
# -----------------------------------------------------------------------------

def test_see_also_drops_grammar_blob():
    """Grammar xrefs are excluded while semantic xrefs remain."""
    tree = lxml_html.fromstring(
        b"""
        <div>
          <div class="xref grammar"><span class="x-h dx-h">Be about to</span></div>
          <div class="xref synonyms"><span class="x-h dx-h">capable</span></div>
        </div>
        """
    )

    assert _extract_see_also(tree) == ["capable"]


# -----------------------------------------------------------------------------
# Test 3: collocations extracted from .lu dlu spans
# -----------------------------------------------------------------------------

def test_collocations_extracted_from_cl_spans(violation_record):
    """violation sense 1 should have a populated collocations dict, NOT empty.

    Spec expected: {"collocations": ["flagrant violation", "code violation",
                                       "traffic violation", "blatant violation",
                                       "serious violation", "human rights violation",
                                       "civil rights violation"]}
    """
    sense_1 = violation_record["pos_data"][0]["definitions"][0]
    collocs = sense_1.get("collocations", {})
    # Must be non-empty
    assert collocs, f"collocations dict is empty for violation sense 1"
    # Must have a 'collocations' key
    assert "collocations" in collocs, f"Missing 'collocations' key: {collocs}"
    # flagrant violation must be present
    assert "flagrant violation" in collocs["collocations"], \
        f"'flagrant violation' missing from collocations: {collocs['collocations']}"
    # At least 3 collocations extracted
    assert len(collocs["collocations"]) >= 3, \
        f"Too few collocations extracted: {len(collocs['collocations'])}"


# -----------------------------------------------------------------------------
# Test 4: examples stripped of collocation prefix
# -----------------------------------------------------------------------------

def test_examples_stripped_of_colloc_prefix(violation_record):
    """Examples must be full sentences, NOT "<colloc> <sentence>".

    Bare collocation entries (e.g. "blatant violation" with no example sentence)
    should be EXCLUDED entirely (they're captured in collocations, not examples).
    """
    sense_1 = violation_record["pos_data"][0]["definitions"][0]
    examples = sense_1.get("examples", [])
    assert examples, "examples list is empty"

    # Heuristic: no example should start with a known collocation phrase
    # followed by a Capitalized sentence
    collocs = sense_1.get("collocations", {}).get("collocations", [])

    for ex in examples:
        text = ex.get("text") or ""
        # Skip empty/short
        if not text or len(text) < 20:
            continue
        # Check if example starts with a collocation phrase
        for cl in collocs:
            if text.startswith(cl + " "):
                # Find what comes after the collocation prefix
                rest = text[len(cl):].strip()
                # If rest starts with a Capital letter, it's likely "<colloc> <Sentence>"
                if rest and rest[0].isupper():
                    pytest.fail(
                        f"Example starts with collocation prefix '{cl}' followed by "
                        f"Capitalized text. Example: {text[:80]!r}"
                    )
        # Also check for pattern "violation of" / "in violation of" — grammar frame
        if text.startswith("violation of ") or text.startswith("in violation of "):
            pytest.fail(
                f"Example contains grammar frame as prefix: {text[:80]!r}"
            )
