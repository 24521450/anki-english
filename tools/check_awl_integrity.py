"""Check or normalize AWL POS/CEFR enrichment against dictionary sources."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.awl_integrity import AwlIntegrityPaths, audit_awl


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    project = ProjectPaths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--awl", type=Path, default=project.awl_md)
    parser.add_argument("--oxford", type=Path, default=project.oxford_jsonl)
    parser.add_argument(
        "--cambridge-fallbacks",
        type=Path,
        default=project.awl_cambridge_fallbacks,
    )
    parser.add_argument(
        "--cambridge-cache", type=Path, default=project.cambridge_cache_dir
    )
    args = parser.parse_args(argv)
    paths = AwlIntegrityPaths(
        args.awl,
        args.oxford,
        args.cambridge_fallbacks,
        args.cambridge_cache,
    )
    result = audit_awl(paths)

    print(f"Headwords: {result.headword_count}")
    print(f"Rows: {result.rows_before} -> {result.rows_after}")
    print(f"Corrections: {len(result.corrections)}")
    for correction in result.corrections:
        print(f"  line {correction.line_number}: {correction.old_line}")
        for new_line in correction.new_lines:
            print(f"    -> {new_line}")

    if result.errors:
        print(f"Errors: {len(result.errors)}", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if args.apply and result.corrections:
        args.awl.write_text(result.proposed_text, encoding="utf-8", newline="\n")
        rerun = audit_awl(paths)
        if rerun.errors or rerun.corrections:
            print("Post-apply verification failed", file=sys.stderr)
            return 1
        print("Applied and re-verified AWL corrections.")
        return 0

    if result.corrections:
        print("Run with --apply to write these corrections.", file=sys.stderr)
        return 1
    print("AWL integrity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
