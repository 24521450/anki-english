import sys
import json
import hashlib
from pathlib import Path
import pytest
import genanki

from src.config import ProjectPaths
from src.deck_builder.package_contract import json_value_for_key

paths = ProjectPaths()
PROJECT_ROOT = paths.root
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder import package_command as update_anki_deck


def _patch_production_templates(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    production_front = tmp_path / "production_front_template.txt"
    production_front.write_text(
        "{{#DefinitionVI}}{{#Example}}{{#ProductionAnswer}}"
        "{{DefinitionVI}}{{type:ProductionAnswer}}"
        "{{/ProductionAnswer}}{{/Example}}{{/DefinitionVI}}",
        encoding="utf-8",
    )
    production_prefix = tmp_path / "production_answer_prefix.txt"
    production_prefix.write_text("<div>{{FrontSide}}</div>", encoding="utf-8")
    monkeypatch.setattr(
        update_anki_deck, "PRODUCTION_FRONT_TEMPLATE", production_front
    )
    monkeypatch.setattr(
        update_anki_deck, "PRODUCTION_ANSWER_PREFIX", production_prefix
    )
    return production_front, production_prefix


@pytest.fixture(autouse=True)
def _production_design_paths(tmp_path: Path, monkeypatch):
    _patch_production_templates(tmp_path, monkeypatch)
    fixture_paths = ProjectPaths(tmp_path)
    monkeypatch.setattr(update_anki_deck, "paths", fixture_paths)
    monkeypatch.setattr(
        update_anki_deck,
        "validate_canonical_release_state",
        lambda project_paths: None,
    )
    for path in (
        fixture_paths.anki_notes_txt,
        fixture_paths.card_registry,
        fixture_paths.semantic_registry,
        fixture_paths.collocation_registry,
        fixture_paths.headword_audio_manifest,
        fixture_paths.bilingual_semantic_audit,
        fixture_paths.bilingual_idiom_audit,
        fixture_paths.collocation_audit,
        fixture_paths.vietnamese_naturalness_review,
        fixture_paths.semantic_policy_locks,
        fixture_paths.pronunciation_selection_locks,
        fixture_paths.definition_concision_review,
        fixture_paths.semantic_sense_merge_review,
        fixture_paths.cambridge_english_vietnamese_jsonl,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")


def test_packager_stops_before_inputs_when_canonical_guard_fails(
    monkeypatch, capsys,
):
    def reject(_project_paths):
        raise ValueError("stale Semantic Registry")

    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)
    monkeypatch.setattr(update_anki_deck, "validate_canonical_release_state", reject)

    assert update_anki_deck.main(["--dry-run"]) == 1
    assert "Canonical release guard failed" in capsys.readouterr().err

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
    assert update_anki_deck.EAVM_FIELD_NAMES[-9:] == (
        "DefinitionVI", "CambridgeURL", "OxfordPOSURLs", "ProductionAnswer",
        "SensePOS", "IdiomMeaningVI", "CollocationSources",
        "HeadwordAudioUKSrc", "HeadwordAudioUSSrc",
    )
    assert update_anki_deck.EAVM_FIELD_NAMES[22] == "ProductionAnswer"
    assert update_anki_deck.EAVM_FIELD_NAMES[23] == "SensePOS"
    assert update_anki_deck.EAVM_FIELD_NAMES[24] == "IdiomMeaningVI"
    assert update_anki_deck.EAVM_FIELD_NAMES[25] == "CollocationSources"
    assert update_anki_deck.EAVM_TEMPLATE_NAMES == (
        "Recognition", "Production (VI -> EN)",
    )


def test_headword_playback_sources_are_derived_from_established_sound_fields():
    row = {
        "uk_audio": "[sound:uk_word.mp3]",
        "us_audio": "[sound:us_word.mp3]",
        "headword_audio_uk_src": "untrusted.mp3",
    }

    assert json_value_for_key(row, "headword_audio_uk_src") == "uk_word.mp3"
    assert json_value_for_key(row, "headword_audio_us_src") == "us_word.mp3"


def test_template_loader_is_ordered_and_composes_production_answer(tmp_path: Path):
    front = tmp_path / "front.txt"
    back = tmp_path / "back.txt"
    production_front = tmp_path / "production-front.txt"
    production_prefix = tmp_path / "production-prefix.txt"
    front.write_text("recognition front", encoding="utf-8")
    back.write_text("recognition back", encoding="utf-8")
    production_front.write_text("prompt {{type:ProductionAnswer}}", encoding="utf-8")
    production_prefix.write_text("{{FrontSide}} answer ", encoding="utf-8")

    templates = update_anki_deck.load_eavm_templates(
        front, back, production_front, production_prefix
    )

    assert tuple(template.name for template in templates) == (
        "Recognition", "Production (VI -> EN)",
    )
    assert templates[0].back == "recognition back"
    assert templates[1].back == "{{FrontSide}} answer recognition back"


def test_genanki_model_emits_production_only_for_eligible_notes():
    templates = (
        update_anki_deck.EavmTemplate("Recognition", "{{Word}}", "{{Definition}}"),
        update_anki_deck.EavmTemplate(
            "Production (VI -> EN)",
            "{{#DefinitionVI}}{{#Example}}{{#ProductionAnswer}}"
            "prompt {{type:ProductionAnswer}}"
            "{{/ProductionAnswer}}{{/Example}}{{/DefinitionVI}}",
            "{{FrontSide}}",
        ),
    )
    model = genanki.Model(
        update_anki_deck.EAVM_MODEL_ID,
        update_anki_deck.EAVM_MODEL_NAME,
        fields=[{"name": name} for name in update_anki_deck.EAVM_FIELD_NAMES],
        templates=[template.for_genanki() for template in templates],
    )
    update_anki_deck.configure_genanki_requirements(model)
    values = [""] * len(update_anki_deck.EAVM_FIELD_NAMES)
    values[0] = "conquer"
    values[3] = "win"
    values[4] = "They conquered it."
    values[19] = "chiến thắng"
    values[22] = "conquer"
    eligible = genanki.Note(model=model, fields=values.copy(), guid="eligible")
    values[19] = ""
    ineligible = genanki.Note(model=model, fields=values, guid="ineligible")

    assert [card.ord for card in eligible.cards] == [0, 1]
    assert [card.ord for card in ineligible.cards] == [0]

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
        "production_answer": "conquer",
        "sense_pos": "verb|verb",
        "idiom_meaning_vi": "",
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
    old_receipt = update_anki_deck.verified_receipt_path_for(output_apkg)
    old_receipt.parent.mkdir(parents=True)
    old_receipt.write_text("stale", encoding="utf-8")

    # Run deck generator
    exit_code = update_anki_deck.main([])
    assert exit_code == 0
    assert output_apkg.exists()
    assert update_anki_deck.provenance_path_for(output_apkg).is_file()
    assert not old_receipt.exists()


def test_update_anki_deck_dry_run_does_not_write_release_artifacts(
    tmp_path: Path, monkeypatch,
):
    front_file = tmp_path / "front_template.txt"
    front_file.write_text("{{Word}}", encoding="utf-8")
    back_file = tmp_path / "back_template.txt"
    back_file.write_text("{{Definition}}", encoding="utf-8")
    styling_file = tmp_path / "styling.txt"
    styling_file.write_text("body {}", encoding="utf-8")
    notes_file = tmp_path / "anki_notes.jsonl"
    notes_file.write_text(
        json.dumps({
            "word": "conquer", "definition": "win", "deck": "Deck",
            "guid": "dry-run-guid",
        }) + "\n",
        encoding="utf-8",
    )
    output_apkg = tmp_path / "output_deck.apkg"
    monkeypatch.setattr(update_anki_deck, "NOTES_JSONL", notes_file)
    monkeypatch.setattr(update_anki_deck, "FRONT_TEMPLATE", front_file)
    monkeypatch.setattr(update_anki_deck, "BACK_TEMPLATE", back_file)
    monkeypatch.setattr(update_anki_deck, "STYLING_TXT", styling_file)
    monkeypatch.setattr(update_anki_deck, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(update_anki_deck, "OUTPUT_APKG", output_apkg)
    monkeypatch.setattr(update_anki_deck, "check_design_sync", lambda: True)
    receipt = update_anki_deck.verified_receipt_path_for(output_apkg)
    receipt.parent.mkdir(parents=True)
    receipt.write_text("existing receipt", encoding="utf-8")

    assert update_anki_deck.main(["--dry-run"]) == 0
    assert not output_apkg.exists()
    assert not update_anki_deck.provenance_path_for(output_apkg).exists()
    assert receipt.read_text(encoding="utf-8") == "existing receipt"

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
        "production_answer": "conquer",
        "sense_pos": "verb|verb",
        "idiom_meaning_vi": "bilingual_gloss :: nghĩa",
        "collocation_sources": "curated",
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
    note_data["cambridge_url"] = "https://dictionary.cambridge.org/dictionary/english/conquer"
    note_data["oxford_pos_urls"] = (
        "https://www.oxfordlearnersdictionaries.com/definition/english/conquer"
    )
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
    assert created["fields"][20:] == [
        "https://dictionary.cambridge.org/dictionary/english/conquer",
        "https://www.oxfordlearnersdictionaries.com/definition/english/conquer",
        "conquer",
        "verb|verb",
        "bilingual_gloss :: nghĩa",
        "curated",
        "uk_conquer.mp3",
        "us_conquer.mp3",
    ]
    assert created["guid"] == "test_guid_12345"
    assert created["tags"] == ["C1", "verb", "academic"]

