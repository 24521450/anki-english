"""Run the read-only canonical/package/import release guard."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from src.config import ProjectPaths
from src.deck_builder.release_guard import (
    RELEASE_GUARD_SCOPES,
    ReleaseGuardError,
    run_release_guard,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", choices=RELEASE_GUARD_SCOPES)
    parser.add_argument("--root", type=Path, help="Repository root")
    parser.add_argument("--package", type=Path, help="APKG path")
    parser.add_argument("--provenance", type=Path, help="Provenance sidecar path")
    parser.add_argument("--receipt", type=Path, help="Verified-import receipt path")
    args = parser.parse_args(argv)

    paths = ProjectPaths(args.root)
    try:
        report = run_release_guard(
            paths,
            args.scope,
            package_path=args.package,
            provenance_path=args.provenance,
            receipt_path=args.receipt,
        )
    except ReleaseGuardError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"[OK] {report.scope} release guard: "
        f"{', '.join(report.checks)}; notes={report.note_count}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
