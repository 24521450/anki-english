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


def test_validate_audio_gate_rejects_tracked_unreferenced_audio(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "oxford_uk_used.mp3").write_bytes(b"used")
    (audio_dir / "oxford_uk_orphan.mp3").write_bytes(b"orphan")

    report = validate_audio_gate(
        [_card("[sound:oxford_uk_used.mp3]")],
        audio_dir,
        {"oxford_uk_used.mp3", "oxford_uk_orphan.mp3"},
    )

    orphan_issues = [
        issue for issue in report.issues
        if issue.code == "audio_unreferenced_tracked_file"
    ]
    assert len(orphan_issues) == 1
    assert orphan_issues[0].source == audio_dir / "oxford_uk_orphan.mp3"


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


def test_validate_audio_gate_accepts_tracked_html_example_audio(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    filename = "example_uk_0123456789abcdef01234567.mp3"
    (audio_dir / filename).write_bytes(b"ID3" + b"x" * 509)
    card = _card()._replace(
        example_audio_uk=f'<audio preload="none" src="{filename}"></audio>',
    )

    report = validate_audio_gate([card], audio_dir, {filename})

    assert report.ok
    assert report.reference_count == 1


def test_validate_audio_gate_rejects_truncated_example_audio(tmp_path: Path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    filename = "example_uk_0123456789abcdef01234567.mp3"
    (audio_dir / filename).write_bytes(b"ID3truncated")
    card = _card()._replace(
        example_audio_uk=f'<audio preload="none" src="{filename}"></audio>',
    )

    report = validate_audio_gate([card], audio_dir, {filename})

    assert not report.ok
    assert any(issue.code == "audio_invalid_example_mp3" for issue in report.issues)
