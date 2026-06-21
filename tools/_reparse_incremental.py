"""Incremental re-parse of Oxford HTML cache with state tracking.

The original _run_full_cache.py processes all 6,832 files in one go (~60s).
This script splits the work into small batches that can be resumed:

  - state file: data/.cache_html/_reparse_state.json
  - per-batch output: data/.cache_html/_reparse_batches/batch_NNNN.jsonl
  - run: python -m tools._reparse_incremental [batch_size]
  - run repeatedly until 'all done' message

When all files are processed, run merge step (combines all batches into
oxford_merged.jsonl via merge layer).

Each batch is deterministic (sort by filename before parse) so resume
is safe.
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
sys.path.insert(0, str(PROJECT_ROOT))

from src.scraper.oxford import parse_oxford  # noqa: E402

OXFORD_DIR = PROJECT_ROOT / "data" / ".cache_html" / "oxford"
STATE_PATH = PROJECT_ROOT / "data" / ".cache_html" / "_reparse_state.json"
BATCH_DIR = PROJECT_ROOT / "data" / ".cache_html" / "_reparse_batches"
OXFORD_MERGED_OUT = PROJECT_ROOT / "data" / "oxford_merged.jsonl"

DEFAULT_BATCH_SIZE = 200


def _parse_one(args):
    path, fname = args
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        record = parse_oxford(raw, source_files=[fname])
        return fname, record, None
    except Exception as e:
        return fname, None, str(e)[:200]


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "last_processed_idx": 0,
        "files_total": 0,
        "batches_done": 0,
        "all_done": False,
    }


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def run_one_batch(batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """Process next batch_size files. Returns stats dict."""
    state = load_state()
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    # List all files (sorted for determinism)
    all_files = sorted(f for f in os.listdir(OXFORD_DIR) if f.endswith(".html"))

    if state["files_total"] == 0:
        state["files_total"] = len(all_files)
        save_state(state)

    if state["all_done"]:
        print("All files already processed. Run --finalize to merge batches.")
        return state

    start = state["last_processed_idx"]
    end = min(start + batch_size, len(all_files))
    batch_files = all_files[start:end]
    batch_num = state["batches_done"] + 1

    print(f"\n=== Batch {batch_num}: files [{start}:{end}] of {len(all_files)} ({len(batch_files)} files) ===")

    workers = max(1, (os.cpu_count() or 4) * 2)
    print(f"Using {workers} workers")

    t0 = time.time()
    records = []
    skipped = []
    errors = []

    tasks = [(str(OXFORD_DIR / f), f) for f in batch_files]
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_parse_one, t): t[1] for t in tasks}
        for fut in as_completed(futures):
            fname, record, err = fut.result()
            completed += 1
            if err is not None:
                errors.append((fname, err))
                continue
            if record is None:
                skipped.append(fname)
                continue
            records.append(record)
            if completed % 100 == 0:
                rate = completed / (time.time() - t0)
                print(f"  {completed}/{len(batch_files)} ({rate:.0f} files/s)")

    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s ({len(records)/elapsed:.0f} files/s)")
    print(f"Records: {len(records)}, skipped: {len(skipped)}, errors: {len(errors)}")

    # Write batch file
    batch_path = BATCH_DIR / f"batch_{batch_num:04d}.jsonl"
    # Sort records by (word, source_files[0]) for determinism
    records.sort(key=lambda r: (
        r.get("word") or "",
        (r.get("source_files") or [""])[0],
    ))
    with open(batch_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote: {batch_path}")

    if errors:
        err_path = BATCH_DIR / f"errors_{batch_num:04d}.log"
        with open(err_path, "w", encoding="utf-8") as f:
            for fname, err in errors:
                f.write(f"{fname}: {err}\n")
        print(f"Errors: {err_path}")

    # Update state
    state["last_processed_idx"] = end
    state["batches_done"] = batch_num
    if end >= len(all_files):
        state["all_done"] = True
    save_state(state)

    print(f"Progress: {end}/{len(all_files)} files processed ({state['all_done'] and 'DONE' or 'more batches needed'})")
    return state


def finalize() -> int:
    """Combine all batches and run merge to produce oxford_merged.jsonl."""
    from src.scraper.merge import merge_word_records, fold_phrasal_verb_records
    from collections import defaultdict

    batch_files = sorted(BATCH_DIR.glob("batch_*.jsonl"))
    if not batch_files:
        print("No batch files found. Run --batch first.")
        return 1

    print(f"\n=== Finalize: combining {len(batch_files)} batches ===")
    all_records = []
    for bf in batch_files:
        with open(bf, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_records.append(json.loads(line))
    print(f"Total records from batches: {len(all_records)}")

    # Fold phrasal verbs
    all_records = fold_phrasal_verb_records(all_records)
    folded = sum(1 for r in all_records if (r.get("_skip_reason") or "").startswith("folded-into-main-word"))
    if folded:
        print(f"Folded {folded} phrasal-verb records")

    # Group by (word, homonym_index)
    by_word = defaultdict(list)
    for r in all_records:
        w = r.get("word")
        h = r.get("homonym_index")
        if w:
            by_word[(w, h)].append(r)
    print(f"Unique (word, homonym_index): {len(by_word)}")

    # Merge
    merged = []
    skipped = 0
    for (w, h), group in by_word.items():
        m = merge_word_records(group)
        if m.get("_skip"):
            skipped += 1
        merged.append(m)
    merged.sort(key=lambda r: (r.get("word") or "", r.get("homonym_index") or 0))

    # Write
    backup = OXFORD_MERGED_OUT.with_suffix(".jsonl.bak_pre_fkcefr_fix_20260618")
    import shutil
    if OXFORD_MERGED_OUT.exists():
        shutil.copy(OXFORD_MERGED_OUT, backup)
        print(f"Backup: {backup}")

    with open(OXFORD_MERGED_OUT, "w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote: {OXFORD_MERGED_OUT} ({len(merged)} records, {skipped} _skip)")

    # Clean up state
    state = load_state()
    state["finalized"] = True
    save_state(state)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--finalize" in args:
        return finalize()
    if "--status" in args:
        state = load_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    # Parse batch size
    batch_size = DEFAULT_BATCH_SIZE
    if "--batch" in args:
        i = args.index("--batch")
        if i + 1 < len(args):
            batch_size = int(args[i + 1])

    run_one_batch(batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
