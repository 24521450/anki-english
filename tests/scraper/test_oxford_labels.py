"""Tests for extract_labels_for_sense — ownership scoping.

Regression cases that must hold after the allowlist fix:
- spectacle sense 1: formal kept, variant informal rejected
- cheek sense 1: no labels (variant block only)
- cheek sense 3: informal kept (genuine sense-level label)
- football: no false register labels from variant block
- like: no informal from usage note (span.un)
- little: no informal/formal from example sentences
- slash verb sense 2: informal kept (direct child of li.sense)
"""
import pytest
from lxml import html as lxml_html
from src.scraper.oxford_labels import (
    CONFLICT_PAIRS,
    REGISTER_LABELS,
    SUBJECT_LABELS,
    parse_label_compound,
    extract_labels_for_sense,
    _label_is_owned_by_sense,
)


# ---------------------------------------------------------------------------
# parse_label_compound (existing tests, unchanged)
# ---------------------------------------------------------------------------

def test_parse_label_compound_basic_informal():
    res = parse_label_compound("(informal)")
    assert res["register_tags"] == ["informal"]
    assert res["domain"] is None


def test_parse_label_compound_regional_and_informal():
    """(British English, informal) -> only informal (regional label ignored)."""
    res = parse_label_compound("(British English, informal)")
    assert res["register_tags"] == ["informal"]
    assert res["domain"] is None


def test_parse_label_compound_subject_law():
    """(law) -> domain='law'."""
    res = parse_label_compound("(law)")
    assert res["register_tags"] == []
    assert res["domain"] == "law"


def test_parse_label_compound_compound_register_and_subject():
    """(informal, law) -> register_tags=['informal'], domain='law'."""
    res = parse_label_compound("(informal, law)")
    assert res["register_tags"] == ["informal"]
    assert res["domain"] == "law"


def test_parse_label_compound_grammar_notes_ignored():
    """Grammar notes like 'countable' or 'transitive' or 'often passive' are ignored."""
    res = parse_label_compound("(transitive, often passive)")
    assert res["register_tags"] == []
    assert res["domain"] is None


# ---------------------------------------------------------------------------
# CONFLICT_PAIRS — canonical location sanity check
# ---------------------------------------------------------------------------

def test_conflict_pairs_canonical():
    """CONFLICT_PAIRS is defined in oxford_labels and imported consistently."""
    from src.deck_builder.sense_labels import CONFLICT_PAIRS as sl_cp
    from src.deck_builder.simplify_senses import CONFLICT_PAIRS as ss_cp
    assert CONFLICT_PAIRS == sl_cp
    assert CONFLICT_PAIRS == ss_cp


def test_conflict_pairs_content():
    assert ("formal", "informal") in CONFLICT_PAIRS
    assert ("formal", "slang") in CONFLICT_PAIRS
    assert ("approving", "disapproving") in CONFLICT_PAIRS


# ---------------------------------------------------------------------------
# Ownership allowlist: _label_is_owned_by_sense
# ---------------------------------------------------------------------------

def test_direct_child_owned():
    """span.labels directly inside li.sense is owned."""
    html = """<li class="sense">
        <span class="labels">(formal)</span>
        <span class="def">some definition</span>
    </li>"""
    s = lxml_html.fromstring(html)
    lbl = s.cssselect("span.labels")[0]
    assert _label_is_owned_by_sense(lbl, s) is True


def test_inside_sensetop_owned():
    """span.labels inside span.sensetop is owned."""
    html = """<li class="sense">
        <span class="sensetop">
            <span class="labels">(formal)</span>
        </span>
        <span class="def">some definition</span>
    </li>"""
    s = lxml_html.fromstring(html)
    lbl = s.cssselect("span.labels")[0]
    assert _label_is_owned_by_sense(lbl, s) is True


def test_inside_variants_not_owned():
    """span.labels inside div.variants is NOT owned by the sense."""
    html = """<li class="sense">
        <div class="variants">
            <span class="v-g">
                <span class="labels">informal</span>
                <span class="v">specs</span>
            </span>
        </div>
        <span class="def">two lenses in a frame</span>
    </li>"""
    s = lxml_html.fromstring(html)
    lbl = s.cssselect("span.labels")[0]
    assert _label_is_owned_by_sense(lbl, s) is False


def test_inside_examples_not_owned():
    """span.labels inside ul.examples is NOT owned."""
    html = """<li class="sense">
        <span class="labels">(formal)</span>
        <ul class="examples">
            <li><span class="labels">(informal)</span> she liked him</li>
        </ul>
    </li>"""
    s = lxml_html.fromstring(html)
    # First label is owned, second is not
    lbls = s.cssselect("span.labels")
    owned = [_label_is_owned_by_sense(lbl, s) for lbl in lbls]
    assert owned[0] is True   # direct
    assert owned[1] is False  # in examples


