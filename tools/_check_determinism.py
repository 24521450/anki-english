"""Verify oxford_merged.jsonl rebuild determinism via SHA-256.

v3.1 contract (replaces the v3.0 --oxford-only flag's pre-merge check):
    Rebuilding data/oxford_merged.jsonl MUST be byte-identical across runs,
    given the same HTML cache. Verified by SHA-256 of two consecutive builds.

This tool provides two modes:

1. compare_two_runs (default):
       Compare two pre-built oxford_merged.jsonl files. Useful when you've
       run the pipeline twice and saved the first build to a backup.

2. build_and_compare (--build):
       Run _run_full_cache.py twice with --oxford-only, then compare the
       two output oxford_merged.jsonl files. This is the full determinism
       test (~6 minutes for Oxford only).

Usage:
    python -m tools._check_determinism              # compare two pre-built files
    python -m tools._check_determinism --build     # run + compare (slow)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
MERGED_PATH = os.path.join(PROJECT_ROOT, "data", "oxford_merged.jsonl")
RUN1_BACKUP = os.path.join(PROJECT_ROOT, "data", ".cache_html", "_oxford_merged_run1.jsonl")


def sha256_of_file(path: str) -> str:
    """Compute SHA-256 of file contents (read in binary mode)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_two_runs(run1: str, run2: str) -> int:
    """Return 0 if SHA-256 match, 1 otherwise. Print report."""
    if not os.path.exists(run1):
        print(f"ERROR: run1 file not found: {run1}")
        print("Run with --build to do a fresh build-and-compare, or pass a path to a saved build.")
        return 1
    if not os.path.exists(run2):
        print(f"ERROR: run2 file not found: {run2}")
        return 1

    h1 = sha256_of_file(run1)
    h2 = sha256_of_file(run2)
    size1 = os.path.getsize(run1)
    size2 = os.path.getsize(run2)

    print(f"Run 1: {run1}")
    print(f"  size:  {size1:>10,} bytes")
    print(f"  sha256: {h1}")
    print()
    print(f"Run 2: {run2}")
    print(f"  size:  {size2:>10,} bytes")
    print(f"  sha256: {h2}")
    print()

    if h1 == h2:
        print("DETERMINISTIC: SHA-256 matches across runs.")
        return 0
    else:
        print("NON-DETERMINISTIC: SHA-256 differs. Investigate sort/order logic.")
        print("See AGENTS.md 'Oxford rebuild determinism contract' for the contract.")
        return 1


def build_and_compare() -> int:
    """Run _run_full_cache --oxford-only twice, then compare outputs."""
    # Move current oxford_merged.jsonl aside as run1 baseline
    if os.path.exists(RUN1_BACKUP):
        os.unlink(RUN1_BACKUP)
    if os.path.exists(MERGED_PATH):
        print(f"[run1] Backing up current {MERGED_PATH} -> {RUN1_BACKUP}")
        shutil.copy2(MERGED_PATH, RUN1_BACKUP)
    else:
        print(f"ERROR: no current {MERGED_PATH} to use as run1 baseline. Run the pipeline first.")
        return 1

    print("\n[run2] Running _run_full_cache --oxford-only...")
    result = subprocess.run(
        [sys.executable, "-m", "tools._run_full_cache", "--oxford-only"],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(f"ERROR: pipeline returned {result.returncode}")
        return 1

    print("\n[verify] Comparing run1 (backup) vs run2 (current)...")
    rc = compare_two_runs(RUN1_BACKUP, MERGED_PATH)
    if rc == 0:
        os.unlink(RUN1_BACKUP)
        print(f"Cleaned up {RUN1_BACKUP}")
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify oxford_merged.jsonl rebuild determinism via SHA-256.")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run _run_full_cache --oxford-only twice, then compare. SLOW (~6 min).",
    )
    parser.add_argument(
        "--run1",
        default=RUN1_BACKUP,
        help=f"Path to run1 file (default: {RUN1_BACKUP})",
    )
    parser.add_argument(
        "--run2",
        default=MERGED_PATH,
        help=f"Path to run2 file (default: {MERGED_PATH})",
    )
    args = parser.parse_args()

    if args.build:
        return build_and_compare()
    return compare_two_runs(args.run1, args.run2)


if __name__ == "__main__":
    sys.exit(main())