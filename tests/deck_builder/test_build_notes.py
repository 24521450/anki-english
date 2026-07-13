from pathlib import Path

from src.deck_builder.build_contracts import DEF_SEPARATOR, EX_SEP
from src.deck_builder.build_support import _format_examples, get_word_candidates, lookup_gloss
from src.deck_builder.build_validation import _parse_txt_cards


def test_separators_match_template_contract():
    assert DEF_SEPARATOR == "|"
    assert EX_SEP == "|"


def test_format_examples_keeps_one_example_per_sense_by_default():
    examples = [
        {"text": "first ex"},
        {"text": "second ex"},
        {"text": "third ex"},
    ]
    assert _format_examples(examples) == "first ex"
    assert _format_examples(examples, max_n=2) == "first ex|second ex"


def test_definition_example_pairing_uses_same_pipe_chunks():
    senses = [
        {"text": "sense 1 def", "examples": [{"text": "sense 1 ex"}]},
        {"text": "sense 2 def", "examples": [{"text": "sense 2 ex"}]},
        {"text": "sense 3 def", "examples": [{"text": "sense 3 ex"}]},
    ]
    definition = DEF_SEPARATOR.join(s["text"] for s in senses)
    example = EX_SEP.join(_format_examples(s["examples"]) for s in senses)
    assert definition == "sense 1 def|sense 2 def|sense 3 def"
    assert example == "sense 1 ex|sense 2 ex|sense 3 ex"
    assert definition.count("|") == example.count("|")


def _txt_row(guid: str, word: str, pos: str, cefr: str) -> str:
    return "\t".join([
        guid,
        "English Academic Vocabulary Model",
        "English Academic Vocabulary::Oxford",
        word,
        pos,
        "/ipa/",
        "stub",
        "stub ex",
        "",
        "",
        "",
        "",
        "Oxford",
        "Oxford",
        cefr,
        "",
        f"Source::Oxford CEFR::{cefr} CEFR::oxford",
        "",
        "",
        "",
        "",
        "",
        "",
    ])


def test_txt_artifact_parser_preserves_parenthetical_words(tmp_path: Path):
    txt = "\n".join([
        "#separator:tab",
        "#html:true",
        "#guid column:1",
        "#notetype column:2",
        "#deck column:3",
        "#tags column:17",
        _txt_row("G1", "counter (argue against)", "verb", "C1"),
        _txt_row("G2", "counter (long flat surface)", "noun", "B2"),
        "",
    ])
    path = tmp_path / "anki_notes.txt"
    path.write_text(txt, encoding="utf-8")
    cards, issues = _parse_txt_cards(path.read_text(encoding="utf-8"), path)
    assert not issues
    assert [card.word for card in cards] == [
        "counter (argue against)",
        "counter (long flat surface)",
    ]


def test_get_word_candidates_strips_parenthetical_for_source_lookup():
    assert get_word_candidates("counter (argue against)")[0] == "counter"
    assert get_word_candidates("grave (serious)")[0] == "grave"
    assert get_word_candidates("strip (long narrow piece)")[0] == "strip"
    assert "counter (argue against)" not in get_word_candidates("counter (argue against)")


def test_get_word_candidates_resolves_learning_pattern_to_source_lemma():
    assert get_word_candidates("devote sth to sth")[0] == "devote"


def test_lookup_gloss_prefers_exact_parenthetical_key():
    audit = {
        ("counter (argue against)", "verb", "C1"): "oppose",
        ("counter", "verb", "C1"): "ghost oppose",
    }
    assert lookup_gloss(
        audit,
        "counter (argue against)",
        "verb",
        "C1",
        "counter",
        ["verb"],
        "C1",
    ) == "oppose"


def test_lookup_gloss_blocks_unsafe_base_fallback_for_sibling_homonyms():
    audit = {
        ("counter (argue against)", "verb", "C1"): "oppose",
        ("counter (long flat surface)", "noun", "B2"): "service desk",
        ("counter", "verb", "C1"): "wrong",
    }
    assert lookup_gloss(
        audit,
        "counter (argue against)",
        "verb",
        "C1",
        "counter",
        ["verb"],
        "C1",
    ) == "oppose"
