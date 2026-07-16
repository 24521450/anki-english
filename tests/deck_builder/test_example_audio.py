from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

from src.config import ProjectPaths
from src.deck_builder import example_audio_command
from src.deck_builder.build_contracts import BuiltCard
from src.deck_builder.example_audio import (
    VOICES,
    clean_example_text,
    generate_example_audio,
    plan_card_example_audio,
    plan_cards_example_audio,
)


def _card(*, example: str = "", idioms: str = "") -> BuiltCard:
    return BuiltCard(
        "g", "English Academic Vocabulary Model", "Deck", "word", "noun", "",
        "definition", example, "", "", "", "", "Oxford", "Oxford", "B2",
        idioms, "Source::Oxford", "", "",
    )


def test_cleaner_removes_annotations_and_normalizes_placeholders():
    assert clean_example_text("  He gave it away (give away). ") == "He gave it away."
    assert clean_example_text("give sb/sth a(n) answer") == "give somebody or something an answer"
    assert clean_example_text("one / two") == "one or two"


def test_planner_rejects_annotation_only_example():
    with pytest.raises(ValueError, match="became empty"):
        plan_card_example_audio(_card(example="(give away)"))


def test_planner_aligns_main_and_idiom_examples_and_deduplicates():
    card = _card(
        example="First sentence.<br><br>Shared sentence.|",
        idioms="one :: meaning :: Shared sentence.$$two :: meaning",
    )
    planned, tasks = plan_card_example_audio(card)

    assert planned.example_audio_uk.count("<audio ") == 2
    assert planned.example_audio_uk.endswith("|")
    assert planned.idiom_example_audio_uk.count("<audio ") == 1
    assert planned.idiom_example_audio_uk.endswith("$$")
    # Shared sentence is reused across the main field and Idiom Box.
    _, all_tasks = plan_cards_example_audio([card])
    assert len(tasks) == 6
    assert len(all_tasks) == 4
    assert all(task.filename.startswith(f"example_{task.accent}_") for task in all_tasks)


def test_planner_preserves_empty_first_idiom_audio_slot_for_both_accents():
    card = _card(
        idioms="one :: meaning$$two :: meaning :: Second idiom example.",
    )

    planned, _ = plan_card_example_audio(card)

    assert planned.idiom_example_audio_uk.startswith("$$<audio ")
    assert planned.idiom_example_audio_us.startswith("$$<audio ")
    assert planned.idiom_example_audio_uk.count("<audio ") == 1
    assert planned.idiom_example_audio_us.count("<audio ") == 1


def test_hash_changes_with_accent_and_is_stable():
    card = _card(example="A stable sentence.")
    first, _ = plan_card_example_audio(card)
    second, _ = plan_card_example_audio(card)
    assert first == second
    assert first.example_audio_uk != first.example_audio_us


def test_generator_resumes_atomically_and_prunes_after_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, str, str, str]] = []

    class FakeCommunicate:
        def __init__(self, text, voice, *, rate, pitch, volume, connect_timeout, receive_timeout):
            calls.append((text, voice, rate, pitch))
            assert (connect_timeout, receive_timeout) == (10, 60)

        async def save(self, path):
            Path(path).write_bytes(b"ID3" + b"x" * 509)

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=FakeCommunicate))
    card = _card(example="Generate me.")
    planned, tasks = plan_cards_example_audio([card])
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "example_uk_stale.mp3").write_bytes(b"ID3" + b"x" * 509)

    first = asyncio.run(generate_example_audio(planned, audio_dir))
    mtimes = {task.filename: (audio_dir / task.filename).stat().st_mtime_ns for task in tasks}
    second = asyncio.run(generate_example_audio(planned, audio_dir))

    assert first.generated == 2
    assert first.pruned == 1
    assert second.generated == 0
    assert second.reused == 2
    assert len(calls) == 2
    assert {voice for _, voice, _, _ in calls} == set(VOICES.values())
    assert mtimes == {task.filename: (audio_dir / task.filename).stat().st_mtime_ns for task in tasks}


def test_dry_run_has_no_side_effects(tmp_path: Path):
    audio_dir = tmp_path / "missing-audio"
    report = asyncio.run(generate_example_audio([_card(example="Plan only.")], audio_dir, dry_run=True))
    assert report.generated == 2
    assert not audio_dir.exists()


def test_production_example_audio_fails_closed_without_semantic_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setattr(
        example_audio_command,
        "ProjectPaths",
        lambda: ProjectPaths(tmp_path),
    )

    assert example_audio_command.main(["--dry-run"]) == 1
    assert "Semantic Registry file missing" in capsys.readouterr().err


def test_failed_generation_keeps_stale_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class FailingCommunicate:
        def __init__(self, *args, **kwargs):
            pass

        async def save(self, path):
            raise OSError("network down")

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=FailingCommunicate))
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    stale = audio_dir / "example_uk_stale.mp3"
    stale.write_bytes(b"ID3" + b"x" * 509)

    with pytest.raises(RuntimeError, match="failed to generate"):
        asyncio.run(generate_example_audio([_card(example="Failure.")], audio_dir, retries=1))
    assert stale.exists()
