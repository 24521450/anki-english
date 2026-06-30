"""Tests for clean see_also + collocations + examples in Cambridge parser.

These tests verify the parser correctly:
  1. Strips artifact words ("Synonyms", "formal", "UK") from see_also
  2. Drops grammar-blob xref blocks (no usable headwords)
  3. Extracts collocations from <span class="lu dlu"> in <span class="dexamp">
  4. Strips collocation prefix from example text (only full sentences remain)

Golden fixture: cambridge_violation.html (real cache file).
"""
from __future__ import annotations

import os
import sys

from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, PROJECT_ROOT)

import pytest  # noqa: E402

from src.scraper.cambridge import parse_cambridge  # noqa: E402

CAMBRIDGE_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "cambridge")
VIOLATION_FILE = os.path.join(CAMBRIDGE_DIR, "cambridge_violation.html")


@pytest.fixture(scope="module")
def violation_record():
    """Parse cambridge_violation.html — has Synonyms header + colloc+example merged."""
    with open(VIOLATION_FILE, "rb") as f:
        raw = f.read()
    return parse_cambridge(raw, source_files=["cambridge_violation.html"])


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
    """When xref block is a grammar pattern (no real headwords), see_also should be empty for that block.

    We scan all Cambridge files and check that .xref.grammar blocks do not
    contribute any words to see_also. We verify by parsing + checking that none
    of the words appearing in .xref.grammar blocks leak into see_also.

    Note: words that happen to be both grammar terms AND real headwords (e.g.
    'progressive' as a synonym) are still legitimate see_also entries when
    they come from non-grammar blocks.
    """
    # Sample from 100 files to keep test fast
    files = sorted(os.listdir(CAMBRIDGE_DIR))[:100]
    leaked = []
    for fn in files:
        path = os.path.join(CAMBRIDGE_DIR, fn)
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except Exception:
            continue
        rec = parse_cambridge(raw, source_files=[fn])

        # Re-parse to find words from .xref.grammar blocks specifically
        from lxml import html as lxml_html
        tree = lxml_html.fromstring(raw)
        grammar_words = set()
        for x in tree.cssselect('.xref.grammar'):
            for hw in x.cssselect('.x-h.dx-h'):
                if hw.text_content().strip():
                    grammar_words.add(hw.text_content().strip())

        # Check that none of the grammar words appear in see_also
        for w in rec.get("see_also", []):
            if w in grammar_words:
                leaked.append((fn, w))
                if len(leaked) >= 5:
                    break
        if len(leaked) >= 5:
            break

    assert not leaked, f"Words from .xref.grammar blocks leaked into see_also: {leaked}"


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
