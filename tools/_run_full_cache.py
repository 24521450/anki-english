"""Phase 5 + 7b: Run parser over entire HTML cache, output JSONL, merge Oxford.

Usage:
    python -m tools._run_full_cache                # Oxford + Cambridge
    python -m tools._run_full_cache --oxford-only  # Oxford only (skip Cambridge)

Reads every *.html in data/.cache_html/oxford/ and data/.cache_html/cambridge/,
parses with lxml, writes one JSON object per line to:
    data/sources/oxford.jsonl     (Phase 7b: 1 record per unique word, merged)
    data/sources/cambridge.jsonl    (unmerged, 1 record per source file — Cambridge
                                  has no multi-file words so merge would be a
                                  no-op)

v3.1: removed data/oxford_full.jsonl. The intermediate unmerged Oxford file
is no longer written — Oxford records go straight from the parser into the
merge layer (in-memory pass) and only the merged output is persisted. This
removes a ~17MB duplicate and the redundant Oxford-only determinism check
flag (use tools/_check_determinism.py instead — it SHA-256-compares two
consecutive oxford.jsonl builds).

Oxford is a 2-stage pipeline: parse → merge (groups by word, dedupes pos_data).
Cambridge stays unmerged (per source) — only Oxford has multi-file words.

Skips None returns (non-word pages) — counts as 'skipped'.
Catches all exceptions per file — counts as 'errors', logs to stderr.
"""
from __future__ import annotations

import json
import os
import sys
import time
import tempfile
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from src.config import ProjectPaths

paths = ProjectPaths(Path(PROJECT_ROOT))

from src.scraper.oxford import parse_oxford  # noqa: E402
from src.scraper.cambridge import parse_cambridge  # noqa: E402
from src.scraper.merge import merge_word_records, fold_phrasal_verb_records  # noqa: E402

OXFORD_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")
CAMBRIDGE_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "cambridge")
OXFORD_MERGED_OUT = str(paths.oxford_jsonl)
CAMBRIDGE_OUT = str(paths.cambridge_jsonl)
LOG_PATH = os.path.join(PROJECT_ROOT, "data", ".cache_html", "_run_full_cache.log")
ERROR_THRESHOLD = 0.01  # 1% — abort if exceeded


