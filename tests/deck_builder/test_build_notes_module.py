import sys
import json
from pathlib import Path
import pytest
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.build_notes import (
    BuildNotesPaths,
    build_notes,
    lookup_gloss,
    _resolve_audio_filename,
    _parse_existing_txt
)
import tools.build_notes


def _setup_fixtures(tmp_path: Path):
    # oxford_merged.jsonl
    jsonl_file = tmp_path / "oxford_merged.jsonl"
    jsonl_data = [
        {
            "word": "conquer",
            "source_files": ["oxford_conquer.html"],
            "uk_ipa": "ˈkɒŋkə(r)",
            "us_ipa": "ˈkɑːŋkər",
            "audio": {"uk": "uk_url", "us": "us_url"},
            "pos_data": [{"pos": "verb", "definitions": [{"text": "take control by force"}]}]
        },
        {
            "word": "counter",
            "source_files": ["oxford_counter.html"],
            "uk_ipa": "ˈkaʊntə(r)",
            "pos_data": [
                {"pos": "verb", "definitions": [{"text": "oppose"}]},
                {"pos": "noun", "definitions": [{"text": "surface"}]}
            ]
        }
    ]
    jsonl_file.write_text("\n".join(json.dumps(r) for r in jsonl_data) + "\n", encoding="utf-8")

    # existing txt
    txt_file = tmp_path / "vocab.txt"
    header = (
        "#separator:tab\n"
        "#html:true\n"
        "#guid column:1\n"
        "#notetype column:2\n"
        "#deck column:3\n"
        "#tags column:17\n"
    )
    # 17 cols tab separated
    rows = [
        "\t".join(["guid_conq", "Model", "Deck Oxford", "conquer", "verb", "/ˈkɒŋkə(r)/", "take control", "ex", "", "", "[sound:uk.mp3]", "[sound:us.mp3]", "Oxford", "Oxford", "C1", "", "Source::Oxford CEFR::C1"]),
        "\t".join(["guid_counter", "Model", "Deck Oxford", "counter (argue against)", "verb", "/ˈkaʊntə(r)/", "oppose", "ex", "", "", "", "", "Oxford", "Oxford", "C1", "", "Source::Oxford CEFR::C1"])
    ]
    txt_file.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")

    # audit jsonl
    audit_file = tmp_path / "audit.jsonl"
    audit_data = [
        {"word": "counter (argue against)", "pos": "verb", "cefr": "C1", "gloss_after": "oppose specifically"},
        {"word": "counter", "pos": "verb", "cefr": "C1", "gloss_after": "ghost oppose"}
    ]
    audit_file.write_text("\n".join(json.dumps(r) for r in audit_data) + "\n", encoding="utf-8")

    # gamma verdicts
    gamma_file = tmp_path / "gamma.json"
    gamma_file.write_text(json.dumps({"verdicts": []}), encoding="utf-8")

    # oxford_3000, 5000, awl targets
    ox3 = tmp_path / "oxford_3000.md"
    ox3.write_text("| **conquer** | verb | C1 |\n", encoding="utf-8")
    
    ox5 = tmp_path / "oxford_5000.md"
    ox5.write_text("| **counter (argue against)** | verb | C1 |\n", encoding="utf-8")

    awl = tmp_path / "awl.md"
    awl.write_text("", encoding="utf-8")

    # filled json
    filled_file = tmp_path / "filled.json"
    filled_file.write_text(json.dumps([]), encoding="utf-8")

    # audio dir
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    return BuildNotesPaths(
        jsonl_path=jsonl_file,
        txt_path=txt_file,
        audit_jsonl_path=audit_file,
        gamma_verdicts_path=gamma_file,
        oxford_3000_md=ox3,
        oxford_5000_md=ox5,
        awl_md=awl,
        filled_path=filled_file,
        audio_dir=audio_dir
    )


def test_build_notes_preserves_guid_and_deck(tmp_path):
    paths = _setup_fixtures(tmp_path)
    res = build_notes(paths)
    assert res.built_cards_count == 2
    cards = {c.word: c for c in res.built_cards}
    
    # conquer card
    assert "conquer" in cards
    assert cards["conquer"].guid == "guid_conq"
    assert cards["conquer"].deck == "Deck Oxford"


def test_lookup_gloss_parenthetical_match_first():
    audit = {
        ("counter (argue against)", "verb", "C1"): "oppose specifically",
        ("counter", "verb", "C1"): "ghost oppose"
    }
    # Should exact match full parenthetical word first
    res = lookup_gloss(audit, "counter (argue against)", "verb", "C1", "counter", ["verb"], "C1")
    assert res == "oppose specifically"