def test_inside_unbox_not_owned():
    """span.labels inside span.unbox is NOT owned."""
    html = """<li class="sense">
        <div class="collapse">
            <span class="unbox">
                <span class="body">
                    <span class="labels">British English</span>
                </span>
            </span>
        </div>
    </li>"""
    s = lxml_html.fromstring(html)
    lbl = s.cssselect("span.labels")[0]
    assert _label_is_owned_by_sense(lbl, s) is False


def test_inside_un_not_owned():
    """span.labels inside span.un (inline usage note) is NOT owned."""
    html = """<li class="sense">
        <span class="def">to want something</span>
        <span class="un">
            <span class="labels">(informal)</span>
            I like it.
        </span>
    </li>"""
    s = lxml_html.fromstring(html)
    lbl = s.cssselect("span.labels")[0]
    assert _label_is_owned_by_sense(lbl, s) is False


# ---------------------------------------------------------------------------
# extract_labels_for_sense — integration cases
# ---------------------------------------------------------------------------

def test_extract_labels_slash_sense_2():
    """slash verb sense 2: (informal) is a direct child label -> kept."""
    html = """<li class="sense">
        <span class="def">to reduce something by a large amount</span>
        <span class="labels" hclass="labels">(informal)</span>
    </li>"""
    s = lxml_html.fromstring(html)
    res = extract_labels_for_sense(s)
    assert res["register_tags"] == ["informal"]
    assert res["domain"] is None


def test_extract_labels_spectacle_sense_1():
    """spectacle noun sense 1: (formal) kept, variant informal rejected."""
    html = """<li class="sense" sensenum="1">
        <span class="sensetop">
            <span class="labels" hclass="labels">(formal)</span>
        </span>
        <div class="variants" type="vf" hclass="variants">
            (also
            <span class="v-g">
                <span class="labels" hclass="labels">informal</span>
                <span class="v">specs</span>
            </span>)
        </div>
        <span class="def">two lenses in a frame</span>
    </li>"""
    s = lxml_html.fromstring(html)
    res = extract_labels_for_sense(s)
    assert "formal" in res["register_tags"]
    assert "informal" not in res["register_tags"]


def test_extract_labels_cheek_sense_1_no_labels():
    """cheek noun sense 1: only a variant label -> no register_tags extracted."""
    html = """<li class="sense" sensenum="1">
        <span class="def">either side of the face below the eyes</span>
        <div class="variants">
            <span class="v-g">
                <span class="labels">(informal)</span>
                <span class="v">cheeks</span>
            </span>
        </div>
    </li>"""
    s = lxml_html.fromstring(html)
    res = extract_labels_for_sense(s)
    assert res["register_tags"] == []


def test_extract_labels_cheek_sense_3_informal():
    """cheek noun sense 3: (informal) is a genuine direct-child label -> kept."""
    html = """<li class="sense" sensenum="3">
        <span class="labels">(informal)</span>
        <span class="def">either of the buttocks</span>
    </li>"""
    s = lxml_html.fromstring(html)
    res = extract_labels_for_sense(s)
    assert res["register_tags"] == ["informal"]


def test_extract_labels_football_no_false_labels():
    """football noun sense 1: variant-block label 'formal' NOT extracted."""
    html = """<li class="sense" sensenum="1">
        <span class="labels">(both British English)</span>
        <div class="variants">
            <span class="v-g">
                <span class="labels">formal</span>
                <span class="v">association football</span>
            </span>
        </div>
        <span class="def">a game played by two teams</span>
    </li>"""
    s = lxml_html.fromstring(html)
    res = extract_labels_for_sense(s)
    # "both British English" is a regional label -> parse_label_compound drops it
    # "formal" is inside variants -> rejected by ownership rule
    assert res["register_tags"] == []


def test_extract_labels_example_labels_rejected():
    """Labels inside example sentences are NOT extracted as sense labels."""
    html = """<li class="sense" sensenum="1">
        <span class="def">to want something</span>
        <ul class="examples">
            <li><span class="labels">(informal)</span> I like it.</li>
            <li><span class="labels">(formal)</span> I would like to...</li>
        </ul>
    </li>"""
    s = lxml_html.fromstring(html)
    res = extract_labels_for_sense(s)
    assert res["register_tags"] == []


def test_extract_labels_excludes_topics_and_grammar():
    """Topics and grammar annotations don't affect register_tags."""
    html = """<li class="sense">
        <span class="grammar">[transitive]</span>
        <span class="labels">(formal)</span>
        <span class="topic-g"><span class="topic">Business</span></span>
    </li>"""
    s = lxml_html.fromstring(html)
    res = extract_labels_for_sense(s)
    assert res["register_tags"] == ["formal"]
    assert res["domain"] is None
