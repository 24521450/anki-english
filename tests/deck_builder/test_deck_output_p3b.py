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
    extract_type_a_keys,
    primary_list_from_tags,
    LIST_PRIORITY,
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
    # word-cefr duplicate key — under the new (Word, CEFR, LIST) identity
    # rule, two rows that share `(word, CEFR)` but resolve to the same LIST
    # (here both NO_LIST because tags carry no list token) ARE still a real
    # duplicate. Hard check should still fail.
    data_rows = [
        ["G1", "M", "D", "absent", "adjective", "ipa", "defn", "ex", "c", "wf", "uk", "us", "s1", "s2", "C1", "id", "Source::Oxford CEFR::C1 CEFR::oxford"],
        ["G2", "M", "D", "absent", "noun", "ipa", "defn", "ex", "c", "wf", "uk", "us", "s1", "s2", "C1", "id", "Source::Oxford CEFR::C1 CEFR::oxford"],
    ]
    audit_rows = []
    with pytest.raises(SystemExit):
        verify_card_identity(data_rows, audit_rows)


def test_card_identity_firm_split_passes():
    """`firm` at B2 across Oxford_3000 and Oxford_5000 is a legitimate split
    under the list-aware identity rule (2026-06-21). The verifier must NOT
    fail on `(Word, CEFR)` duplicates; only `(Word, CEFR, LIST)` is hard.
    """
    data_rows = [
        ["G1", "M", "D", "firm", "adjective", "ipa", "solid", "ex", "c", "wf", "uk", "us", "s1", "s2", "B2", "id", "Source::Oxford CEFR::B2 CEFR::oxford Oxford_5000"],
        ["G2", "M", "D", "firm", "noun",      "ipa", "company", "ex", "c", "wf", "uk", "us", "s1", "s2", "B2", "id", "Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000"],
    ]
    audit_rows = []  # No audit check on these synthetic rows
    # Should NOT raise — (word, CEFR) duplicates are informational only.
    verify_card_identity(data_rows, audit_rows)


def test_card_identity_word_cefr_list_duplicate_fails():
    """Two rows that share `(Word, CEFR, LIST)` is a hard duplicate — verifier
    must exit 1. This is the core contract of list-aware identity."""
    data_rows = [
        ["G1", "M", "D", "yield", "noun", "ipa", "output", "ex", "c", "wf", "uk", "us", "s1", "s2", "C1", "id", "Source::Oxford CEFR::C1 CEFR::oxford Oxford_5000"],
        ["G2", "M", "D", "yield", "verb", "ipa", "produce", "ex", "c", "wf", "uk", "us", "s1", "s2", "C1", "id", "Source::Oxford CEFR::C1 CEFR::oxford Oxford_5000"],
    ]
    audit_rows = []
    with pytest.raises(SystemExit):
        verify_card_identity(data_rows, audit_rows)


def test_card_identity_word_pos_cefr_duplicate_still_fails():
    """(Word, pos, CEFR) duplicates remain a hard contract — even when LIST
    differs, two cards at the same word+POS+CEFR is a real bug."""
    data_rows = [
        ["G1", "M", "D", "firm", "adjective", "ipa", "solid",   "ex", "c", "wf", "uk", "us", "s1", "s2", "B2", "id", "Source::Oxford CEFR::B2 CEFR::oxford Oxford_5000"],
        ["G2", "M", "D", "firm", "adjective", "ipa", "sturdy",  "ex", "c", "wf", "uk", "us", "s1", "s2", "B2", "id", "Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000"],
    ]
    audit_rows = []
    with pytest.raises(SystemExit):
        verify_card_identity(data_rows, audit_rows)


class TestPrimaryListFromTags:
    """Card Identity = (Word, CEFR, LIST). LIST is resolved from the card's
    tags via `primary_list_from_tags` per the fixed priority
    Oxford_5000 > Oxford_3000 > AWL > NO_LIST."""

    def test_priority_5000_wins_when_all_present(self):
        assert primary_list_from_tags("Oxford_5000 Oxford_3000 AWL") == "Oxford_5000"

    def test_3000_wins_over_AWL(self):
        assert primary_list_from_tags("Oxford_3000 AWL") == "Oxford_3000"

    def test_only_AWL_returns_AWL(self):
        assert primary_list_from_tags("AWL") == "AWL"

    def test_no_list_tokens_returns_NO_LIST(self):
        assert primary_list_from_tags("") == "NO_LIST"

    def test_unrelated_tags_returns_NO_LIST(self):
        assert primary_list_from_tags("Source::Oxford CEFR::B2 CEFR::oxford") == "NO_LIST"

    def test_priority_order_is_fixed(self):
        """LIST_PRIORITY must remain Oxford_5000 > Oxford_3000 > AWL so
        identity stays stable across runs and rebuilds."""
        assert LIST_PRIORITY == ("Oxford_5000", "Oxford_3000", "AWL")

    def test_full_firm_tags_resolve_correctly(self):
        """Regression: the `firm` worked example — Oxford_5000 and Oxford_3000
        tags on different rows must resolve to their respective lists."""
        adj_tags = "Source::Oxford CEFR::B2 CEFR::oxford Oxford_5000 idioms"
        noun_tags = "Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000 idioms"
        assert primary_list_from_tags(adj_tags) == "Oxford_5000"
        assert primary_list_from_tags(noun_tags) == "Oxford_3000"
        # And the two (Word, CEFR, LIST) tuples differ — verifier should pass.
        assert ("firm", "B2", "Oxford_5000") != ("firm", "B2", "Oxford_3000")


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
    Loading existing txt: anki_notes.txt
      existing cards: 2450
    Loading gamma verdicts: gamma_verdicts.json
      gamma verdicts: 548
      audit glosses loaded: 2487
      filled keys loaded: 30
    Loading jsonl: oxford.jsonl
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
