#!/usr/bin/env python3
"""Production orchestrator: scrape -> example-audio -> build -> validate -> deck -> import.

Run with:
    python -m src.pipeline

Every real run that packages a deck continues to verified Anki import.
Supports stage ranges, dry-runs, and explicit cache parsing.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = paths.root
NOTES_JSONL = paths.anki_notes_jsonl
NOTES_TXT = paths.anki_notes_txt

ALL_STAGES = ["scrape", "example-audio", "build", "validate", "deck", "import"]
# The requested default range ends at packaging; main appends the mandatory
# live import finalizer to real (non-dry-run) executions.
DEFAULT_STAGES = ["example-audio", "build", "validate", "deck"]


def _canonical_stage(stage: str) -> str:
    if stage in ALL_STAGES:
        return stage
    raise ValueError(f"Unknown stage '{stage}'")

def run_scrape(dry_run: bool) -> int:
    print("=== Pipeline: Running scrape stage ===", file=sys.stderr)
    if dry_run:
        print("[dry-run] scrape: Would parse HTML cache and merge Oxford records.", file=sys.stderr)
        return 0
        
    from src.scraper.rebuild_command import main as run_full_cache

    # The production pipeline always rebuilds both Oxford and Cambridge.
    return run_full_cache([])

def run_build(dry_run: bool) -> int:
    print("=== Pipeline: Running build stage ===", file=sys.stderr)
    from src.deck_builder.build_command import main as run_build_notes
    argv = ["--dry-run"] if dry_run else []
    return run_build_notes(argv)


def run_example_audio(dry_run: bool) -> int:
    print("=== Pipeline: Running example-audio stage ===", file=sys.stderr)
    from src.deck_builder.example_audio_command import main as run_example_audio_command
    argv = ["--dry-run"] if dry_run else []
    return run_example_audio_command(argv)

def run_validate(dry_run: bool) -> int:
    print("=== Pipeline: Running validate stage ===", file=sys.stderr)
    if not NOTES_JSONL.exists() or not NOTES_TXT.exists():
        print("Error: build artifacts not found. Cannot run validate stage.", file=sys.stderr)
        return 1

    from src.deck_builder.build_validation import validate_artifact_paths

    report = validate_artifact_paths(
        NOTES_JSONL,
        NOTES_TXT,
        paths.card_registry,
        paths.audio_dir,
    )
    if not report.ok:
        print("Validation failed:", file=sys.stderr)
        print(report.error_text(), file=sys.stderr)
        return 1

    from src.deck_builder.release_guard import run_release_guard

    try:
        guard_report = run_release_guard(paths, "canonical")
    except (OSError, ValueError) as exc:
        print(f"Canonical release guard failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"  Validation OK: cards={report.card_count} "
        f"jsonl_sha256={report.jsonl_sha256} txt_sha256={report.txt_sha256}",
        file=sys.stderr,
    )
    print(
        "  Canonical release guard OK: "
        f"checks={','.join(guard_report.checks)}",
        file=sys.stderr,
    )
    print("  Deck distribution summary:", file=sys.stderr)
    for deck, count in report.deck_counts.items():
        print(f"    - {deck}: {count} cards", file=sys.stderr)
    return 0


def run_deck(dry_run: bool) -> int:
    print("=== Pipeline: Running deck stage ===", file=sys.stderr)
    from src.deck_builder.package_command import main as run_update_anki_deck
    argv = ["--dry-run"] if dry_run else []
    return run_update_anki_deck(argv)


def run_import(dry_run: bool) -> int:
    print("=== Pipeline: Running import stage ===", file=sys.stderr)
    from src.deck_builder.anki_import_command import main as run_anki_import
    argv = ["--dry-run"] if dry_run else []
    return run_anki_import(argv)

def resolve_stages(stage: str | None = None, from_stage: str | None = None, to_stage: str | None = None) -> list[str]:
    """Resolve active stages based on CLI arguments and defaults."""
    if stage:
        stage = _canonical_stage(stage)
        if to_stage:
            to_stage = _canonical_stage(to_stage)
            start_idx = ALL_STAGES.index(stage)
            end_idx = ALL_STAGES.index(to_stage)
            if start_idx > end_idx:
                raise ValueError(f"Invalid range -- from '{stage}' to '{to_stage}'")
            return ALL_STAGES[start_idx : end_idx + 1]
        else:
            return [stage]
    else:
        if from_stage or to_stage:
            start_stage = _canonical_stage(from_stage or "example-audio")
            end_stage = _canonical_stage(to_stage or "deck")
            start_idx = ALL_STAGES.index(start_stage)
            end_idx = ALL_STAGES.index(end_stage)
            if start_idx > end_idx:
                raise ValueError(f"Invalid range -- from '{start_stage}' to '{end_stage}'")
            return ALL_STAGES[start_idx : end_idx + 1]
        else:
            return DEFAULT_STAGES


def _append_required_import(stages: list[str], *, dry_run: bool) -> list[str]:
    """Append the live-import finalizer without mutating the requested range."""
    effective = list(stages)
    if not dry_run and "deck" in effective and "import" not in effective:
        effective.append("import")
    return effective

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Production-stage orchestrator")
    ap.add_argument("stage", nargs="?", help="Run a single stage")
    ap.add_argument("--from", dest="from_stage", help="Start stage")
    ap.add_argument("--to", dest="to_stage", help="End stage")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Run non-writing checks without appending the automatic live import",
    )
    args = ap.parse_args(argv)

    try:
        requested_stages = resolve_stages(args.stage, args.from_stage, args.to_stage)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    stages_to_run = _append_required_import(
        requested_stages,
        dry_run=args.dry_run,
    )

    print(f"Pipeline active stages: {stages_to_run}", file=sys.stderr)
    if args.dry_run:
        print("Pipeline is running in DRY-RUN mode.", file=sys.stderr)
    # Execute stages sequentially
    for stage in stages_to_run:
        if stage == "scrape":
            code = run_scrape(args.dry_run)
        elif stage == "example-audio":
            code = run_example_audio(args.dry_run)
        elif stage == "build":
            code = run_build(args.dry_run)
        elif stage == "validate":
            code = run_validate(args.dry_run)
        elif stage == "deck":
            code = run_deck(args.dry_run)
        elif stage == "import":
            code = run_import(args.dry_run)
        else:
            print(f"Error: Unknown stage '{stage}'", file=sys.stderr)
            return 1

        if code != 0:
            print(f"Pipeline FAILED at stage '{stage}' with exit code {code}", file=sys.stderr)
            return code

    print("=== Pipeline COMPLETED successfully ===", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
