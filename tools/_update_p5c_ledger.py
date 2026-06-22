"""P5C Ledger Update -- reflect P5C seed fix in P5 ledger.

The P5 ledger (`data/gloss_precision_phrase_p5.jsonl`) carries the
ground-truth `new_gloss` for each repair row. When a subsequent
pass (P5C) mutates the audit/TXT/JSONL with a different gloss, the
ledger must be updated so verifiers stay in sync.

For P5C seed fix:
- additionally|adverb|B2: new_gloss `in addition` -> `also`
- gloss_word_count: 2 -> 1
- Add `loop_type` = `word_family_loop` metadata
- Add `p5c_version` = `2026-06-22` provenance

No new files written. Existing ledger is mutated in place. Backups
captured before any write.

Run:
  python -m tools._update_p5c_ledger             # dry-run (default)
  python -m tools._update_p5c_ledger --apply     # write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


# P5C seed fixes: (word, pos, cefr) -> dict of fields to update.
P5C_SEED_FIXES: dict[tuple[str, str, str], dict] = {
    ('additionally', 'adverb', 'B2'): {
        'new_gloss': 'also',
        'gloss_word_count': 1,
        'loop_type': 'word_family_loop',
        'p5c_version': '2026-06-22',
        'p5c_reason': (
            'word_family_loop: `in addition` shares the `addit-*` '
            'stem with headword; replaced with `also` (basic '
            'connector, no shared stem).'
        ),
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P5C Ledger Update (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    if not LEDGER_PATH.exists():
        print(f'FATAL: P5 ledger not found: {LEDGER_PATH}')
        return 1

    ledger = [
        json.loads(l)
        for l in LEDGER_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]
    print(f'\n  Loaded {len(ledger)} ledger rows.')

    # Apply seed fixes.
    updated_keys: list[tuple[str, str, str]] = []
    for row in ledger:
        k = (
            (row.get('word') or '').strip().lower(),
            (row.get('pos') or '').strip().lower(),
            (row.get('cefr') or '').strip().upper(),
        )
        fix = P5C_SEED_FIXES.get(k)
        if not fix:
            continue
        old = dict(row)
        for field, value in fix.items():
            row[field] = value
        updated_keys.append(k)
        print(f'\n  Updated {k[0]}|{k[1]}|{k[2]}:')
        print(f'    new_gloss:       {old.get("new_gloss")!r} -> {row["new_gloss"]!r}')
        print(f'    gloss_word_count: {old.get("gloss_word_count")} -> {row["gloss_word_count"]}')
        print(f'    loop_type:        {row["loop_type"]!r}')
        print(f'    p5c_version:      {row["p5c_version"]!r}')

    # Cross-check: every seed fix must have been applied.
    expected = set(P5C_SEED_FIXES.keys())
    got = set(updated_keys)
    missing = expected - got
    if missing:
        print(f'\nFATAL: missing ledger rows for P5C seed fixes: {missing}')
        return 1

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # Write.
    bak = LEDGER_PATH.with_suffix(LEDGER_PATH.suffix + f'.bak_pre_p5c_{_ts()}')
    bak.write_text(LEDGER_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'\n  Ledger backup: {bak.name}')

    LEDGER_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in ledger) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote ledger: {LEDGER_PATH.name} ({len(ledger)} rows)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
