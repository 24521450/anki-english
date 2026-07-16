import sys
import json
import hashlib
from pathlib import Path
import pytest
import genanki

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = paths.root
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder import package_command as update_anki_deck

def test_generate_deterministic_id():
    name = "Test Deck"
    deck_id = update_anki_deck.generate_deterministic_id(name)
    assert isinstance(deck_id, int)
    assert 1 <= deck_id <= 2**31 - 1
    # Check stable across runs
    assert deck_id == update_anki_deck.generate_deterministic_id(name)


def test_eavm_model_identity_matches_existing_anki_note_type():
    assert update_anki_deck.EAVM_MODEL_NAME == "English Academic Vocabulary Model"
    assert update_anki_deck.EAVM_MODEL_ID == 1607392819
    assert update_anki_deck.EAVM_MODEL_ID != update_anki_deck.generate_deterministic_id(
        update_anki_deck.EAVM_MODEL_NAME
    )
    assert update_anki_deck.EAVM_FIELD_NAMES[-1] == "DefinitionVI"

def test_extract_audio_filename():
    assert update_anki_deck.extract_audio_filename("[sound:hello.mp3]") == "hello.mp3"
    assert update_anki_deck.extract_audio_filename("[sound: UK_hello_pos.mp3]") == "UK_hello_pos.mp3"
    assert update_anki_deck.extract_audio_filename("invalid_sound") is None
    assert update_anki_deck.extract_audio_filename("") is None


def test_extract_audio_filenames_supports_aligned_html_audio():
    value = (
        '<audio preload="none" src="example_uk_a.mp3"></audio>|'
        '<audio preload="none" src="example_uk_b.mp3"></audio>'
    )
    assert update_anki_deck.extract_audio_filenames(value) == [
        "example_uk_a.mp3", "example_uk_b.mp3"
    ]


@pytest.mark.parametrize("value", ["|", "$$", "$$|$$", "<br><br>"])
def test_empty_audio_layout_accepts_alignment_delimiters(value):
    assert update_anki_deck.is_empty_audio_layout(value)


def test_empty_audio_layout_rejects_unparsed_content():
    assert not update_anki_deck.is_empty_audio_layout("not-an-audio-reference")

def test_update_anki_deck_success(tmp_path, monkeypatch):
    # Setup mock templates
    front_file = tmp_path / "front_template.txt"
    front_file.write_text("{{Word}}", encoding="utf-8")
    back_file = tmp_path / "back_template.txt"
    back_file.write_text("{{Definition}}", encoding="utf-8")
    styling_file = tmp_path / "styling.txt"
    styling_file.write_text("body {}", encoding="utf-8")

    # Setup mock notes JSONL
    notes_file = tmp_path / "anki_notes.jsonl"
    note_data = {
        "word": "conquer",
        "pos": "verb",
        "cefr": "C1",
        "definition": "take control by force|overcome",
        "definition_vi": "chiếm quyền kiểm soát|vượt qua",
        "example": "to conquer the world",
        "ipa": "/ˈkɒŋkə(r)/",
        "uk_audio": "[sound:uk_conquer.mp3]",
        "us_audio": "",
        "tags": "C1 verb",
        "collocations": "",
        "wordfamily": "",
        "idioms": "",
        "deck": "IELTS Academic::C1",
        "guid": "test_guid_12345"
    }
    notes_file.write_text(json.dumps(note_data) + "\n", encoding="utf-8")

    # Setup mock audio files
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    audio_file = audio_dir / "uk_conquer.mp3"
    audio_file.write_bytes(b"mock_mp3_data")

    output_apkg = tmp_path / "output_deck.apkg"

    # Monkeypatch paths
    monkeypatch.setattr(update_anki_deck, "NOTES_JSONL", notes_file)
    monkeypatch.setattr(update_anki_deck, "FRONT_TEMPLATE", front_file)
    monkeypatch.setattr(update_anki_deck, "BACK_TEMPLATE", back_file)
    monkeypatch.setattr(update_anki_deck, "STYLING_TXT", styling_file)
    monkeypatch.setattr(update_anki_deck, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(update_anki_deck, "OUTPUT_APKG", output_apkg)

    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)

    # Run deck generator
    exit_code = update_anki_deck.main([])
    assert exit_code == 0
    assert output_apkg.exists()

