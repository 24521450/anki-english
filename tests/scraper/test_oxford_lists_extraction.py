"""Tests for _extract_oxford_lists — Oxford 3000/5000 list membership.

The Oxford HTML page-top badge for list membership is a span inside a .symbols div:
  <div class="symbols">
    <a href="?list=ox3000&level=a1">
      <span class="ox3ksym_a1"> </span>
    </a>
    <a href="?list=ox5000&level=c1">
      <span class="ox5ksym_c1"> </span>
    </a>
  </div>

The current scraper (src/scraper/oxford.py:128) only checks `sense.get("ox3000")` /
`sense.get("ox5000")` on <li class="sense"> elements — but those attributes are not
the list membership signal in current Oxford HTML. The real signal is the .ox3ksym /
.ox5ksym span classes (which the .oxford_badge extractor already uses correctly).

This test was written to document the bug, then drives the fix.
"""
import pytest
import lxml.html as lxml_html
from src.scraper.oxford import _extract_oxford_lists, _extract_oxford_badge


def _parse(html: str):
    return lxml_html.fromstring(html)


class TestExtractOxfordLists:
    """Pure: feed HTML, get back list of list names."""

    def test_oxford_5000_via_ox5ksym_span(self):
        """HTML with .ox5ksym span -> returns ['Oxford 5000']."""
        html = """<html><body>
            <h1 class="headword">abolish</h1>
            <div class="symbols">
                <a href="?list=ox5000&level=c1">
                    <span class="ox5ksym_c1"> </span>
                </a>
            </div>
            <ol class="senses_multiple"></ol>
        </body></html>"""
        root = _parse(html)
        result = _extract_oxford_lists(root)
        assert 'Oxford 5000' in result

    def test_oxford_3000_via_ox3ksym_span(self):
        """HTML with .ox3ksym span -> returns ['Oxford 3000']."""
        html = """<html><body>
            <h1 class="headword">committee</h1>
            <div class="symbols">
                <a href="?list=ox3000&level=b1">
                    <span class="ox3ksym_b1"> </span>
                </a>
            </div>
            <ol class="senses_multiple"></ol>
        </body></html>"""
        root = _parse(html)
        result = _extract_oxford_lists(root)
        assert 'Oxford 3000' in result

    def test_both_3000_and_5000(self):
        """Word on both lists -> returns both."""
        html = """<html><body>
            <h1 class="headword">both</h1>
            <div class="symbols">
                <a href="?list=ox3000&level=c1"><span class="ox3ksym_c1"> </span></a>
                <a href="?list=ox5000&level=c1"><span class="ox5ksym_c1"> </span></a>
            </div>
            <ol class="senses_multiple"></ol>
        </body></html>"""
        root = _parse(html)
        result = _extract_oxford_lists(root)
        assert 'Oxford 3000' in result
        assert 'Oxford 5000' in result

    def test_no_list_membership(self):
        """Word with no list symbol -> returns []."""
        html = """<html><body>
            <h1 class="headword">plain</h1>
            <div class="symbols"></div>
            <ol class="senses_multiple"></ol>
        </body></html>"""
        root = _parse(html)
        result = _extract_oxford_lists(root)
        assert result == []

    def test_legacy_sense_attribute_still_supported(self):
        """Old HTML with sense[ox5000]='y' attribute also detected (backward compat)."""
        html = """<html><body>
            <h1 class="headword">legacy</h1>
            <ol class="senses_multiple">
                <li class="sense" ox5000="y" ox3000="y">
                    <span class="def">a test def</span>
                </li>
            </ol>
        </body></html>"""
        root = _parse(html)
        result = _extract_oxford_lists(root)
        assert 'Oxford 3000' in result
        assert 'Oxford 5000' in result

    def test_modern_ox5ksym_takes_precedence(self):
        """When both .ox5ksym span AND sense[ox5000] exist, both detected (union)."""
        html = """<html><body>
            <h1 class="headword">union</h1>
            <div class="symbols">
                <a href="?list=ox5000&level=c1"><span class="ox5ksym_c1"> </span></a>
            </div>
            <ol class="senses_multiple">
                <li class="sense" ox3000="y">
                    <span class="def">a test def</span>
                </li>
            </ol>
        </body></html>"""
        root = _parse(html)
        result = _extract_oxford_lists(root)
        # Union: 5000 from span, 3000 from sense attr
        assert 'Oxford 3000' in result
        assert 'Oxford 5000' in result


class TestExtractOxfordBadge:
    """Sanity check: _extract_oxford_badge should already work for the same .ox5ksym span.
    This confirms the badge logic and verifies the same selector pattern works.
    """
    def test_badge_from_ox5ksym(self):
        html = """<html><body>
            <div class="symbols">
                <a><span class="ox5ksym_c1"> </span></a>
            </div>
        </body></html>"""
        root = _parse(html)
        assert _extract_oxford_badge(root) == 'C1'

    def test_badge_from_ox3ksym(self):
        html = """<html><body>
            <div class="symbols">
                <a><span class="ox3ksym_b1"> </span></a>
            </div>
        </body></html>"""
        root = _parse(html)
        assert _extract_oxford_badge(root) == 'B1'
