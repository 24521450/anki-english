import pytest

from tools._verify_deck_output_p3b import (
    extract_type_a_keys,
    parse_build_output,
    verify_audit_alignment,
    verify_definition_sync,
    verify_txt_structure,
)
from src.deck_builder.build_contracts import CARD_FIELDS


VALID_ROW = (
    "GUID\tnotetype\tdeck\tword\tpos\tipa\tdefn\tex\tcoll\twf\tuk\tus\t"
    "src1\tsrc2\tcefr\tidioms\ttags\tsynonyms\tantonyms\t"
    "example_audio_uk\texample_audio_us\tidiom_example_audio_uk\t"
    "idiom_example_audio_us"
)


def _unique_rows(count: int = 2) -> list[str]:
    rows = []
    for index in range(count):
        parts = VALID_ROW.split("\t")
        parts[0] = f"G{index}"
        rows.append("\t".join(parts))
    return rows


def test_txt_parser_skips_headers_and_preserves_field_count():
    lines = [
        "#separator:tab",
        "#html:true",
        "#guid:1",
        "#notetype:2",
        "#deck:3",
        "#tags:4",
        "",
        *_unique_rows(),
    ]

    data_rows = verify_txt_structure(lines)

    assert len(data_rows) == 2
    assert all(len(row) == len(CARD_FIELDS) for row in data_rows)


def test_txt_parser_accepts_idiom_only_card():
    lines = _unique_rows()
    parts = lines[0].split("\t")
    parts[6] = ""
    parts[15] = "phrase :: meaning :: example"
    lines[0] = "\t".join(parts)

    data_rows = verify_txt_structure(lines)

    assert len(data_rows) == 2


def test_txt_parser_fails_on_duplicate_guid():
    with pytest.raises(SystemExit):
        verify_txt_structure([VALID_ROW, VALID_ROW])


def test_txt_parser_fails_on_escaped_pipe():
    lines = _unique_rows()
    parts = lines[0].split("\t")
    parts[6] = r"defn\|escaped"
    lines[0] = "\t".join(parts)

    with pytest.raises(SystemExit):
        verify_txt_structure(lines)


def test_audit_alignment_rejects_duplicate_audit_key():
    duplicate = {
        "word": "word",
        "pos": "noun",
        "cefr": "C1",
        "gloss_after": "term",
    }

    with pytest.raises(SystemExit):
        verify_audit_alignment([], [duplicate, dict(duplicate)])


def test_definition_mismatch_against_audit():
    data_rows = [[
        "G1", "M", "D", "behalf", "noun", "ipa",
        "definition mismatch here", "ex", "c", "wf", "uk", "us",
        "s1", "s2", "C1", "id", "tag",
    ]]
    audit_rows = [{
        "word": "behalf",
        "pos": "noun",
        "cefr": "C1",
        "gloss_after": "in someone's place; representing them",
    }]

    with pytest.raises(SystemExit):
        verify_definition_sync(data_rows, audit_rows)


def test_build_output_parser():
    mock_stdout = """
      existing cards: 2461
      audit glosses loaded: 2487
      Dup emit skipped: 0
      built cards: 2461
      missing in jsonl: 0
    """

    metrics = parse_build_output(mock_stdout)

    assert metrics["existing_cards"] == 2461
    assert metrics["built_cards"] == 2461
    assert metrics["missing_in_jsonl"] == 0
    assert metrics["dup_emit_skipped"] == 0
    assert metrics["audit_glosses"] == 2487


def test_type_a_key_extraction():
    assert extract_type_a_keys("") == []
