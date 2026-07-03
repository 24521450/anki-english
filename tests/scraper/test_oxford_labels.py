import pytest
from lxml import html as lxml_html
from src.scraper.oxford_labels import (
    REGISTER_LABELS,
    SUBJECT_LABELS,
    parse_label_compound,
    extract_labels_for_sense,
)


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


def test_extract_labels_for_sense_slash_sense_2():
    html_content = """
    <li class="sense">
        <span class="def">to reduce something by a large amount</span>
        <span class="labels" hclass="labels">(informal)</span>
    </li>
    """
    sense_el = lxml_html.fromstring(html_content)
    res = extract_labels_for_sense(sense_el)
    assert res["register_tags"] == ["informal"]
    assert res["domain"] is None


def test_extract_labels_for_sense_excludes_topics_and_grammar():
    html_content = """
    <li class="sense">
        <span class="grammar">[transitive]</span>
        <span class="labels">(formal)</span>
        <span class="topic-g"><span class="topic">Business</span></span>
    </li>
    """
    sense_el = lxml_html.fromstring(html_content)
    res = extract_labels_for_sense(sense_el)
    assert res["register_tags"] == ["formal"]
    assert res["domain"] is None
