import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
import src.pipeline as pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import resolve_stages, ALL_STAGES, DEFAULT_STAGES, main


def test_scrape_stage_calls_packaged_command_without_mutating_argv(monkeypatch):
    calls = []
    original_argv = list(sys.argv)
    monkeypatch.setattr(
        "src.scraper.rebuild_command.main",
        lambda argv: calls.append(argv) or 0,
    )

    assert pipeline.run_scrape(False) == 0
    assert calls == [[]]
    assert sys.argv == original_argv

def test_resolve_stages_default():
    # Resolution describes the requested build range; main adds live import.
    stages = resolve_stages(stage=None, from_stage=None, to_stage=None)
    assert stages == DEFAULT_STAGES
    assert "scrape" not in stages
    assert "import" not in stages

def test_resolve_stages_single():
    # Single-stage resolution remains literal.
    for s in ALL_STAGES:
        assert resolve_stages(stage=s) == [s]

def test_resolve_stages_from_to_flags():
    # Requested ranges retain their exact endpoints.
    assert resolve_stages(from_stage="build", to_stage="deck") == ["build", "validate", "deck"]
    assert resolve_stages(from_stage="scrape", to_stage="deck") == [
        "scrape", "example-audio", "build", "validate", "deck"
    ]
    # From defaults
    assert resolve_stages(from_stage="build", to_stage=None) == ["build", "validate", "deck"]
    assert resolve_stages(from_stage=None, to_stage="validate") == ["example-audio", "build", "validate"]


def test_import_is_available_as_an_explicit_stage_or_range_endpoint():
    assert resolve_stages(stage="import") == ["import"]
    assert resolve_stages(from_stage="deck", to_stage="import") == ["deck", "import"]


@pytest.mark.parametrize("stages", [
    ["deck"],
    ["build", "validate", "deck"],
    ["scrape", "example-audio", "build", "validate", "deck"],
])
def test_required_import_is_appended_to_real_deck_runs(stages):
    requested = list(stages)

    assert pipeline._append_required_import(stages, dry_run=False) == [
        *stages, "import"
    ]
    assert stages == requested


def test_required_import_is_not_duplicated_or_added_to_dry_run():
    assert pipeline._append_required_import(
        ["deck", "import"], dry_run=False
    ) == ["deck", "import"]
    assert pipeline._append_required_import(
        ["deck"], dry_run=True
    ) == ["deck"]


@pytest.mark.parametrize("argv", [
    ["deck"],
    ["--from", "deck", "--to", "deck"],
])
def test_pipeline_main_runs_import_after_deck(monkeypatch, argv):
    calls = []
    monkeypatch.setattr(
        pipeline,
        "run_deck",
        lambda dry_run: calls.append(("deck", dry_run)) or 0,
    )
    monkeypatch.setattr(
        pipeline,
        "run_import",
        lambda dry_run: calls.append(("import", dry_run)) or 0,
    )

    assert main(argv) == 0
    assert calls == [("deck", False), ("import", False)]


def test_pipeline_main_dry_run_does_not_append_import(monkeypatch):
    calls = []
    monkeypatch.setattr(
        pipeline,
        "run_deck",
        lambda dry_run: calls.append(("deck", dry_run)) or 0,
    )
    monkeypatch.setattr(
        pipeline,
        "run_import",
        lambda dry_run: calls.append(("import", dry_run)) or 0,
    )

    assert main(["deck", "--dry-run"]) == 0
    assert calls == [("deck", True)]


def test_pipeline_main_does_not_import_after_failed_deck(monkeypatch):
    calls = []
    monkeypatch.setattr(
        pipeline,
        "run_deck",
        lambda dry_run: calls.append(("deck", dry_run)) or 7,
    )
    monkeypatch.setattr(
        pipeline,
        "run_import",
        lambda dry_run: calls.append(("import", dry_run)) or 0,
    )

    assert main(["deck"]) == 7
    assert calls == [("deck", False)]


def test_pipeline_main_propagates_import_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(
        pipeline,
        "run_deck",
        lambda dry_run: calls.append(("deck", dry_run)) or 0,
    )
    monkeypatch.setattr(
        pipeline,
        "run_import",
        lambda dry_run: calls.append(("import", dry_run)) or 9,
    )

    assert main(["deck"]) == 9
    assert calls == [("deck", False), ("import", False)]

def test_resolve_stages_rejects_split():
    with pytest.raises(ValueError, match="Unknown stage 'split'"):
        resolve_stages(stage="split")
    with pytest.raises(ValueError, match="Unknown stage 'split'"):
        resolve_stages(from_stage="build", to_stage="split")

def test_resolve_stages_invalid_range():
    # start stage after end stage
    with pytest.raises(ValueError, match="Invalid range"):
        resolve_stages(from_stage="deck", to_stage="build")
        
    with pytest.raises(ValueError, match="Invalid range"):
        resolve_stages(stage="deck", to_stage="build")

def test_pipeline_main_handles_invalid_range(capsys):
    # main() returns non-zero and prints message on invalid ranges
    code = main(["--from", "deck", "--to", "build"])
    assert code != 0
    captured = capsys.readouterr()
    assert "Error: Invalid range" in captured.err or "Error: Invalid range" in captured.out


def test_pipeline_main_rejects_split_stage(capsys):
    code = main(["split", "--dry-run"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Unknown stage 'split'" in captured.err


def test_pipeline_main_rejects_split_range(capsys):
    code = main(["--from", "build", "--to", "split", "--dry-run"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Unknown stage 'split'" in captured.err


def test_validate_stage_fails_when_canonical_release_guard_rejects_state(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    notes_jsonl = tmp_path / "anki_notes.jsonl"
    notes_txt = tmp_path / "anki_notes.txt"
    notes_jsonl.write_text("{}\n", encoding="utf-8")
    notes_txt.write_text("fixture\n", encoding="utf-8")
    monkeypatch.setattr(pipeline, "NOTES_JSONL", notes_jsonl)
    monkeypatch.setattr(pipeline, "NOTES_TXT", notes_txt)
    monkeypatch.setattr(
        "src.deck_builder.build_validation.validate_artifact_paths",
        lambda *_args: SimpleNamespace(
            ok=True,
            card_count=1,
            jsonl_sha256="a" * 64,
            txt_sha256="b" * 64,
            deck_counts={"Deck": 1},
        ),
    )

    def reject(*_args, **_kwargs):
        raise ValueError("stale Semantic Registry")

    monkeypatch.setattr(
        "src.deck_builder.release_guard.run_release_guard",
        reject,
    )

    assert pipeline.run_validate(False) == 1
    assert "Canonical release guard failed" in capsys.readouterr().err