def test_duplicate_emit_keys_skipped_first_wins(tmp_path):
    paths = _setup_fixtures(tmp_path)

    # Let's overwrite txt_path to have two rows resolving to the same key
    header = (
        "#separator:tab\n"
        "#html:true\n"
        "#guid column:1\n"
        "#notetype column:2\n"
        "#deck column:3\n"
        "#tags column:17\n"
    )
    rows = [
        "\t".join(["guid_first", "Model", "Deck Oxford", "conquer", "adjective", "/ˈkɒŋkə(r)/", "defn1", "ex1", "", "", "", "", "Oxford", "Oxford", "C1", "", "Source::Oxford CEFR::C1"]),
        "\t".join(["guid_second", "Model", "Deck Oxford", "conquer", "verb", "/ˈkɒŋkə(r)/", "defn2", "ex2", "", "", "", "", "Oxford", "Oxford", "C1", "", "Source::Oxford CEFR::C1"])
    ]
    paths.txt_path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")

    res = build_notes(paths)
    # First-wins: built cards should contain guid_first, not guid_second.
    assert res.built_cards_count == 1
    assert res.built_cards[0].guid == "guid_first"
    assert res.dup_emit_skip_count == 1


def test_filled_cards_preserved_verbatim(tmp_path):
    paths = _setup_fixtures(tmp_path)
    
    # Setup filled.json with conquer
    filled_data = [{"word": "conquer", "pos": "verb", "cefr": "C1"}]
    paths.filled_path.write_text(json.dumps(filled_data), encoding="utf-8")

    # Run build
    res = build_notes(paths)
    assert res.built_cards_count == 2
    cards = {c.word: c for c in res.built_cards}
    assert "conquer" in cards
    assert cards["conquer"].definition == "take control"  # from existing txt, not rebuilt from jsonl!


def test_audio_resolution_remains_unchanged(tmp_path):
    paths = _setup_fixtures(tmp_path)
    
    # Verify that lookup helper checks the set
    available = { "cambridge_uk_conquer.mp3" }
    res = _resolve_audio_filename("conquer", "uk", available)
    assert res == "[sound:cambridge_uk_conquer.mp3]"

    # If missing in audio_dir, fallback works (build_notes resolves to old sound:uk.mp3 from txt)
    res_build = build_notes(paths)
    conq_card = [c for c in res_build.built_cards if c.word == "conquer"][0]
    assert conq_card.uk_audio == "[sound:uk.mp3]"


def test_generated_outputs_are_deterministic(tmp_path):
    paths = _setup_fixtures(tmp_path)
    res1 = build_notes(paths)
    res2 = build_notes(paths)
    assert res1.jsonl_text == res2.jsonl_text
    assert res1.txt_text == res2.txt_text


def test_tools_build_notes_cli_dry_run(tmp_path, monkeypatch):
    paths = _setup_fixtures(tmp_path)
    
    # Overwrite tools constants to use tmp_path values
    monkeypatch.setattr(tools.build_notes, "JSONL_PATH", paths.jsonl_path)
    monkeypatch.setattr(tools.build_notes, "GAMMA_VERDICTS_PATH", paths.gamma_verdicts_path)
    monkeypatch.setattr(tools.build_notes, "TXT_PATH", paths.txt_path)
    monkeypatch.setattr(tools.build_notes, "OUT_JSONL", tmp_path / "anki_notes.jsonl")
    monkeypatch.setattr(tools.build_notes, "OXFORD_3000_MD", paths.oxford_3000_md)
    monkeypatch.setattr(tools.build_notes, "OXFORD_5000_MD", paths.oxford_5000_md)
    monkeypatch.setattr(tools.build_notes, "AWL_MD", paths.awl_md)
    monkeypatch.setattr(tools.build_notes, "AUDIT_JSONL_PATH", paths.audit_jsonl_path)
    monkeypatch.setattr(tools.build_notes, "FILLED_PATH", paths.filled_path)
    monkeypatch.setattr(tools.build_notes, "AUDIO_DIR", paths.audio_dir)

    out_jsonl = tmp_path / "anki_notes.jsonl"
    argv = ["--dry-run", "--out-jsonl", str(out_jsonl)]
    
    # Let's monkeypatch sys.argv before calling main()
    monkeypatch.setattr(sys, "argv", ["build_notes.py"] + argv)
    
    code = tools.build_notes.main()
    assert code == 0
    assert not out_jsonl.exists()

    # Non-dry-run: should write files and backups
    monkeypatch.setattr(sys, "argv", ["build_notes.py", "--out-jsonl", str(out_jsonl)])
    code = tools.build_notes.main()
    assert code == 0
    assert out_jsonl.exists()
    
    # Check that backup file exists
    backups = list(paths.txt_path.parent.glob("vocab.txt.bak_pre_build_*"))
    assert len(backups) == 1
