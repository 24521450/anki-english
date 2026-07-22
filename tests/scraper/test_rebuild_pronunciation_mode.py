from __future__ import annotations

from src.scraper import rebuild_command


def test_cambridge_only_does_not_parse_or_write_oxford(monkeypatch, tmp_path):
    calls = []

    def fake_run_source(source_dir, parser, output, label):
        calls.append((source_dir, parser, output, label))
        return {"records": 3, "skipped": 1, "errors": 0, "error_rate": 0.0}

    monkeypatch.setattr(rebuild_command, "LOG_PATH", str(tmp_path / "rebuild.log"))
    monkeypatch.setattr(rebuild_command, "CAMBRIDGE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(rebuild_command, "CAMBRIDGE_OUT", str(tmp_path / "cambridge.jsonl"))
    monkeypatch.setattr(rebuild_command, "run_source", fake_run_source)

    assert rebuild_command.main(["--cambridge-only"]) == 0
    assert len(calls) == 1
    assert calls[0][3] == "Cambridge"


def test_source_only_modes_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(
        rebuild_command,
        "run_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert rebuild_command.main(["--oxford-only", "--cambridge-only"]) == 2
