"""Enumerate ALL distinct topic names from cache HTML.

For each cache file in data/.cache_html/oxford/, walk through
span.topic-g > span.topic elements inside li.sense and collect
the distinct name (after stripping the trailing CEFR suffix).

Output: a sorted list of distinct names + counts.

Optimisations vs original
─────────────────────────
• pathlib — cross-platform (original used Windows-only raw backslash paths)
• sorted(glob()) — deterministic file order, required for byte-identical runs
• lxml_html.parse(fpath) — reads straight from disk; skips the
  open().read() → Python string → fromstring() round-trip
• tp.text (direct text node) — lxml returns text BEFORE the first child tag,
  so for <span class="topic">Arts<span class="topic_cefr">B1</span></span>
  tp.text == "Arts" already; no CEFR stripping needed in the common case
• Single 'li.sense span.topic-g span.topic' cssselect per file — replaces
  the three nested cssselect loops (3 separate DOM traversals → 1)
• ProcessPoolExecutor — parallel CPU work across cores
• JSON checkpoint — save progress after every batch; resume after timeout
  without re-parsing already-done files
• Aggregation iterates in sorted(done) order — matches project sort key
  (word, source_files[0]) from tools/_run_full_cache.py:127
"""
import csv
import json
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from lxml import html as lxml_html

# ── Config ────────────────────────────────────────────────────────────────────
CACHE_DIR  = Path("data/.cache_html/oxford")
CHECKPOINT = Path("data/_topic_enum_checkpoint.json")
OUT_PATH   = Path("data/_topic_names_inventory.csv")
BATCH_SIZE = 500
WORKERS    = min(os.cpu_count() or 4, 8)

# Fallback only — used when tp.text is empty (rare edge-case)
CEFR_RE = re.compile(r"\s+[abc][12]$", re.IGNORECASE)


# ── Per-file worker (runs in a subprocess) ────────────────────────────────────
def parse_file(fpath: str) -> tuple[str, list[str], str | None]:
    """Return (fpath, [topic_names], error_msg | None).

    Real Oxford HTML structure for a topic:
        <span class="topic-g">
          <a class="Ref">
            <span class="topic">
              <span>War and conflict</span>   ← name (in unnamed inner span)
              <span class="topic_cefr">b2</span>  ← CEFR
            </span>
          </a>
        </span>
    So tp.text is None (no direct text on the outer span), and the name
    lives in the FIRST child span. The CEFR is a sibling span.topic_cefr.

    Strategy: take the first non-topic_cefr child span's text as name.
    """
    try:
        tree = lxml_html.parse(fpath)
        root = tree.getroot()
    except Exception as exc:
        return fpath, [], str(exc)

    names: list[str] = []
    for tp in root.cssselect("li.sense span.topic-g span.topic"):
        # Walk children: first span without 'topic_cefr' class is the name
        name = ""
        for child in tp:
            cls = (child.get("class") or "").split()
            if "topic_cefr" in cls:
                continue
            # First non-topic_cefr child span — get its text
            name = (child.text or "").strip()
            break
        if not name:
            # Fallback: use full text minus trailing CEFR token
            name = CEFR_RE.sub("", (tp.text_content() or "").strip()).strip()
        if name:
            names.append(name)

    return fpath, names, None


# ── Checkpoint helpers ────────────────────────────────────────────────────────
def load_checkpoint() -> dict[str, list[str]]:
    if CHECKPOINT.exists():
        with CHECKPOINT.open(encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(data: dict[str, list[str]]) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(CHECKPOINT)  # atomic write — no half-written checkpoint


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    # sorted() → deterministic iteration order across all platforms
    all_files = sorted(str(p) for p in CACHE_DIR.glob("oxford_*.html"))
    print(f"Total files found:  {len(all_files)}")

    done: dict[str, list[str]] = load_checkpoint()
    remaining = [f for f in all_files if f not in done]
    print(f"Already parsed:     {len(done)}")
    print(f"Remaining:          {len(remaining)}")

    errors: list[str] = []
    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[batch_idx : batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1
        print(f"\nBatch {batch_num}/{total_batches}  ({len(batch)} files)…", flush=True)

        with ProcessPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(parse_file, f): f for f in batch}
            for future in as_completed(futures):
                fpath, names, err = future.result()
                if err:
                    errors.append(fpath)
                    print(f"  ⚠ {Path(fpath).name}: {err}")
                else:
                    done[fpath] = names

        save_checkpoint(done)
        print(f"  ✓ checkpoint saved  ({len(done)} total done)")

    # ── Aggregate ─────────────────────────────────────────────────────────────
    # Iterate in sorted(done) — deterministic, matches (word, source_files[0])
    # sort key from tools/_run_full_cache.py:127
    name_counts: Counter = Counter()
    files_with_topics = 0
    for fpath in sorted(done):
        names = done[fpath]
        if names:
            name_counts.update(names)
            files_with_topics += 1

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"\n{'─' * 52}")
    print(f"Files processed:      {len(all_files)}")
    print(f"Files with topics:    {files_with_topics}")
    print(f"Files with errors:    {len(errors)}")
    print(f"Distinct topic names: {len(name_counts)}")
    print()
    print("All distinct topic names (sorted by count desc):")
    for name, n in name_counts.most_common():
        print(f"  {n:>5}  {name!r}")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["topic_name", "count"])
        for name, n in name_counts.most_common():
            w.writerow([name, n])
    print(f"\nWrote: {OUT_PATH}")

    if errors:
        print(f"\n{len(errors)} file(s) failed — check paths above.")


if __name__ == "__main__":
    main()
