"""
Benchmark BS4 vs lxml.html + cssselect on cached Oxford + Cambridge HTML.

Sample: 100 oxford + 100 cambridge stratified random (seed=20260610).
Output: tools/benchmark_results.csv (per-file timing + per-field equivalence).

Per locked decisions (grill-with-docs session 2026-06-10):
  - Output equivalence: per-record field compare (strict, no normalization)
  - Layer: generic traversal (representative forward + ancestor selectors)
  - Sample mix: stratified 100+100
  - Warmup: 3 un-timed runs before timing
  - Timed runs: 10, report median + p95
  - Equivalence threshold: 1 field diverge = row fail
  - RSS profiling: skipped v1 (wall time is primary metric)

Usage:
  python -m tools.benchmark_parser
"""
from __future__ import annotations

import csv
import random
import statistics
import time
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup
from lxml import html as lxml_html

ROOT = Path(__file__).resolve().parent.parent
OXFORD_DIR = ROOT / "data" / ".cache_html" / "oxford"
CAMBRIDGE_DIR = ROOT / "data" / ".cache_html" / "cambridge"
OUTPUT_CSV = ROOT / "tools" / "benchmark_results.csv"

# Forward selectors — representative of the ~95% forward-query workload.
# Per-source because Oxford uses bare class names; Cambridge uses BEM.
OXFORD_FORWARD: dict[str, str] = {
    "sense":    "sense",
    "def":      "def",
    "ipa":      "ipa",
    "pos":      "pos",
    "examples": "eg",
}
CAMBRIDGE_FORWARD: dict[str, str] = {
    "sense":    "dsense_b",
    "def":      "ddef_d",
    "ipa":      "dipa",
    "pos":      "dsense_pos",
    "examples": "dexamp",
}

# Ancestor walks — ~5% of workload, idiom detection per CONTEXT.md Idiom Detection
OXFORD_ANCESTOR: list[str] = ["idioms"]
CAMBRIDGE_ANCESTOR: list[str] = ["idiom-body", "phrase-di-body"]

WARMUP = 3
TIMED_RUNS = 10
SAMPLE_PER_SOURCE = 100
SEED = 20260610
SELECTOR_DEPTH_CAP = 50
ANCESTOR_SAMPLE_CAP = 10  # cap elements walked per selector (avoid O(n^2))


# ----- Parse + traverse -------------------------------------------------------

def parse_bs4(b: bytes) -> BeautifulSoup:
    return BeautifulSoup(b, "lxml")


def parse_lxml(b: bytes):
    return lxml_html.fromstring(b)


def walk_up_bs4(el, cap: int = SELECTOR_DEPTH_CAP) -> int:
    # BS4 el.parents includes the BeautifulSoup document object as the last
    # item; lxml's iterancestors() does not. Subtract 1 to align the count
    # to real HTML tag ancestors only (parser artifact, not a tag).
    return min(len(list(el.parents)) - 1, cap)


def walk_up_lxml(el, cap: int = SELECTOR_DEPTH_CAP) -> int:
    return min(sum(1 for _ in el.iterancestors()), cap)