def test_update_anki_deck_missing_guid(tmp_path, monkeypatch):
    # Setup mock templates
    front_file = tmp_path / "front_template.txt"
    front_file.write_text("{{Word}}", encoding="utf-8")
    back_file = tmp_path / "back_template.txt"
    back_file.write_text("{{Definition}}", encoding="utf-8")
    styling_file = tmp_path / "styling.txt"
    styling_file.write_text("body {}", encoding="utf-8")

    # Setup notes without GUID
    notes_file = tmp_path / "anki_notes.jsonl"
    note_data = {
        "word": "conquer",
        "pos": "verb",
        "cefr": "C1",
        "definition": "take control",
        "example": "example",
        "ipa": "/ipa/",
        "uk_audio": "",
        "us_audio": "",
        "tags": "",
        "collocations": "",
        "wordfamily": "",
        "idioms": "",
        "deck": "IELTS Academic::C1",
        # "guid" is missing
    }
    notes_file.write_text(json.dumps(note_data) + "\n", encoding="utf-8")

    # Monkeypatch paths
    monkeypatch.setattr(update_anki_deck, "NOTES_JSONL", notes_file)
    monkeypatch.setattr(update_anki_deck, "FRONT_TEMPLATE", front_file)
    monkeypatch.setattr(update_anki_deck, "BACK_TEMPLATE", back_file)
    monkeypatch.setattr(update_anki_deck, "STYLING_TXT", styling_file)
    monkeypatch.setattr(update_anki_deck, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(update_anki_deck, "OUTPUT_APKG", tmp_path / "output_deck.apkg")

    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)

    exit_code = update_anki_deck.main([])
    assert exit_code != 0

def test_update_anki_deck_malformed_audio(tmp_path, monkeypatch):
    # Setup mock templates
    front_file = tmp_path / "front_template.txt"
    front_file.write_text("{{Word}}", encoding="utf-8")
    back_file = tmp_path / "back_template.txt"
    back_file.write_text("{{Definition}}", encoding="utf-8")
    styling_file = tmp_path / "styling.txt"
    styling_file.write_text("body {}", encoding="utf-8")

    # Setup notes with malformed audio
    notes_file = tmp_path / "anki_notes.jsonl"
    note_data = {
        "word": "conquer",
        "pos": "verb",
        "cefr": "C1",
        "definition": "take control",
        "example": "example",
        "ipa": "/ipa/",
        "uk_audio": "malformed_audio_reference.mp3",  # Not wrapped in [sound:...]
        "us_audio": "",
        "tags": "",
        "collocations": "",
        "wordfamily": "",
        "idioms": "",
        "deck": "IELTS Academic::C1",
        "guid": "guid_abc"
    }
    notes_file.write_text(json.dumps(note_data) + "\n", encoding="utf-8")

    # Monkeypatch paths
    monkeypatch.setattr(update_anki_deck, "NOTES_JSONL", notes_file)
    monkeypatch.setattr(update_anki_deck, "FRONT_TEMPLATE", front_file)
    monkeypatch.setattr(update_anki_deck, "BACK_TEMPLATE", back_file)
    monkeypatch.setattr(update_anki_deck, "STYLING_TXT", styling_file)
    monkeypatch.setattr(update_anki_deck, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(update_anki_deck, "OUTPUT_APKG", tmp_path / "output_deck.apkg")

    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)

    exit_code = update_anki_deck.main([])
    assert exit_code != 0

def test_update_anki_deck_missing_audio(tmp_path, monkeypatch):
    # Setup mock templates
    front_file = tmp_path / "front_template.txt"
    front_file.write_text("{{Word}}", encoding="utf-8")
    back_file = tmp_path / "back_template.txt"
    back_file.write_text("{{Definition}}", encoding="utf-8")
    styling_file = tmp_path / "styling.txt"
    styling_file.write_text("body {}", encoding="utf-8")

    # Setup notes with missing audio
    notes_file = tmp_path / "anki_notes.jsonl"
    note_data = {
        "word": "conquer",
        "pos": "verb",
        "cefr": "C1",
        "definition": "take control",
        "example": "example",
        "ipa": "/ipa/",
        "uk_audio": "[sound:missing_audio_reference.mp3]",
        "us_audio": "",
        "tags": "",
        "collocations": "",
        "wordfamily": "",
        "idioms": "",
        "deck": "IELTS Academic::C1",
        "guid": "guid_abc"
    }
    notes_file.write_text(json.dumps(note_data) + "\n", encoding="utf-8")

    # Monkeypatch paths
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    monkeypatch.setattr(update_anki_deck, "NOTES_JSONL", notes_file)
    monkeypatch.setattr(update_anki_deck, "FRONT_TEMPLATE", front_file)
    monkeypatch.setattr(update_anki_deck, "BACK_TEMPLATE", back_file)
    monkeypatch.setattr(update_anki_deck, "STYLING_TXT", styling_file)
    monkeypatch.setattr(update_anki_deck, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(update_anki_deck, "OUTPUT_APKG", tmp_path / "output_deck.apkg")

    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)

    exit_code = update_anki_deck.main([])
    assert exit_code != 0

