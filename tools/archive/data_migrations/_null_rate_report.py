"""Phase 4: Run parser on 50 random files (25 Oxford + 25 Cambridge), report null rate per field.

This tells us which selectors actually produce data vs. are always null in production.

Usage: python -m tools._null_rate_report
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter

PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
sys.path.insert(0, PROJECT_ROOT)

from src.scraper.oxford import parse_oxford  # noqa: E402
from src.scraper.cambridge import parse_cambridge  # noqa: E402

OXFORD_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")
CAMBRIDGE_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "cambridge")
OUT = os.path.join(PROJECT_ROOT, "data", ".cache_html", "_null_rate_report.json")

# Fields to track at top-level
TOP_FIELDS = [
    "word", "source", "source_files", "pos", "register_tags",
    "oxford_lists", "oxford_badge", "opal", "awl", "audio", "see_also",
    "pos_data", "verb_forms", "idioms",
]
AUDIO_FIELDS = ["uk", "us"]
DEF_FIELDS = ["text", "sensenum_local", "cefr", "register_tags", "topics",
              "collocations", "examples", "is_phrase", "is_idiom"]


def _is_null_or_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, (list, dict, str)) and len(v) == 0:
        return True
    return False


def _walk(record: dict, source: str) -> dict:
    """Count null/empty occurrences for each field."""
    counts = {f: {"null": 0, "non_null": 0} for f in TOP_FIELDS}
    counts["audio.uk"] = {"null": 0, "non_null": 0}
    counts["audio.us"] = {"null": 0, "non_null": 0}

    # Top-level
    for f in TOP_FIELDS:
        v = record.get(f)
        if _is_null_or_empty(v):
            counts[f]["null"] += 1
        else:
            counts[f]["non_null"] += 1

    # Audio
    audio = record.get("audio") or {}
    for k in AUDIO_FIELDS:
        if _is_null_or_empty(audio.get(k)):
            counts[f"audio.{k}"]["null"] += 1
        else:
            counts[f"audio.{k}"]["non_null"] += 1

    # Per-definition (aggregate across all pos_data)
    defs_total = 0
    defs_null = {f: 0 for f in DEF_FIELDS}
    for pd in record.get("pos_data", []):
        for d in pd.get("definitions", []):
            defs_total += 1
            for f in DEF_FIELDS:
                if _is_null_or_empty(d.get(f)):
                    defs_null[f] += 1

    counts["__defs_total"] = defs_total
    for f in DEF_FIELDS:
        counts[f"def.{f}"] = {"null": defs_null[f], "non_null": defs_total - defs_null[f]}

    return counts


def main() -> int:
    random.seed(99)

    ox_files = [f for f in os.listdir(OXFORD_DIR) if f.endswith(".html")]
    cam_files = [f for f in os.listdir(CAMBRIDGE_DIR) if f.endswith(".html")]

    ox_sample = random.sample(ox_files, 25)
    cam_sample = random.sample(cam_files, 25)

    print(f"Oxford sample: {len(ox_sample)} files")
    print(f"Cambridge sample: {len(cam_sample)} files")

    # Parse and accumulate
    ox_counts = None
    cam_counts = None
    for f in ox_sample:
        with open(os.path.join(OXFORD_DIR, f), "rb") as fh:
            rec = parse_oxford(fh.read(), source_files=[f])
        if rec is None:
            print(f"  SKIP {f}: non-word page")
            continue
        c = _walk(rec, "oxford")
        if ox_counts is None:
            ox_counts = c
        else:
            for k, v in c.items():
                if isinstance(v, dict) and "null" in v:
                    ox_counts[k]["null"] += v["null"]
                    ox_counts[k]["non_null"] += v["non_null"]
                elif k == "__defs_total":
                    ox_counts[k] += v
                else:
                    ox_counts[k] = v

    for f in cam_sample:
        with open(os.path.join(CAMBRIDGE_DIR, f), "rb") as fh:
            rec = parse_cambridge(fh.read(), source_files=[f])
        c = _walk(rec, "cambridge")
        if cam_counts is None:
            cam_counts = c
        else:
            for k, v in c.items():
                if isinstance(v, dict) and "null" in v:
                    cam_counts[k]["null"] += v["null"]
                    cam_counts[k]["non_null"] += v["non_null"]
                elif k == "__defs_total":
                    cam_counts[k] += v
                else:
                    cam_counts[k] = v

    def _to_report(counts, n_records):
        rows = []
        for f, c in counts.items():
            if f == "__defs_total":
                continue
            if isinstance(c, dict) and "null" in c:
                total = c["null"] + c["non_null"]
                pct_null = (100 * c["null"] / total) if total else 0
                rows.append({"field": f, "null": c["null"], "non_null": c["non_null"], "pct_null": round(pct_null, 1)})
        return rows

    ox_report = _to_report(ox_counts, len(ox_sample))
    cam_report = _to_report(cam_counts, len(cam_sample))

    report = {
        "oxford": {"files": len(ox_sample), "total_defs": ox_counts["__defs_total"], "fields": ox_report},
        "cambridge": {"files": len(cam_sample), "total_defs": cam_counts["__defs_total"], "fields": cam_report},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    def _print_table(name, fields, total_defs):
        print(f"\n=== {name} ===")
        print(f"  Files: {len(ox_sample) if name.startswith('Oxford') else len(cam_sample)}")
        print(f"  Total definitions: {total_defs}")
        print(f"  {'Field':<30}  {'Null':>6}  {'Non-null':>10}  {'% null':>8}")
        print(f"  {'-'*30}  {'-'*6}  {'-'*10}  {'-'*8}")
        for r in fields:
            print(f"  {r['field']:<30}  {r['null']:>6}  {r['non_null']:>10}  {r['pct_null']:>7.1f}%")

    _print_table("Oxford", ox_report, ox_counts["__defs_total"])
    _print_table("Cambridge", cam_report, cam_counts["__defs_total"])

    print(f"\nSaved to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
