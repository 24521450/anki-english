import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools._verify_deck_output_p3b import (
    verify_txt_structure,
    verify_card_identity,
    verify_definition_sync,
    parse_build_output,
    extract_type_a_keys
)


def test_txt_parser_skips_headers_and_preserves_field_count():
    # 6 header lines starting with # + 1 blank line + 2 valid lines
    # (Since total lines must be 2450 to pass structure check, we mock with 2450 valid rows)
    valid_row = "GUID\tnotetype\tdeck\tword\tpos\tipa\tdefn\tex\tcoll\twf\tuk\tus\tsrc1\tsrc2\tcefr\tidioms\ttags"
    lines = ["#separator:tab", "#html:true", "#guid:1", "#notetype:2", "#deck:3", "#tags:4", ""]
    lines.extend([valid_row] * 2450)
    
    # Change GUIDs to make them unique
    for i in range(7, len(lines)):
        parts = lines[i].split('\t')
        parts[0] = f"G{i}"
        lines[i] = '\t'.join(parts)

    data_rows = verify_txt_structure(lines)
    assert len(data_rows) == 2450
    assert all(len(row) == 17 for row in data_rows)


def test_txt_parser_fails_on_duplicate_guid():
    valid_row = "GUID\tnotetype\tdeck\tword\tpos\tipa\tdefn\tex\tcoll\twf\tuk\tus\tsrc1\tsrc2\tcefr\tidioms\ttags"
    lines = [valid_row] * 2450
    # Duplicate GUIDs present, so verify_txt_structure should exit 1
    with pytest.raises(SystemExit):
        verify_txt_structure(lines)


def test_txt_parser_fails_on_escaped_pipe():
    valid_row = "G\tnotetype\tdeck\tword\tpos\tipa\tdefn\\|escaped\tex\tcoll\twf\tuk\tus\tsrc1\tsrc2\tcefr\tidioms\ttags"
    lines = [valid_row] * 2450
    # Make GUIDs unique
    for i in range(2450):
        parts = lines[i].split('\t')
        parts[0] = f"G{i}"
        lines[i] = '\t'.join(parts)
    with pytest.raises(SystemExit):
        verify_txt_structure(lines)


def test_card_identity_duplicate_word_cefr_detection():
    # word-cefr duplicate key
    data_rows = [
        ["G1", "M", "D", "absent", "adjective", "ipa", "defn", "ex", "c", "wf", "uk", "us", "s1", "s2", "C1", "id", "tag"],
        ["G2", "M", "D", "absent", "noun", "ipa", "defn", "ex", "c", "wf", "uk", "us", "s1", "s2", "C1", "id", "tag"]
    ]
    audit_rows = []
    with pytest.raises(SystemExit):
        verify_card_identity(data_rows, audit_rows)


def test_definition_mismatch_against_audit():
    data_rows = [
        ["G1", "M", "D", "behalf", "noun", "ipa", "definition mismatch here", "ex", "c", "wf", "uk", "us", "s1", "s2", "C1", "id", "tag"]
    ]
    # Expected audit gloss is 'in someone's place; representing them'
    audit_rows = [
        {"word": "behalf", "pos": "noun", "cefr": "C1", "gloss_after": "in someone's place; representing them"}
    ]
    with pytest.raises(SystemExit):
        verify_definition_sync(data_rows, audit_rows)


def test_build_output_parser():
    mock_stdout = """
    Vocab AWL:   AWL.md
      3000: 3806 entries
      5000: 2138 entries
      AWL:  715 entries
      total target keys: 6100
    Loading existing txt: English Academic Vocabulary.txt
      existing cards: 2450
    Loading gamma verdicts: gamma_all_verdicts.json
      gamma verdicts: 548
      audit glosses loaded: 2487
      filled keys loaded: 30
    Loading jsonl: oxford_merged.jsonl
      unique words in jsonl: 5311
      unique idioms in jsonl: 6175
    === Building cards (existing txt scope) ===
      Pre-computing simplified senses for all jsonl records...
      words with simplified data: 5307
      Iterating 2450 existing txt rows (3-type POS fix)...
      Type A (POS fix): 4
      Type B (lemmatize): 0
      Type C (drop, no data): 0
      Dup emit skipped: 0
      UNCLASSIFIED drop: 0
      POS-fixed keys: 4
      Dropped keys: 0
      built cards: 2450
      missing in jsonl: 0
    """
    metrics = parse_build_output(mock_stdout)
    assert metrics['existing_cards'] == 2450
    assert metrics['built_cards'] == 2450
    assert metrics['missing_in_jsonl'] == 0
    assert metrics['dup_emit_skipped'] == 0
    assert metrics['audit_glosses'] == 2487


def test_type_a_key_extraction():
    # Test extract_type_a_keys directly runs without exceptions
    try:
        keys = extract_type_a_keys("")
        assert isinstance(keys, list)
    except Exception as e:
        pytest.fail(f"extract_type_a_keys raised an exception: {e}")