def test_update_anki_deck_multiple_subdecks(tmp_path, monkeypatch):
    # Setup mock templates
    front_file = tmp_path / "front_template.txt"
    front_file.write_text("{{Word}}", encoding="utf-8")
    back_file = tmp_path / "back_template.txt"
    back_file.write_text("{{Definition}}", encoding="utf-8")
    styling_file = tmp_path / "styling.txt"
    styling_file.write_text("body {}", encoding="utf-8")

    # Setup notes with different decks
    notes_file = tmp_path / "anki_notes.jsonl"
    notes = [
        {
            "word": "conquer", "pos": "verb", "cefr": "C1", "definition": "def",
            "example": "ex", "ipa": "/ipa/", "uk_audio": "", "us_audio": "",
            "tags": "", "collocations": "", "wordfamily": "", "idioms": "",
            "deck": "IELTS Academic::C1", "guid": "guid1"
        },
        {
            "word": "consciousness", "pos": "noun", "cefr": "B2", "definition": "def2",
            "example": "ex2", "ipa": "/ipa2/", "uk_audio": "", "us_audio": "",
            "tags": "", "collocations": "", "wordfamily": "", "idioms": "",
            "deck": "IELTS Academic::B2", "guid": "guid2"
        }
    ]
    notes_file.write_text("\n".join(json.dumps(n) for n in notes) + "\n", encoding="utf-8")

    # Monkeypatch paths
    monkeypatch.setattr(update_anki_deck, "NOTES_JSONL", notes_file)
    monkeypatch.setattr(update_anki_deck, "FRONT_TEMPLATE", front_file)
    monkeypatch.setattr(update_anki_deck, "BACK_TEMPLATE", back_file)
    monkeypatch.setattr(update_anki_deck, "STYLING_TXT", styling_file)
    monkeypatch.setattr(update_anki_deck, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(update_anki_deck, "OUTPUT_APKG", tmp_path / "output_deck.apkg")

    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)

    # We want to intercept the decks and check if both exist
    original_deck_init = genanki.Deck.__init__
    decks_created = []

    def mock_deck_init(self, deck_id, name, *args, **kwargs):
        decks_created.append(name)
        original_deck_init(self, deck_id, name, *args, **kwargs)

    monkeypatch.setattr(genanki.Deck, "__init__", mock_deck_init)

    exit_code = update_anki_deck.main([])
    assert exit_code == 0
    assert "IELTS Academic::C1" in decks_created
    assert "IELTS Academic::B2" in decks_created

def test_update_anki_deck_note_fields_and_guid_preservation(tmp_path, monkeypatch):
    # Setup mock templates
    front_file = tmp_path / "front_template.txt"
    front_file.write_text("{{Word}}", encoding="utf-8")
    back_file = tmp_path / "back_template.txt"
    back_file.write_text("{{Definition}}", encoding="utf-8")
    styling_file = tmp_path / "styling.txt"
    styling_file.write_text("body {}", encoding="utf-8")

    # Setup mock notes JSONL
    notes_file = tmp_path / "anki_notes.jsonl"
    note_data = {
        "word": "conquer",
        "pos": "verb",
        "cefr": "C1",
        "definition": "take control by force|overcome",
        "definition_vi": "chiếm quyền kiểm soát|vượt qua",
        "example": "to conquer the world",
        "ipa": "/ˈkɒŋkə(r)/",
        "uk_audio": "[sound:uk_conquer.mp3]",
        "us_audio": "[sound:us_conquer.mp3]",
        "tags": "C1 verb academic",
        "collocations": "colloc",
        "wordfamily": "family",
        "idioms": "idiom",
        "deck": "IELTS Academic::C1",
        "guid": "test_guid_12345"
    }
    notes_file.write_text(json.dumps(note_data) + "\n", encoding="utf-8")

    # Setup mock audio files
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "uk_conquer.mp3").write_bytes(b"uk")
    (audio_dir / "us_conquer.mp3").write_bytes(b"us")

    # Monkeypatch paths
    monkeypatch.setattr(update_anki_deck, "NOTES_JSONL", notes_file)
    monkeypatch.setattr(update_anki_deck, "FRONT_TEMPLATE", front_file)
    monkeypatch.setattr(update_anki_deck, "BACK_TEMPLATE", back_file)
    monkeypatch.setattr(update_anki_deck, "STYLING_TXT", styling_file)
    monkeypatch.setattr(update_anki_deck, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(update_anki_deck, "OUTPUT_APKG", tmp_path / "output_deck.apkg")

    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)

    # Intercept Note creation
    notes_created = []
    original_note_init = genanki.Note.__init__

    def mock_note_init(self, model=None, fields=None, guid=None, tags=None, *args, **kwargs):
        notes_created.append({
            "fields": fields,
            "guid": guid,
            "tags": tags
        })
        original_note_init(self, model=model, fields=fields, guid=guid, tags=tags, *args, **kwargs)

    monkeypatch.setattr(genanki.Note, "__init__", mock_note_init)

    exit_code = update_anki_deck.main([])
    assert exit_code == 0
    assert len(notes_created) == 1
    created = notes_created[0]
    
    assert created["fields"][0:2] == ["conquer", "verb"]
    assert created["fields"][2] == "/ˈkɒŋkə(r)/"
    assert created["fields"][3:7] == [
        "take control by force|overcome",
        "to conquer the world",
        "colloc",
        "family",
    ]
    assert created["fields"][7:15] == [
        "[sound:uk_conquer.mp3]",
        "[sound:us_conquer.mp3]",
        "",
        "",
        "C1",
        "idiom",
        "",
        "",
    ]
    assert created["fields"][15:19] == ["", "", "", ""]
    assert created["fields"][19] == "chiếm quyền kiểm soát|vượt qua"
    assert created["guid"] == "test_guid_12345"
    assert created["tags"] == ["C1", "verb", "academic"]

