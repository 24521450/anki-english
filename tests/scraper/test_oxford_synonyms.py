import pytest
from lxml import html as lxml_html
from src.scraper.oxford import _extract_synonyms, _extract_antonyms
from src.scraper.merge import merge_word_records

def test_extract_synonyms_none():
    html_content = """
    <li class="sense">
        <span class="def">having a lot of something</span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_synonyms(element) == []

def test_extract_synonyms_single():
    html_content = """
    <li class="sense">
        <span class="def">having a lot of something</span>
        <span class="xrefs" xt="syn" hclass="xrefs">
            <span class="prefix">synonym</span>
            <span class="xh">plentiful</span>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_synonyms(element) == ["plentiful"]

def test_extract_synonyms_multiple_and_dedup():
    html_content = """
    <li class="sense">
        <span class="def">having a lot of something</span>
        <span class="xrefs" xt="syn" hclass="xrefs">
            <span class="prefix">synonym</span>
            <span class="xh">plentiful</span>
            <span class="xh">abundant</span>
            <span class="xh">plentiful</span>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_synonyms(element) == ["plentiful", "abundant"]

def test_extract_synonyms_exclusion():
    # Opposites (xt="opp") and see-also prefix should be excluded
    html_content = """
    <li class="sense">
        <span class="def">having a lot of something</span>
        <span class="xrefs" xt="opp" hclass="xrefs">
            <span class="prefix">opposite</span>
            <span class="xh">scarce</span>
        </span>
        <span class="xrefs" xt="syn" hclass="xrefs">
            <span class="xh">plentiful</span>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_synonyms(element) == ["plentiful"]

def test_extract_antonyms_none():
    """Sense with no opposite block → empty list."""
    html_content = """
    <li class="sense">
        <span class="def">having a lot of something</span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_antonyms(element) == []

def test_extract_antonyms_single():
    """Sense with one xh headword inside xt='opp' xrefs block."""
    html_content = """
    <li class="sense">
        <span class="def">allowing you to see through it</span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="opp">
            <span class="prefix">opposite</span>
            <a class="Ref"><span class="xr-g"><span class="xh">opaque</span></span></a>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_antonyms(element) == ["opaque"]

def test_extract_antonyms_multiple_and_dedup():
    """Multiple xh headwords → preserved first-appearance order, deduped."""
    html_content = """
    <li class="sense">
        <span class="def">easy to understand</span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="opp">
            <span class="prefix">opposite</span>
            <a class="Ref"><span class="xr-g"><span class="xh">opaque</span></span></a>
            <a class="Ref"><span class="xr-g"><span class="xh">unclear</span></span></a>
            <a class="Ref"><span class="xr-g"><span class="xh">opaque</span></span></a>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_antonyms(element) == ["opaque", "unclear"]

def test_extract_antonyms_excludes_synonyms():
    """xt='syn' blocks must NOT leak into the antonyms list — separate semantic field."""
    html_content = """
    <li class="sense">
        <span class="def">that you can easily see is false</span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="syn">
            <span class="prefix">synonym</span>
            <a class="Ref"><span class="xr-g"><span class="xh">obvious</span></span></a>
        </span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="opp">
            <span class="prefix">opposite</span>
            <a class="Ref"><span class="xr-g"><span class="xh">subtle</span></span></a>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    # Synonym block ignored; only opp xh headword survives.
    assert _extract_antonyms(element) == ["subtle"]
    # And the synonym extractor ignores the opp block (regression on the
    # existing exclusion rule).
    assert _extract_synonyms(element) == ["obvious"]