def traverse_bs4(soup, forward_map, ancestor_list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label, cls in forward_map.items():
        counts[f"fwd_{label}"] = len(soup.find_all(class_=cls))
    for cls in ancestor_list:
        elems = soup.find_all(class_=cls)
        chain = sum(walk_up_bs4(e) for e in elems[:ANCESTOR_SAMPLE_CAP])
        counts[f"anc_{cls}"] = chain
    return counts


def traverse_lxml(root, forward_map, ancestor_list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label, cls in forward_map.items():
        try:
            counts[f"fwd_{label}"] = len(root.cssselect(f".{cls}"))
        except Exception:
            counts[f"fwd_{label}"] = -1
    for cls in ancestor_list:
        try:
            elems = root.cssselect(f".{cls}")
        except Exception:
            counts[f"anc_{cls}"] = -1
            continue
        chain = sum(walk_up_lxml(e) for e in elems[:ANCESTOR_SAMPLE_CAP])
        counts[f"anc_{cls}"] = chain
    return counts


# ----- Equivalence ------------------------------------------------------------

def equivalence_check(
    bs4_counts: dict[str, int], lxml_counts: dict[str, int]
) -> tuple[dict[str, bool], bool]:
    keys = sorted(set(bs4_counts) | set(lxml_counts))
    matches = {k: bs4_counts.get(k, -1) == lxml_counts.get(k, -1) for k in keys}
    return matches, all(matches.values())


# ----- Per-file benchmark -----------------------------------------------------

def benchmark_file(html_path: Path, source: str) -> dict:
    html_bytes = html_path.read_bytes()
    fwd = OXFORD_FORWARD if source == "oxford" else CAMBRIDGE_FORWARD
    anc = OXFORD_ANCESTOR if source == "oxford" else CAMBRIDGE_ANCESTOR

    bs4_timings: list[float] = []
    lxml_timings: list[float] = []
    bs4_counts: dict[str, int] = {}
    lxml_counts: dict[str, int] = {}

    for i in range(WARMUP + TIMED_RUNS):
        if i < WARMUP:
            # un-timed warmup: cold-cache eviction, lxml import, BS4 cache
            parse_bs4(html_bytes)
            parse_lxml(html_bytes)
            continue
        t0 = time.perf_counter()
        bc = traverse_bs4(parse_bs4(html_bytes), fwd, anc)
        t_bs4 = (time.perf_counter() - t0) * 1000.0
        t0 = time.perf_counter()
        lc = traverse_lxml(parse_lxml(html_bytes), fwd, anc)
        t_lxml = (time.perf_counter() - t0) * 1000.0
        bs4_timings.append(t_bs4)
        lxml_timings.append(t_lxml)
        if i == WARMUP:  # capture counts on first timed run for equivalence
            bs4_counts = bc
            lxml_counts = lc

    bs4_p50 = statistics.median(bs4_timings)
    lxml_p50 = statistics.median(lxml_timings)
    bs4_p95 = (
        statistics.quantiles(bs4_timings, n=10)[-1]
        if len(bs4_timings) >= 10
        else max(bs4_timings)
    )
    lxml_p95 = (
        statistics.quantiles(lxml_timings, n=10)[-1]
        if len(lxml_timings) >= 10
        else max(lxml_timings)
    )
    speedup = bs4_p50 / lxml_p50 if lxml_p50 > 0 else float("inf")

    field_matches, pass_all = equivalence_check(bs4_counts, lxml_counts)
    polymorphic_form = (
        polymorphic_form_oxford(html_path.name) if source == "oxford" else "single"
    )

    row: dict = {
        "file": html_path.name,
        "source": source,
        "polymorphic_form": polymorphic_form,
        "size_kb": round(len(html_bytes) / 1024.0, 1),
        "bs4_ms_p50": round(bs4_p50, 3),
        "bs4_ms_p95": round(bs4_p95, 3),
        "lxml_ms_p50": round(lxml_p50, 3),
        "lxml_ms_p95": round(lxml_p95, 3),
        "speedup": round(speedup, 2),
        "pass": pass_all,
    }
    for f, m in field_matches.items():
        row[f"match_{f}"] = m
    return row


# ----- Sampling ---------------------------------------------------------------

def polymorphic_form_oxford(name: str) -> str:
    """Return the Oxford cache polymorphic form label for a file basename."""
    base = name.removesuffix(".html")
    if "_(" in base:
        head = base.split("_(")[0]
        if head.rsplit("_", 1)[-1].isdigit():
            return "indexed_pos"
        return "pos_suffix"
    return "main_page"


def stratified_sample(d: Path, n: int) -> list[Path]:
    files = sorted(d.glob("*.html"))
    if len(files) <= n:
        return files
    rng = random.Random(SEED)
    return rng.sample(files, n)


# ----- Main -------------------------------------------------------------------

def main() -> None:
    rows: list[dict] = []
    print(
        f"Sampling {SAMPLE_PER_SOURCE} oxford + {SAMPLE_PER_SOURCE} cambridge "
        f"(seed={SEED}, warmup={WARMUP}, timed_runs={TIMED_RUNS})",
        flush=True,
    )
    oxf = stratified_sample(OXFORD_DIR, SAMPLE_PER_SOURCE)
    cam = stratified_sample(CAMBRIDGE_DIR, SAMPLE_PER_SOURCE)
    for i, p in enumerate(oxf, 1):
        print(f"[oxford {i}/{len(oxf)}] {p.name}", flush=True)
        rows.append(benchmark_file(p, "oxford"))
    for i, p in enumerate(cam, 1):
        print(f"[cambridge {i}/{len(cam)}] {p.name}", flush=True)
        rows.append(benchmark_file(p, "cambridge"))

    # Union of all row keys (Oxford/Cambridge produce different match_anc_* keys)
    fieldnames = sorted({k for r in rows for k in r.keys()})
    # Stable column order: meta + timing + pass + match_* sorted
    META = ["file", "source", "polymorphic_form", "size_kb"]
    TIMING = ["bs4_ms_p50", "bs4_ms_p95", "lxml_ms_p50", "lxml_ms_p95", "speedup", "pass"]
    match_keys = [k for k in fieldnames if k.startswith("match_")]
    fieldnames = [k for k in META + TIMING + match_keys if k in fieldnames]
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    speedups = [r["speedup"] for r in rows]
    pass_count = sum(1 for r in rows if r["pass"])
    print("\n=== Summary ===", flush=True)
    print(f"Files: {len(rows)}")
    print(
        f"Equivalence pass: {pass_count}/{len(rows)} "
        f"({100.0 * pass_count / len(rows):.1f}%)"
    )
    print(f"Speedup median: {statistics.median(speedups):.2f}x")
    print(f"Speedup mean:   {statistics.mean(speedups):.2f}x")
    print(f"Speedup min:    {min(speedups):.2f}x")
    print(f"Speedup max:    {max(speedups):.2f}x")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
