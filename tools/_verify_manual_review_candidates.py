"""Verify the manual review candidate file matches the spec.

Checks:
  1. Exactly 988 rows.
  2. All rows have decision='pending'.
  3. All rows have manual_gloss_after='' and manual_rule_after='' and notes=''.
  4. No duplicate (word, pos, cefr, old_gloss) guards.
  5. Every row matches a corresponding review_candidate row in the
     P5 ledger (read-only check).

Run: `python -m tools._verify_manual_review_candidates`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

MANUAL_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5_candidates.jsonl'
P5_LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'


def main() -> int:
    failures: list[str] = []

    # Load manual file
    if not MANUAL_PATH.exists():
        print(f'FAIL: file not found: {MANUAL_PATH}')
        return 1
    manual = [
        json.loads(l) for l in MANUAL_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]
    print(f'Loaded {len(manual)} rows from {MANUAL_PATH.name}')

    # Check 1: count
    if len(manual) != 988:
        failures.append(f'count={len(manual)} (expected 988)')

    # Check 2: all decision=pending
    n_pending = sum(1 for r in manual if r.get('decision') == 'pending')
    if n_pending != len(manual):
        failures.append(f'decision=pending count={n_pending} (expected {len(manual)})')
    print(f'  decision=pending: {n_pending}/{len(manual)}')

    # Check 3: all manual fields empty
    for r in manual:
        if r.get('manual_gloss_after') != '':
            failures.append(f'  ({r["word"]}|{r["pos"]}|{r["cefr"]}) manual_gloss_after not empty')
        if r.get('manual_rule_after') != '':
            failures.append(f'  ({r["word"]}|{r["pos"]}|{r["cefr"]}) manual_rule_after not empty')
        if r.get('notes') != '':
            failures.append(f'  ({r["word"]}|{r["pos"]}|{r["cefr"]}) notes not empty')

    # Check 4: no duplicate (word, pos, cefr, old_gloss) guards
    seen: dict[tuple, int] = {}
    for r in manual:
        g = (
            (r.get('word') or '').strip().lower(),
            (r.get('pos') or '').strip().lower(),
            (r.get('cefr') or '').strip().upper(),
            (r.get('old_gloss') or '').strip(),
        )
        seen[g] = seen.get(g, 0) + 1
    dups = [g for g, n in seen.items() if n > 1]
    if dups:
        failures.append(f'{len(dups)} duplicate keys (showing 3):')
        for g in dups[:3]:
            failures.append(f'  {g}')

    # Check 5: every row matches a P5 review_candidate row
    if not P5_LEDGER_PATH.exists():
        failures.append(f'P5 ledger not found: {P5_LEDGER_PATH}')
    else:
        p5_review = [
            json.loads(l) for l in P5_LEDGER_PATH.read_text(encoding='utf-8').splitlines()
            if l.strip()
        ]
        p5_review = [r for r in p5_review if r.get('decision') == 'review_candidate']
        p5_by_guard: dict[tuple, dict] = {}
        for r in p5_review:
            g = (
                (r.get('word') or '').strip().lower(),
                (r.get('pos') or '').strip().lower(),
                (r.get('cefr') or '').strip().upper(),
                (r.get('old_gloss') or '').strip(),
            )
            p5_by_guard[g] = r
        unmatched = []
        for r in manual:
            g = (
                (r.get('word') or '').strip().lower(),
                (r.get('pos') or '').strip().lower(),
                (r.get('cefr') or '').strip().upper(),
                (r.get('old_gloss') or '').strip(),
            )
            if g not in p5_by_guard:
                unmatched.append(r)
        if unmatched:
            failures.append(f'{len(unmatched)} rows do not match P5 ledger (showing 3):')
            for r in unmatched[:3]:
                failures.append(f'  {r["word"]}|{r["pos"]}|{r["cefr"]} old={r["old_gloss"]!r}')

    # === Final verdict ===
    print()
    if failures:
        print('=' * 60)
        print('FAIL:')
        for f in failures:
            print(f)
        print('=' * 60)
        return 1
    print('=' * 60)
    print(f'PASS: {len(manual)} manual review candidates ready for filling.')
    print('  - count: 988')
    print('  - decision: all pending')
    print('  - manual_gloss_after / manual_rule_after / notes: all empty')
    print('  - no duplicate (word, pos, cefr, old_gloss) guards')
    print('  - every row matches a P5 ledger review_candidate row')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())