def test_extract_antonyms_excludes_other_xt_blocks():
    """xt='cp' (compare) and xt='see' (see also) are not antonyms."""
    html_content = """
    <li class="sense">
        <span class="def">some def</span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="cp">
            <span class="prefix">compare</span>
            <a class="Ref"><span class="xr-g"><span class="xh">buck</span></span></a>
        </span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="see">
            <span class="prefix">see also</span>
            <a class="Ref"><span class="xr-g"><span class="xh">sterling</span></span></a>
        </span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="opp">
            <span class="prefix">opposite</span>
            <a class="Ref"><span class="xr-g"><span class="xh">cheap</span></span></a>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_antonyms(element) == ["cheap"]

def test_merge_union_synonyms():
    # Two records with identical definitions, but different synonyms
    record1 = {
        "word": "abundant",
        "homonym_index": 1,
        "source": "Oxford",
        "pos": ["adjective"],
        "pos_data": [
            {
                "pos": "adjective",
                "definitions": [
                    {
                        "n": 1,
                        "sensenum_local": "1",
                        "text": "existing in large quantities",
                        "cefr": "C1",
                        "topics": [],
                        "collocations": {},
                        "examples": [],
                        "is_phrase": False,
                        "is_idiom": False,
                        "synonyms": ["plentiful"]
                    }
                ]
            }
        ]
    }

    record2 = {
        "word": "abundant",
        "homonym_index": 1,
        "source": "Oxford",
        "pos": ["adjective"],
        "pos_data": [
            {
                "pos": "adjective",
                "definitions": [
                    {
                        "n": 1,
                        "sensenum_local": "1",
                        "text": "existing in large quantities",
                        "cefr": "C1",
                        "topics": [],
                        "collocations": {},
                        "examples": [],
                        "is_phrase": False,
                        "is_idiom": False,
                        "synonyms": ["copious", "plentiful"]
                    }
                ]
            }
        ]
    }

    merged = merge_word_records([record1, record2])
    defs = merged["pos_data"][0]["definitions"]
    assert len(defs) == 1
    # union, preserving order of first appearance, no duplicates
    assert defs[0]["synonyms"] == ["plentiful", "copious"]


def test_merge_union_antonyms():
    """Union antonyms across 2 records with the same def — same strategy as synonyms."""
    record1 = {
        "word": "transparent",
        "homonym_index": None,
        "source": "Oxford",
        "pos": ["adjective"],
        "pos_data": [
            {
                "pos": "adjective",
                "definitions": [
                    {
                        "n": 1,
                        "sensenum_local": "1",
                        "text": "allowing you to see through it",
                        "cefr": "C1",
                        "topics": [],
                        "collocations": {},
                        "examples": [],
                        "is_phrase": False,
                        "is_idiom": False,
                        "synonyms": [],
                        "antonyms": ["opaque"],
                    }
                ],
            }
        ],
    }
    record2 = {
        "word": "transparent",
        "homonym_index": None,
        "source": "Oxford",
        "pos": ["adjective"],
        "pos_data": [
            {
                "pos": "adjective",
                "definitions": [
                    {
                        "n": 1,
                        "sensenum_local": "1",
                        "text": "allowing you to see through it",
                        "cefr": "C1",
                        "topics": [],
                        "collocations": {},
                        "examples": [],
                        "is_phrase": False,
                        "is_idiom": False,
                        "synonyms": [],
                        "antonyms": ["cloudy", "opaque"],
                    }
                ],
            }
        ],
    }

    merged = merge_word_records([record1, record2])
    defs = merged["pos_data"][0]["definitions"]
    assert len(defs) == 1
    # Union preserves first-appearance order, no duplicates
    assert defs[0]["antonyms"] == ["opaque", "cloudy"]


def test_merge_single_record_normalizes_missing_antonyms():
    """A single-record input that lacks the antonyms field is normalized to [].

    Defensive: handles synthetic/legacy records that predate the antonyms
    extraction. The single-record passthrough must backfill so the schema
    validator and downstream consumers always see the field.
    """
    record = {
        "word": "old_word",
        "homonym_index": None,
        "source": "Oxford",
        "pos": ["noun"],
        "pos_data": [
            {
                "pos": "noun",
                "definitions": [
                    {
                        # Note: no "antonyms" key
                        "n": 1,
                        "sensenum_local": "1",
                        "text": "an older word",
                        "cefr": "B2",
                        "topics": [],
                        "collocations": {},
                        "examples": [],
                        "is_phrase": False,
                        "is_idiom": False,
                        "synonyms": [],
                    }
                ],
            }
        ],
    }
    merged = merge_word_records([record])
    defs = merged["pos_data"][0]["definitions"]
    assert defs[0]["antonyms"] == []
    assert defs[0]["synonyms"] == []


def test_merge_multi_record_normalizes_missing_antonyms():
    """Same backfill rule for the multi-record path — old records lacking
    the field should still merge cleanly without breaking the union logic."""
    record1 = {
        "word": "old",
        "homonym_index": None,
        "source": "Oxford",
        "pos": ["adjective"],
        "pos_data": [
            {
                "pos": "adjective",
                "definitions": [
                    {
                        # Missing antonyms
                        "n": 1,
                        "sensenum_local": "1",
                        "text": "ancient",
                        "cefr": "A2",
                        "topics": [],
                        "collocations": {},
                        "examples": [],
                        "is_phrase": False,
                        "is_idiom": False,
                        "synonyms": [],
                    }
                ],
            }
        ],
    }
    record2 = {
        "word": "old",
        "homonym_index": None,
        "source": "Oxford",
        "pos": ["adjective"],
        "pos_data": [
            {
                "pos": "adjective",
                "definitions": [
                    {
                        "n": 1,
                        "sensenum_local": "1",
                        "text": "ancient",
                        "cefr": "A2",
                        "topics": [],
                        "collocations": {},
                        "examples": [],
                        "is_phrase": False,
                        "is_idiom": False,
                        "synonyms": [],
                        "antonyms": ["new", "young"],
                    }
                ],
            }
        ],
    }
    merged = merge_word_records([record1, record2])
    defs = merged["pos_data"][0]["definitions"]
    assert len(defs) == 1
    # Union picks up record2's antonyms; record1's missing field was
    # treated as [] for the union.
    assert defs[0]["antonyms"] == ["new", "young"]


def test_extract_synonyms_nsyn_vicious_structure():
    """xt='nsyn' block (like in vicious -> brutal) must extract synonym."""
    html_content = """
    <li class="sense" id="vicious_sng_1" cefr="c1">
        <span class="def">violent and cruel</span>
        <span class="xrefs" hclass="xrefs" htag="span" xt="nsyn">
            <span class="prefix">synonym</span>
            <a class="Ref" href="..."><span class="xr-g"><span class="xh">brutal</span></span></a>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_synonyms(element) == ["brutal"]


