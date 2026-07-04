#!/usr/bin/env python3
"""Production-stage orchestrator: scrape -> build -> validate -> deck.

Run with:
    python -m src.pipeline

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

ALL_STAGES = ["scrape", "build", "validate", "deck"]
DEFAULT_STAGES = ["build", "validate", "deck"]


def _canonical_stage(stage: str) -> str:
    if stage in ALL_STAGES:
        return stage
    raise ValueError(f"Unknown stage '{stage}'")

def run_scrape(dry_run: bool) -> int:
    print("=== Pipeline: Running scrape stage ===", file=sys.stderr)
    if dry_run:
        print("[dry-run] scrape: Would parse HTML cache and merge Oxford records.", file=sys.stderr)
        return 0
        
    # Import and call tools._run_full_cache
    orig_argv = sys.argv
    try:
        sys.argv = [orig_argv[0]]
        # We always rebuild both Oxford and Cambridge in the pipeline
        from tools._run_full_cache import main as run_full_cache
        return run_full_cache()
    finally:
        sys.argv = orig_argv

def run_build(dry_run: bool) -> int:
    print("=== Pipeline: Running build stage ===", file=sys.stderr)
    from tools.build_notes import main as run_build_notes
    argv = ["--dry-run"] if dry_run else []
    return run_build_notes(argv)

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

    print(
        f"  Validation OK: cards={report.card_count} "
        f"jsonl_sha256={report.jsonl_sha256} txt_sha256={report.txt_sha256}",
        file=sys.stderr,
    )
    print("  Deck distribution summary:", file=sys.stderr)
    for deck, count in report.deck_counts.items():
        print(f"    - {deck}: {count} cards", file=sys.stderr)
    return 0


def run_deck(dry_run: bool) -> int:
    print("=== Pipeline: Running deck stage ===", file=sys.stderr)
    from update_anki_deck import main as run_update_anki_deck
    argv = ["--dry-run"] if dry_run else []
    return run_update_anki_deck(argv)

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
            start_stage = _canonical_stage(from_stage or "build")
            end_stage = _canonical_stage(to_stage or "deck")
            start_idx = ALL_STAGES.index(start_stage)
            end_idx = ALL_STAGES.index(end_stage)
            if start_idx > end_idx:
                raise ValueError(f"Invalid range -- from '{start_stage}' to '{end_stage}'")
            return ALL_STAGES[start_idx : end_idx + 1]
        else:
            return DEFAULT_STAGES

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Production-stage orchestrator")
    ap.add_argument("stage", nargs="?", help="Run a single stage")
    ap.add_argument("--from", dest="from_stage", help="Start stage")
    ap.add_argument("--to", dest="to_stage", help="End stage")
    ap.add_argument("--dry-run", action="store_true", help="Run non-writing checks")
    args = ap.parse_args(argv)

    try:
        stages_to_run = resolve_stages(args.stage, args.from_stage, args.to_stage)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Pipeline active stages: {stages_to_run}", file=sys.stderr)
    if args.dry_run:
        print("Pipeline is running in DRY-RUN mode.", file=sys.stderr)
    # Execute stages sequentially
    for stage in stages_to_run:
        if stage == "scrape":
            code = run_scrape(args.dry_run)
        elif stage == "build":
            code = run_build(args.dry_run)
        elif stage == "validate":
            code = run_validate(args.dry_run)
        elif stage == "deck":
            code = run_deck(args.dry_run)
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