def _write_atomic(out_path: str, lines: list[str]) -> None:
    """Atomic write: write to .tmp, then os.replace. Avoids corrupt file on crash."""
    tmp_dir = os.path.dirname(out_path)
    fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, suffix=".tmp", prefix=".cache_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line)
                f.write("\n")
        os.replace(tmp_path, out_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _parse_one_oxford(args):
    path, fname = args
    with open(path, "rb") as fh:
        raw = fh.read()
    record = parse_oxford(raw, source_files=[fname])
    return fname, record, None


def _parse_one_cambridge(args):
    path, fname = args
    with open(path, "rb") as fh:
        raw = fh.read()
    record = parse_cambridge(raw, source_files=[fname])
    return fname, record, None


def run_source(
    src_dir: str,
    parse_fn,
    out_path: str,
    label: str,
) -> dict:
    """Parse all .html in src_dir, write JSONL to out_path. Returns stats dict."""
    files = sorted(f for f in os.listdir(src_dir) if f.endswith(".html"))
    total = len(files)
    print(f"\n[{label}] {total} files in {src_dir}")

    workers = max(1, (os.cpu_count() or 4) * 2)
    print(f"[{label}] Using {workers} workers")

    # Pre-load all file paths (read happens in worker)
    tasks = [(os.path.join(src_dir, f), f) for f in files]

    log_lines: list[str] = []
    log_lines.append(f"=== {label} run started: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    log_lines.append(f"Total files: {total}")

    skipped: list[str] = []
    errors: list[tuple[str, str]] = []
    records: list[dict] = []

    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(parse_fn, t): t[1] for t in tasks}
        for fut in as_completed(futures):
            fname, record, err = fut.result()
            completed += 1
            if completed % 500 == 0:
                elapsed = time.time() - t0
                rate = completed / elapsed
                print(f"  [{label}] {completed}/{total} ({rate:.0f} files/s)")
            if err is not None:
                errors.append((fname, str(err)))
                continue
            if record is None:
                skipped.append(fname)
                continue
            records.append(record)

    elapsed = time.time() - t0
    print(f"[{label}] Parsed in {elapsed:.1f}s ({len(records)/elapsed:.0f} files/s)")

    # Sort records by (word, source_files[0]) for deterministic merge ordering.
    # Sort key MUST include source_files[0] because multi-file words
    # (e.g. transport has verb + noun homonym pages) have identical word
    # values; without this, `as_completed()` race order from the parallel
    # parser leaks into the merge layer's "first non-null" picks, causing
    # oxford_badge / audio / idioms / see_also to vary across runs.
    # Filenames are ASCII (oxford_<word>_(<pos>).html), so this is
    # deterministic on every OS.
    records.sort(key=lambda r: (
        r.get("word") or "",
        (r.get("source_files") or [""])[0],
    ))

    # Write JSONL
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    _write_atomic(out_path, lines)

    # Stats
    n_records = len(records)
    n_skipped = len(skipped)
    n_errors = len(errors)
    error_rate = n_errors / total if total else 0
    stats = {
        "label": label,
        "src_dir": src_dir,
        "out_path": out_path,
        "total_files": total,
        "records": n_records,
        "skipped": n_skipped,
        "errors": n_errors,
        "error_rate": error_rate,
        "elapsed_sec": elapsed,
    }
    log_lines.append(f"Records: {n_records}")
    log_lines.append(f"Skipped: {n_skipped}")
    log_lines.append(f"Errors: {n_errors} ({100*error_rate:.2f}%)")
    log_lines.append(f"Elapsed: {elapsed:.1f}s")
    log_lines.append("")

    if errors:
        log_lines.append("--- Top 10 errors ---")
        for fname, err in errors[:10]:
            log_lines.append(f"  {fname}: {err[:200]}")
        log_lines.append("")

    if skipped:
        log_lines.append(f"--- All skipped files ({len(skipped)}) ---")
        for fname in skipped:
            log_lines.append(f"  {fname}")
        log_lines.append("")

    log_lines.append(f"=== {label} run finished: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    log_lines.append("")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"[{label}] Stats: {stats}")
    return stats


def main() -> int:
    oxford_only = "--oxford-only" in sys.argv

    if os.path.exists(LOG_PATH):
        os.unlink(LOG_PATH)
    print(f"Log: {LOG_PATH}")
    if oxford_only:
        print("[mode] Oxford only (--oxford-only)")

    # v3.1: Oxford records go parser → merge in-memory (no intermediate file).
    # We use a temp path for run_source's contract (it writes a JSONL), but
    # immediately hand the records to merge_oxford_records_from_records and
    # delete the temp file. The cleaner future state is to inline the parse
    # loop into merge; left as-is to keep the diff minimal.
    import tempfile as _tempfile
    oxford_tmp = _tempfile.NamedTemporaryFile(
        prefix="oxford_unmerged_", suffix=".jsonl", dir=os.path.dirname(OXFORD_MERGED_OUT), delete=False
    )
    oxford_tmp.close()
    OXFORD_TMP_OUT = oxford_tmp.name

    try:
        ox_stats = run_source(OXFORD_DIR, _parse_one_oxford, OXFORD_TMP_OUT, "Oxford")
        if ox_stats["error_rate"] > ERROR_THRESHOLD:
            print(f"\n*** ABORT: Oxford error rate {100*ox_stats['error_rate']:.2f}% exceeds {100*ERROR_THRESHOLD:.2f}% threshold ***")
            print("Check log for error patterns.")
            return 1

        # Phase 7b: Merge Oxford records by (word, homonym_index) in-memory
        merge_stats = merge_oxford_records_from_file(OXFORD_TMP_OUT, OXFORD_MERGED_OUT)
    finally:
        if os.path.exists(OXFORD_TMP_OUT):
            os.unlink(OXFORD_TMP_OUT)

    if oxford_only:
        print(f"\n=== FINAL (Oxford only) ===")
        print(f"Oxford (parsed):  {ox_stats['records']} records, {ox_stats['skipped']} skipped, {ox_stats['errors']} errors")
        print(f"Oxford (merged):  {merge_stats['merged']} records ({merge_stats['unique_words']} unique words, {merge_stats['skipped']} flagged _skip)")
        print(f"Output: {OXFORD_MERGED_OUT}")
        return 0

    cam_stats = run_source(CAMBRIDGE_DIR, _parse_one_cambridge, CAMBRIDGE_OUT, "Cambridge")
    if cam_stats["error_rate"] > ERROR_THRESHOLD:
        print(f"\n*** ABORT: Cambridge error rate {100*cam_stats['error_rate']:.2f}% exceeds {100*ERROR_THRESHOLD:.2f}% threshold ***")
        print("Check log for error patterns.")
        return 1

    print(f"\n=== FINAL ===")
    print(f"Oxford (parsed):     {ox_stats['records']} records, {ox_stats['skipped']} skipped, {ox_stats['errors']} errors")
    print(f"Oxford (merged, 7b): {merge_stats['merged']} records (from {ox_stats['records']} per-file, {merge_stats['unique_words']} unique words, {merge_stats['skipped']} flagged _skip)")
    print(f"Cambridge:           {cam_stats['records']} records, {cam_stats['skipped']} skipped, {cam_stats['errors']} errors")

    return 0


def merge_oxford_records_from_file(in_path: str, out_path: str) -> dict:
    """Phase 7b: Group Oxford records by word, merge per group, write to out_path.

    v3.1: `in_path` is a private temp file (deleted by caller after this
    returns). The merged output is the only file persisted to disk.
    """
    print(f"\n[Oxford merge] Reading {in_path}")
    with open(in_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    in_count = len(records)
    print(f"[Oxford merge] {in_count} per-file records, folding phrasal verbs then grouping by (word, homonym_index)...")

    # Pre-merge step: fold phrasal-verb records (e.g. "deprive of") into their
    # main-word records ("deprive"). The phrasal-verb record itself is flagged
    # _skip=true so the builder doesn't render a duplicate card.
    records = fold_phrasal_verb_records(records)
    folded_count = sum(
        1 for r in records
        if (r.get("_skip_reason") or "").startswith("folded-into-main-word")
    )
    if folded_count:
        print(f"[Oxford merge] {folded_count} phrasal-verb records folded into main words")

    # Group by (word, homonym_index) — bass1 and bass2 are SEPARATE records.
    # Phase 7b homonym fix: previously grouped by word only, which would
    # merge 'bass1' (the fish) with 'bass2' (the music note) — they are
    # distinct words with different etymologies and must stay separate.
    by_word: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        w = r.get("word")
        h = r.get("homonym_index")
        if w:
            by_word[(w, h)].append(r)
    unique_words = len(by_word)

    # Merge each group
    merged_records = []
    multi_file = 0
    skipped = 0
    for (w, h), group in by_word.items():
        if len(group) > 1:
            multi_file += 1
        merged = merge_word_records(group)
        if merged.get("_skip"):
            skipped += 1
        merged_records.append(merged)

    # Sort by (word, homonym_index) — homonym_1 comes before homonym_2
    merged_records.sort(key=lambda r: (r.get("word") or "", r.get("homonym_index") or 0))

    # Write
    lines = [json.dumps(r, ensure_ascii=False) for r in merged_records]
    _write_atomic(out_path, lines)

    stats = {
        "in_records": in_count,
        "merged": len(merged_records),
        "unique_words": unique_words,
        "multi_file_words": multi_file,
        "single_file_words": unique_words - multi_file,
        "skipped": skipped,
    }
    print(f"[Oxford merge] Wrote {len(merged_records)} merged records to {out_path}")
    print(f"[Oxford merge] Stats: {stats}")
    if skipped:
        print(f"[Oxford merge] {skipped} records flagged _skip=true (Anki builder must skip)")

    # Log
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"=== Oxford merge (Phase 7b): {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(f"Input records:    {in_count}\n")
        f.write(f"Merged records:   {len(merged_records)}\n")
        f.write(f"Unique words:     {unique_words}\n")
        f.write(f"Multi-file words: {multi_file}\n")
        f.write(f"Single-file words: {stats['single_file_words']}\n")
        f.write(f"Skipped (_skip=true): {skipped}\n")
        f.write(f"Output: {out_path}\n\n")

    return stats


# Backward-compat alias: previous name was `merge_oxford_records`. New name
# makes the in-file -> out-file contract explicit. If any external caller
# imports the old name, this keeps them working.
merge_oxford_records = merge_oxford_records_from_file


if __name__ == "__main__":
    sys.exit(main())
