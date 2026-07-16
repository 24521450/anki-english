import pytest

from src.deck_builder.dictionary_links import (
    OxfordLinkIndex,
    cambridge_url,
    is_official_cambridge_url,
    is_official_oxford_url,
)
from src.deck_builder.simplify_senses import _flatten_senses
from src.deck_builder.source_sense_identity import source_sense_id


def _record(pos: str, url: str, filename: str, text: str) -> dict:
    return {
        "word": "torture",
        "homonym_index": None,
        "source": "oxford",
        "source_files": [filename],
        "oxford_badge": "C1",
        "pos_data": [{
            "pos": pos,
            "source_url": url,
            "definitions": [{"sensenum_local": "1", "text": text, "cefr": "C1"}],
        }],
    }


def test_torture_links_are_pipe_aligned_by_semantic_source_ids():
    noun_url = "https://www.oxfordlearnersdictionaries.com/definition/english/torture_1"
    verb_url = "https://www.oxfordlearnersdictionaries.com/definition/english/torture_2"
    noun = _record("noun", noun_url, "oxford_torture_(noun).html", "extreme pain")
    verb = _record("verb", verb_url, "oxford_torture_(verb).html", "to hurt")
    source_ids = {
        source_sense_id(record, _flatten_senses(record)[0])
        for record in (noun, verb)
    }
    index = OxfordLinkIndex({"torture": [noun, verb]})
    assert index.aligned_urls("torture", ["noun", "verb"], source_ids) == f"{noun_url}|{verb_url}"
    assert cambridge_url("torture") == "https://dictionary.cambridge.org/dictionary/english/torture"


def test_ambiguous_pos_without_semantic_evidence_stays_empty():
    first = _record("noun", "https://www.oxfordlearnersdictionaries.com/definition/english/bow_1", "bow_1.html", "bend")
    second = _record("noun", "https://www.oxfordlearnersdictionaries.com/definition/english/bow_2", "bow_2.html", "weapon")
    first["word"] = second["word"] = "bow"
    index = OxfordLinkIndex({"bow": [first, second]})
    assert index.aligned_urls("bow", ["noun"], set()) == ""


def test_cambridge_url_uses_the_resolved_learning_pattern_lemma():
    assert cambridge_url("devote") == "https://dictionary.cambridge.org/dictionary/english/devote"


@pytest.mark.parametrize("unsafe", [" ", "\t", '"', "'", "<", ">"])
def test_official_url_validators_reject_href_attribute_delimiters(unsafe: str):
    assert not is_official_cambridge_url(
        f"https://dictionary.cambridge.org/dictionary/english/tor{unsafe}ture"
    )
    assert not is_official_oxford_url(
        f"https://www.oxfordlearnersdictionaries.com/definition/english/tor{unsafe}ture_1"
    )
