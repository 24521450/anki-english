import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import resolve_stages, ALL_STAGES, DEFAULT_STAGES, main

def test_resolve_stages_default():
    # If no stage or flags, run default pipeline: build -> split -> deck
    stages = resolve_stages(stage=None, from_stage=None, to_stage=None)
    assert stages == DEFAULT_STAGES
    assert "scrape" not in stages

def test_resolve_stages_single():
    # Single stage runs just that stage
    for s in ALL_STAGES:
        assert resolve_stages(stage=s) == [s]

def test_resolve_stages_from_to_flags():
    # From build to deck range
    assert resolve_stages(from_stage="build", to_stage="deck") == ["build", "split", "deck"]
    # Full range from scrape to deck
    assert resolve_stages(from_stage="scrape", to_stage="deck") == ["scrape", "build", "split", "deck"]
    # From defaults
    assert resolve_stages(from_stage="build", to_stage=None) == ["build", "split", "deck"]
    assert resolve_stages(from_stage=None, to_stage="split") == ["build", "split"]

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
