"""Apply gloss verdicts to the cache file.

Usage:
  python -m tools._apply_glosses --batch <verdicts.json>
  python -m tools._apply_glosses --backfill-categories
  python -m tools._apply_glosses --list
  python -m tools._apply_glosses --stats

Each batch is a JSON list of GlossVerdict dicts. Apply merges them into the master
verdicts file (latest verdict wins per hash). Category is auto-detected at apply
time (no M3 cost).
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))
from src.deck_builder.gloss_llm import (
    GlossVerdict, detect_category, load_jobs, load_existing_verdicts, save_verdicts, stats,
    JOBS_PATH, VERDICTS_PATH,
)


def apply_batch(verdicts: dict[str, GlossVerdict], jobs_by_hash: dict, batch: list[dict]) -> tuple[int, int]:
    """Merge a batch into verdicts. Returns (added, updated) counts. Auto-detects category."""
    added = updated = 0
    for v in batch:
        gv = GlossVerdict(**v)
        # Backfill category if missing
        if not gv.category:
            job = jobs_by_hash.get(gv.hash)
            if job:
                gv.category = detect_category(job.get('def', ''), job.get('pos', ''))
        if gv.hash in verdicts:
            updated += 1
        else:
            added += 1
        verdicts[gv.hash] = gv
    return added, updated


def backfill_categories(verdicts: dict[str, GlossVerdict], jobs_by_hash: dict) -> int:
    """Set category on all existing verdicts that lack it. Returns count filled."""
    n = 0
    for h, gv in verdicts.items():
        if gv.category:
            continue
        job = jobs_by_hash.get(h)
        if job:
            gv.category = detect_category(job.get('def', ''), job.get('pos', ''))
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', type=Path, help='Path to JSON file with a list of verdicts')
    ap.add_argument('--backfill-categories', action='store_true', help='Set category on existing verdicts (no M3 cost)')
    ap.add_argument('--flag-violations', action='store_true', help='List verdicts that may violate Rule A (synonyms) or Rule B (multi-sense 3+ awkward)')
    ap.add_argument('--prune-stale', action='store_true', help='Remove verdicts whose hash is not in current jobs.jsonl')
    ap.add_argument('--list', action='store_true', help='List jobs without verdicts')
    ap.add_argument('--stats', action='store_true', help='Show progress stats')
    args = ap.parse_args()

    verdicts = load_existing_verdicts()
    jobs = load_jobs()
    jobs_by_hash = {j['hash']: j for j in jobs}

    if args.batch:
        if not args.batch.exists():
            print(f'ERR: {args.batch} not found')
            return 1
        batch_data = json.loads(args.batch.read_text(encoding='utf-8'))
        if not isinstance(batch_data, list):
            print(f'ERR: batch file must contain a list, got {type(batch_data).__name__}')
            return 1
        added, updated = apply_batch(verdicts, jobs_by_hash, batch_data)
        save_verdicts(verdicts)
        print(f'  added: {added}, updated: {updated}')
    elif args.backfill_categories:
        n = backfill_categories(verdicts, jobs_by_hash)
        save_verdicts(verdicts)
        print(f'Backfilled category on {n} verdicts')
        # Show distribution
        cats = Counter(gv.category for gv in verdicts.values())
        print(f'  category distribution: {dict(cats)}')
    elif args.flag_violations:
        # Find candidates: category in {multi-sense-3+, multi-pos} AND gloss has ';'
        # and (heuristic) the two halves look like a Rule A or Rule B violation
        candidates = []
        for gv in verdicts.values():
            if gv.decision != 'gloss' or ';' not in gv.gloss:
                continue
            cat = gv.category or ''
            if cat not in ('multi-sense-3+', 'multi-pos'):
                continue
            parts = [p.strip() for p in gv.gloss.split(';')]
            # Rule A heuristic: both parts are 1 word and 1-2 letters apart (near-synonyms)
            # e.g. "ridiculous; nonsensical" (both -ous)
            # Rule B heuristic: gloss has 3-4 words AND def has 3+ sense chunks
            wc = len(gv.gloss.split())
            if wc <= 4 and len(parts) == 2:
                # Likely Rule A (synonyms) or Rule B (multi-sense 3+ dropped to 2)
                candidates.append((gv, 'A or B'))
        print(f'Found {len(candidates)} potential violations:')
        print(f'{"Word":<14} {"Cat":<15} {"Current gloss":<35} Def (rút gọn)')
        for gv, rule in candidates:
            job = jobs_by_hash.get(gv.hash, {})
            d = (job.get('def') or '')[:60]
            print(f'  {gv.word:<14} {gv.category:<15} {gv.gloss!r:<35} {d!r}')
    elif args.prune_stale:
        # Remove verdicts whose hash is not in current jobs.jsonl
        stale = [h for h in verdicts if h not in jobs_by_hash]
        for h in stale:
            del verdicts[h]
        save_verdicts(verdicts)
        print(f'Pruned {len(stale)} stale verdicts (hash not in current jobs)')
    elif args.list:
        done_hashes = set(verdicts.keys())
        pending = [j for j in jobs if j['hash'] not in done_hashes]
        print(f'Pending: {len(pending)} of {len(jobs)}')
        for j in pending[:20]:
            print(f'  {j["word"]!r:20} {j["pos"]:12} {j["cefr"]:13} {j["hash"]}  def={j["def"][:60]!r}')
    elif args.stats:
        stats(verdicts, len(jobs))
        cats = Counter(gv.category for gv in verdicts.values())
        print(f'  category distribution: {dict(cats)}')
    else:
        ap.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
