"""Unit tests for _extract_topics (oxford.py).

Regression for multi-topic/sense bug where the old regex-on-text_content approach
collapsed "Social issuesc1, Health problemsc1" into one entry whose name was
"Social issuesc1" (CEFR leaked into name of topic 1, topic 2 dropped entirely).

Fix: iterate span.topic elements directly; extract CEFR from span.topic_cefr child.
"""
from __future__ import annotations

import pytest
from lxml import html as lxml_html

from src.scraper.oxford import _extract_topics


def _make_sense_html(topic_g_inner: str) -> object:
    """Wrap arbitrary topic-g markup inside a fake li.sense element."""
    markup = f'<li class="sense"><span class="topic-g">{topic_g_inner}</span></li>'
    root = lxml_html.fromstring(markup)
    return root  # root IS the li.sense element


# ── Single topic with CEFR ───────────────────────────────────────────────────

def test_single_topic_with_cefr():
    """Existing golden case (kilometre): one topic, CEFR a1."""
    sense = _make_sense_html(
        '<span class="prefix">Topics </span>'
        '<a class="Ref"><span class="topic">Maths and measurement'
        '<span class="topic_cefr">a1</span></span></a>'
    )
    result = _extract_topics(sense)
    assert result == [{"name": "Maths and measurement", "cefr": "A1"}]


def test_single_topic_cefr_uppercased():
    """CEFR value must be uppercased regardless of DOM case."""
    sense = _make_sense_html(
        '<a class="Ref"><span class="topic">Holidays'
        '<span class="topic_cefr">b2</span></span></a>'
    )
    result = _extract_topics(sense)
    assert result == [{"name": "Holidays", "cefr": "B2"}]


# ── Multi-topic / sense (the bug) ────────────────────────────────────────────

def test_multi_topic_both_same_cefr():
    """Regression: addictive sense 1 — two topics, both C1.

    Old code produced: [{'name': 'Social issuesc1, Health problems', 'cefr': 'C1'}]
    (one entry, name contaminated with 'c1' in the middle).

    Fixed code must produce two clean entries.
    """
    sense = _make_sense_html(
        '<span class="prefix">Topics </span>'
        '<a class="Ref"><span class="topic">Social issues'
        '<span class="topic_cefr">c1</span></span></a>'
        '<span class="sep">, </span>'
        '<a class="Ref"><span class="topic">Health problems'
        '<span class="topic_cefr">c1</span></span></a>'
    )
    result = _extract_topics(sense)
    assert result == [
        {"name": "Social issues", "cefr": "C1"},
        {"name": "Health problems", "cefr": "C1"},
    ]


def test_multi_topic_different_cefr():
    """Two topics with different CEFR levels must both be kept with correct names."""
    sense = _make_sense_html(
        '<a class="Ref"><span class="topic">Education'
        '<span class="topic_cefr">b1</span></span></a>'
        '<span class="sep">, </span>'
        '<a class="Ref"><span class="topic">Work'
        '<span class="topic_cefr">c2</span></span></a>'
    )
    result = _extract_topics(sense)
    assert result == [
        {"name": "Education", "cefr": "B1"},
        {"name": "Work", "cefr": "C2"},
    ]


def test_three_topics():
    """Three topics in one sense — all must appear."""
    sense = _make_sense_html(
        '<a class="Ref"><span class="topic">Food'
        '<span class="topic_cefr">a2</span></span></a>'
        '<span class="sep">, </span>'
        '<a class="Ref"><span class="topic">Health'
        '<span class="topic_cefr">b1</span></span></a>'
        '<span class="sep">, </span>'
        '<a class="Ref"><span class="topic">Science'
        '<span class="topic_cefr">c1</span></span></a>'
    )
    result = _extract_topics(sense)
    assert len(result) == 3
    assert result[0] == {"name": "Food", "cefr": "A2"}
    assert result[1] == {"name": "Health", "cefr": "B1"}
    assert result[2] == {"name": "Science", "cefr": "C1"}


# ── Topic without CEFR ───────────────────────────────────────────────────────

def test_topic_without_cefr():
    """Topics that Oxford does not tag with a level: cefr must be None."""
    sense = _make_sense_html(
        '<a class="Ref"><span class="topic">War and conflict</span></a>'
    )
    result = _extract_topics(sense)
    assert result == [{"name": "War and conflict", "cefr": None}]


def test_multi_topic_mixed_cefr_presence():
    """One topic has CEFR, the other does not."""
    sense = _make_sense_html(
        '<a class="Ref"><span class="topic">Law'
        '<span class="topic_cefr">c1</span></span></a>'
        '<span class="sep">, </span>'
        '<a class="Ref"><span class="topic">Society</span></a>'
    )
    result = _extract_topics(sense)
    assert result == [
        {"name": "Law", "cefr": "C1"},
        {"name": "Society", "cefr": None},
    ]


# ── Empty / absent topic-g ───────────────────────────────────────────────────

def test_no_topic_g():
    """Sense with no topic-g at all must return empty list."""
    markup = '<li class="sense"><span class="def">some definition</span></li>'
    sense = lxml_html.fromstring(markup)
    result = _extract_topics(sense)
    assert result == []


def test_empty_topic_g():
    """topic-g present but empty (no span.topic children)."""
    sense = _make_sense_html('<span class="prefix">Topics </span>')
    result = _extract_topics(sense)
    assert result == []
