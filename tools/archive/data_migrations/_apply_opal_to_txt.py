"""Apply opal tags from oxford_merged.jsonl to English Academic Vocabulary.txt.

Dry-run by default. Use --apply to write changes (with backup).
"""
from __future__ import annotations
import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.deck_builder.opal_sync import (
    compute_card_updates,
    apply_updates,
    HEADER_LINES,
)

ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
JSONL_PATH = ROOT / 'data' / 'oxford_merged.jsonl'
TXT_PATH = ROOT / 'English Academic Vocabulary.txt'


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def load_txt(path: Path) -> list[str]:
    return path.read_text(encoding='utf-8').splitlines()


def write_txt(path: Path, lines: list[str]) -> None:
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    ap.add_argument('--jsonl', type=Path, default=JSONL_PATH, help='Path to jsonl file')
    ap.add_argument('--txt', type=Path, default=TXT_PATH, help='Path to .txt file')
    args = ap.parse_args()

    jsonl = load_jsonl(args.jsonl)
    txt = load_txt(args.txt)
    updates = compute_card_updates(jsonl, txt)

    # Summary
    opal_dist = Counter(u.opal_added for u in updates)
    print('=== Phase A.1 OPAL backfill ===')
    print(f'JSONL:    {args.jsonl.relative_to(ROOT)}')
    print(f'TXT:      {args.txt.relative_to(ROOT)}')
    print(f'Updates:  {len(updates)}')
    for tag, n in opal_dist.most_common():
        print(f'  {tag}: {n}')

    if not updates:
        print('\nNo changes needed.')
        return

    # Show first 10
    print('\nSample (first 10):')
    for u in updates[:10]:
        print(f'  {u.word} ({u.pos}) [{u.source}]: +{u.opal_added}')

    if not args.apply:
        print('\nDry run. Pass --apply to write changes.')
        return

    # Backup
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = args.txt.with_suffix(f'.txt.bak_pre_opal_txt_{ts}')
    shutil.copy2(args.txt, backup)
    print(f'\nBackup: {backup.name}')

    # Apply
    new_txt = apply_updates(txt, updates)
    write_txt(args.txt, new_txt)
    print(f'Wrote: {args.txt.relative_to(ROOT)}')

    # Verify
    new_updates = compute_card_updates(jsonl, new_txt)
    print(f'Re-check: {len(new_updates)} updates remain (expected 0)')

    if new_updates:
        print('WARNING: updates still remain after apply!')
        return 1
    print('OK: 0 updates remain after apply.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