def test_extract_synonyms_syn_and_nsyn_dom_order_and_dedup():
    """Both xt='syn' and xt='nsyn' are extracted in DOM order and deduped."""
    html_content = """
    <li class="sense">
        <span class="def">violent and cruel</span>
        <span class="xrefs" xt="syn" hclass="xrefs">
            <span class="prefix">synonym</span>
            <span class="xh">savage</span>
            <span class="xh">brutal</span>
        </span>
        <span class="xrefs" xt="nsyn" hclass="xrefs">
            <span class="prefix">synonym</span>
            <span class="xh">brutal</span>
            <span class="xh">ferocious</span>
        </span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_synonyms(element) == ["savage", "brutal", "ferocious"]


def test_extract_synonyms_excludes_other_xt():
    """xt='opp', xt='cp', xt='see' blocks must NOT leak into synonyms."""
    html_content = """
    <li class="sense">
        <span class="def">sample def</span>
        <span class="xrefs" xt="opp" hclass="xrefs"><span class="xh">opposite_word</span></span>
        <span class="xrefs" xt="cp" hclass="xrefs"><span class="xh">compare_word</span></span>
        <span class="xrefs" xt="see" hclass="xrefs"><span class="xh">see_word</span></span>
        <span class="xrefs" xt="nsyn" hclass="xrefs"><span class="xh">valid_synonym</span></span>
    </li>
    """
    element = lxml_html.fromstring(html_content)
    assert _extract_synonyms(element) == ["valid_synonym"]
