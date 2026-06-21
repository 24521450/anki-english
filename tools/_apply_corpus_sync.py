"""Apply corpus tag sync (Oxford_3000/5000) from vocab_list to deck.

Source of truth: vocab_list/Oxford/{Oxford_3000,Oxford_5000}.md
Keyed on (word, POS, CEFR) — the right granularity for our cards.
"""
import argparse
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.deck_builder.corpus_tag_sync import (
    compute_tag_updates,
    apply_updates,
    _parse_vocab_list,
    HEADER_LINES,
)

ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
VOCAB_3000_PATH = ROOT / 'vocab_list' / 'Oxford' / 'Oxford_3000.md'
VOCAB_5000_PATH = ROOT / 'vocab_list' / 'Oxford' / 'Oxford_5000.md'
TXT_PATH = ROOT / 'English Academic Vocabulary.txt'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    ap.add_argument('--vocab-3000', type=Path, default=VOCAB_3000_PATH)
    ap.add_argument('--vocab-5000', type=Path, default=VOCAB_5000_PATH)
    ap.add_argument('--txt', type=Path, default=TXT_PATH)
    args = ap.parse_args()

    vocab_3000 = _parse_vocab_list(args.vocab_3000)
    vocab_5000 = _parse_vocab_list(args.vocab_5000)
    txt_lines = args.txt.read_text(encoding='utf-8').splitlines()
    updates = compute_tag_updates(txt_lines, vocab_3000, vocab_5000)

    added_dist = Counter()
    removed_dist = Counter()
    for u in updates:
        for t in u.added:
            added_dist[t] += 1
        for t in u.removed:
            removed_dist[t] += 1

    print('=== Corpus tag sync (Oxford_3000/5000) from vocab_list ===')
    print(f'Vocab 3000: {args.vocab_3000.relative_to(ROOT)} ({len(vocab_3000)} tuples)')
    print(f'Vocab 5000: {args.vocab_5000.relative_to(ROOT)} ({len(vocab_5000)} tuples)')
    print(f'TXT:        {args.txt.relative_to(ROOT)}')
    print(f'Updates:    {len(updates)}')
    print(f'  Added:   {dict(added_dist)}')
    print(f'  Removed: {dict(removed_dist)}')

    if not updates:
        print('\nNo changes needed.')
        return

    print('\nFirst 25:')
    for u in updates[:25]:
        print(f'  {u.word} ({u.pos}) [{u.source}]: +{u.added} -{u.removed}')

    if not args.apply:
        print('\nDry run. Pass --apply to write changes.')
        return

    # Backup
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = args.txt.with_suffix(f'.txt.bak_pre_corpus_v2_{ts}')
    shutil.copy2(args.txt, backup)
    print(f'\nBackup: {backup.name}')

    new_lines = apply_updates(txt_lines, updates)
    args.txt.write_text('\n'.join(new_lines) + '\n', encoding='utf-8', newline='')
    print(f'Wrote: {args.txt.relative_to(ROOT)}')

    # Re-verify
    recheck = compute_tag_updates(new_lines, vocab_3000, vocab_5000)
    print(f'Re-check: {len(recheck)} updates remain (expected 0)')
    if recheck:
        print('WARNING: updates still remain after apply!')
        return 1
    print('OK: 0 updates remain after apply.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
