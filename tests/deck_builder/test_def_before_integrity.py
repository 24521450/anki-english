import json
from pathlib import Path
import pytest

from src.deck_builder.def_before_integrity import (
    DefBeforeIntegrityPaths,
    DefBeforeIntegrityReport,
    check_def_before_integrity,
    norm_def
)

@pytest.fixture
def temp_paths(tmp_path) -> DefBeforeIntegrityPaths:
    return DefBeforeIntegrityPaths(
        deck_audit_jsonl=tmp_path / "deck_audit.jsonl",
        oxford_jsonl=tmp_path / "oxford.jsonl",
        manual_card_fills=tmp_path / "manual_card_fills.json",
        anki_notes_txt=tmp_path / "anki_notes.txt",
        oxford_5000_md=tmp_path / "Oxford_5000.md",
    )


@pytest.fixture(autouse=True)
def empty_oxford_5000(temp_paths):
    temp_paths.oxford_5000_md.write_text("", encoding="utf-8")

def test_norm_def():
    assert norm_def("  [usually singular]  a Book. ") == "a book"
    assert norm_def("something for somebody") == "something for somebody"
    assert norm_def("sth for sb") == "something for somebody"

def test_orphan_detection(temp_paths):
    # Setup audit row
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    # Setup empty files for others
    temp_paths.oxford_jsonl.write_text("", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    
    # Setup anki_notes.txt without this card
    temp_paths.anki_notes_txt.write_text("#header\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["orphan"] == 1
    assert len(report.orphan_rows) == 1
    assert report.orphan_rows[0][1]["word"] == "testword"

def test_manual_fill_exact_match(temp_paths):
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    temp_paths.oxford_jsonl.write_text("", encoding="utf-8")
    
    # Matching manual fill
    mf_data = [{
        "word": "testword",
        "pos": "noun",
        "cefr": "C1",
        "def_before": "a test definition",
        "source": "missing_oxford_5000",
    }]
    temp_paths.manual_card_fills.write_text(json.dumps(mf_data), encoding="utf-8")
    
    # Card exists
    card_row = "guid123\tNotetype\tDeck\ttestword\tnoun\t\t\t\t\t\t\t\t\t\tC1\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["manual_fill"] == 1
    assert report.stats["orphan"] == 0

def test_manual_fill_mismatch_falls_through(temp_paths):
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    temp_paths.oxford_jsonl.write_text("", encoding="utf-8")
    
    # Mismatching manual fill (different def_before)
    mf_data = [{"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a different definition"}]
    temp_paths.manual_card_fills.write_text(json.dumps(mf_data), encoding="utf-8")
    
    card_row = "guid123\tNotetype\tDeck\ttestword\tnoun\t\t\t\t\t\t\t\t\t\tC1\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["manual_fill"] == 0
    assert report.stats["unmatched"] == 1

def test_manual_fill_requires_missing_oxford_source(temp_paths):
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    temp_paths.oxford_jsonl.write_text("", encoding="utf-8")
    temp_paths.manual_card_fills.write_text(json.dumps([{
        "word": "testword",
        "pos": "noun",
        "cefr": "C1",
        "def_before": "a test definition",
        "source": "original_100pct",
    }]), encoding="utf-8")
    card_row = "guid123\tNotetype\tDeck\ttestword\tnoun\t\t\t\t\t\t\t\t\t\tC1\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")

    report = check_def_before_integrity(temp_paths)

    assert report.stats["manual_fill"] == 0
    assert report.stats["unmatched"] == 1

def test_missing_required_input_raises(temp_paths):
    temp_paths.deck_audit_jsonl.write_text("", encoding="utf-8")
    temp_paths.oxford_jsonl.write_text("", encoding="utf-8")
    temp_paths.anki_notes_txt.write_text("", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="manual_card_fills"):
        check_def_before_integrity(temp_paths)

def test_report_tracks_every_input_row(temp_paths):
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    temp_paths.oxford_jsonl.write_text("", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    temp_paths.anki_notes_txt.write_text("#header\n", encoding="utf-8")

    report = check_def_before_integrity(temp_paths)

    assert report.total_rows_read == 1
    assert sum(report.stats.values()) == report.total_rows_read

def test_report_rejects_incomplete_classification():
    report = DefBeforeIntegrityReport(
        stats={"oxford_exact": 0},
        total_rows_read=1,
        orphan_rows=[],
        unmatched_rows=[],
        ambiguous_rows=[],
    )

    assert report.has_errors()

def test_cefr_mismatch_unmatched(temp_paths):
    # Audit row asks for C1
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    # Oxford sense is B2 (mismatch!)
    oxford_row = {
        "word": "testword",
        "pos": ["noun"],
        "oxford_badge": "B2",
        "pos_data": [{
            "pos": "noun",
            "definitions": [{"text": "a test definition", "cefr": "B2"}]
        }]
    }
    temp_paths.oxford_jsonl.write_text(json.dumps(oxford_row) + "\n", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    
    card_row = "guid123\tNotetype\tDeck\ttestword\tnoun\t\t\t\t\t\t\t\t\t\tC1\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["unmatched"] == 1
    assert report.stats["oxford_exact"] == 0

def test_headword_cefr_badge_match(temp_paths):
    # Audit row asks for C1
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    # Oxford sense has no CEFR, but headword badge is C1 (matches!)
    oxford_row = {
        "word": "testword",
        "pos": ["noun"],
        "oxford_badge": "C1",
        "pos_data": [{
            "pos": "noun",
            "definitions": [{"text": "a test definition", "cefr": None}]
        }]
    }
    temp_paths.oxford_jsonl.write_text(json.dumps(oxford_row) + "\n", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    
    card_row = "guid123\tNotetype\tDeck\ttestword\tnoun\t\t\t\t\t\t\t\t\t\tC1\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["oxford_headword_cefr"] == 1

def test_oxford_5000_seed_override_requires_exact_seed_key(temp_paths):
    audit_row = {
        "word": "testword",
        "pos": "noun",
        "cefr": "C1",
        "def_before": "a test definition",
        "cefr_source": "oxford_5000_seed",
    }
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    temp_paths.oxford_jsonl.write_text(json.dumps({
        "word": "testword",
        "pos": ["noun"],
        "pos_data": [{
            "pos": "noun",
            "definitions": [{"text": "a test definition", "cefr": "C2"}],
        }],
    }) + "\n", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    temp_paths.oxford_5000_md.write_text(
        "| **testword** | n. | C1 |  |\n",
        encoding="utf-8",
    )
    card_row = "guid123\tNotetype\tDeck\ttestword\tnoun\t\t\t\t\t\t\t\t\t\tC1\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")

    report = check_def_before_integrity(temp_paths)

    assert report.stats["oxford_5000_seed"] == 1
    assert not report.has_errors()

    temp_paths.oxford_5000_md.write_text("", encoding="utf-8")
    report_without_seed = check_def_before_integrity(temp_paths)
    assert report_without_seed.stats["unmatched"] == 1

def test_idiom_match_exact_only(temp_paths):
    # Audit row asks for UNCLASSIFIED
    audit_row = {"word": "a test idiom", "pos": "idiom", "cefr": "UNCLASSIFIED", "def_before": "exact idiom meaning"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    oxford_row = {
        "word": "test",
        "pos": ["noun"],
        "idioms": [
            {"phrase": "a test idiom", "text": "exact idiom meaning"}
        ]
    }
    temp_paths.oxford_jsonl.write_text(json.dumps(oxford_row) + "\n", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    
    card_row = "guid123\tNotetype\tDeck\ta test idiom\tidiom\t\t\t\t\t\t\t\t\t\tUNCLASSIFIED\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["oxford_idiom"] == 1

def test_idiom_substring_rejected(temp_paths):
    # Audit row has substring of idiom text
    audit_row = {"word": "a test idiom", "pos": "idiom", "cefr": "UNCLASSIFIED", "def_before": "idiom meaning"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    oxford_row = {
        "word": "test",
        "pos": ["noun"],
        "idioms": [
            {"phrase": "a test idiom", "text": "exact idiom meaning"}  # "idiom meaning" is substring, not exact match!
        ]
    }
    temp_paths.oxford_jsonl.write_text(json.dumps(oxford_row) + "\n", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    
    card_row = "guid123\tNotetype\tDeck\ta test idiom\tidiom\t\t\t\t\t\t\t\t\t\tUNCLASSIFIED\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["unmatched"] == 1

def test_ambiguity_detection(temp_paths):
    # Audit row asks for C1
    audit_row = {"word": "testword", "pos": "noun", "cefr": "C1", "def_before": "a test definition"}
    temp_paths.deck_audit_jsonl.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
    
    # Oxford has multiple matching definitions (ambiguity!)
    oxford_row = {
        "word": "testword",
        "pos": ["noun"],
        "oxford_badge": "C1",
        "pos_data": [{
            "pos": "noun",
            "definitions": [
                {"text": "a test definition", "cefr": "C1"},
                {"text": "a test definition", "cefr": "C1"}
            ]
        }]
    }
    temp_paths.oxford_jsonl.write_text(json.dumps(oxford_row) + "\n", encoding="utf-8")
    temp_paths.manual_card_fills.write_text("[]", encoding="utf-8")
    
    card_row = "guid123\tNotetype\tDeck\ttestword\tnoun\t\t\t\t\t\t\t\t\t\tC1\t\tSource::Oxford"
    temp_paths.anki_notes_txt.write_text("#header\n" + card_row + "\n", encoding="utf-8")
    
    report = check_def_before_integrity(temp_paths)
    assert report.stats["ambiguous"] == 1
    assert len(report.ambiguous_rows) == 1
