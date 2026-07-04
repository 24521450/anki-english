from __future__ import annotations

from pathlib import Path

from src.deck_builder.audio_gate import validate_audio_gate
from src.deck_builder.build_contracts import BuiltCard


def _card(audio: str = "") -> BuiltCard:
    return BuiltCard(
        "g1",
        "English Academic Vocabulary Model",
        "Deck",
        "word",
        "noun",
        "",
        "definition",
        "example",
        "",
        "",
        audio,
        "",
        "Oxford",
        "Oxford",
        "A1",
        "",
        "Source::Oxford CEFR::A1 CEFR::oxford",
        "",
        "",
    )


def test_validate_audio_gate_accepts_tracked_dictionary_audio(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "oxford_uk_word.mp3").write_bytes(b"mp3")

    report = validate_audio_gate([_card("[sound:oxford_uk_word.mp3]")], audio_dir, {"oxford_uk_word.mp3"})

    assert report.ok


def test_validate_audio_gate_rejects_untracked_audio(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "oxford_uk_word.mp3").write_bytes(b"mp3")

    report = validate_audio_gate([_card("[sound:oxford_uk_word.mp3]")], audio_dir, set())

    assert not report.ok
    assert any(issue.code == "audio_referenced_but_untracked" for issue in report.issues)


def test_validate_audio_gate_rejects_case_mismatch(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "cambridge_uk_Hypothesis.mp3").write_bytes(b"mp3")

    report = validate_audio_gate([_card("[sound:cambridge_uk_hypothesis.mp3]")], audio_dir, {"cambridge_uk_hypothesis.mp3"})

    assert not report.ok
    assert any(issue.code == "audio_case_mismatch" for issue in report.issues)


def test_validate_audio_gate_rejects_tts_reference_and_file(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "tts_uk_word.mp3").write_bytes(b"mp3")

    report = validate_audio_gate([_card("[sound:tts_uk_word.mp3]")], audio_dir, {"tts_uk_word.mp3"})

    assert not report.ok
    assert any(issue.code == "audio_tts_reference" for issue in report.issues)
    assert any(issue.code == "audio_tts_file_present" for issue in report.issues)
