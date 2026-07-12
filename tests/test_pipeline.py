import sys
from pathlib import Path
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
    # If no stage or flags, run default pipeline: build -> validate -> deck
    stages = resolve_stages(stage=None, from_stage=None, to_stage=None)
    assert stages == DEFAULT_STAGES
    assert "scrape" not in stages

def test_resolve_stages_single():
    # Single stage runs just that stage
    for s in ALL_STAGES:
        assert resolve_stages(stage=s) == [s]

def test_resolve_stages_from_to_flags():
    # From build to deck range
    assert resolve_stages(from_stage="build", to_stage="deck") == ["build", "validate", "deck"]
    # Full range from scrape to deck
    assert resolve_stages(from_stage="scrape", to_stage="deck") == ["scrape", "build", "validate", "deck"]
    # From defaults
    assert resolve_stages(from_stage="build", to_stage=None) == ["build", "validate", "deck"]
    assert resolve_stages(from_stage=None, to_stage="validate") == ["build", "validate"]

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
