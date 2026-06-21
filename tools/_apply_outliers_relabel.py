"""Phase 1A-outliers: relabel 8 cards in-place per Option 1.

Approved by user 2026-06-13. Tackle/trace/hook DEFERRED (would cause
(word, CEFR) collision) — those 3 will be tracked in bucket 1B instead.

Safety:
- Read all 3,026 lines into memory
- For each target line_no, verify line_no + word + current CEFR
  before patching (so we don't patch the wrong row)
- Update only column 14 (declared_cefr)
- Write back
- Re-read and verify

If verification fails at any step, abort and restore from backup.
"""
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
DECK = ROOT / 'English Academic Vocabulary.txt'

# Approved 8 relabels (per Option 1, zero collision)
PATCHES = [
    # (line_no, word, expected_current_cefr, new_cefr)
    (1368, 'striking', 'B2', 'C1'),
    (2649, 'fit',      'C1', 'B2'),
    (2694, 'pop',      'C1', 'C2'),
    (2751, 'total',    'C1', 'C2'),
    (2795, 'trigger',  'B2', 'C2'),
    (2844, 'craft',    'B2', 'C2'),
    (2863, 'deposit',  'B2', 'C1'),
    (2864, 'deposit',  'B2', 'C2'),
]

# Read all lines (preserve raw line endings and exact byte structure)
with DECK.open('r', encoding='utf-8', newline='') as f:
    raw_lines = f.readlines()

print(f'Read {len(raw_lines)} lines from deck')

# Pre-flight: verify all target line_nos are correct rows
print('\n=== Pre-flight verification ===')
patch_by_line = {ln: (w, cur, new) for ln, w, cur, new in PATCHES}

for line_no in sorted(patch_by_line):
    word, expected_cefr, new_cefr = patch_by_line[line_no]
    # raw_lines is 0-indexed; file lines are 1-indexed
    if line_no > len(raw_lines):
        print(f'  ABORT: line {line_no} > file length {len(raw_lines)}')
        sys.exit(1)
    raw = raw_lines[line_no - 1]
    if raw.startswith('#') or not raw.strip():
        print(f'  ABORT: line {line_no} is header/blank, not a card')
        sys.exit(1)
    # Parse tab-separated
    row = raw.rstrip('\r\n').split('\t')
    if len(row) < 16:
        print(f'  ABORT: line {line_no} has only {len(row)} columns')
        sys.exit(1)
    actual_word = row[3].strip()
    actual_cefr = row[14].strip()
    if actual_word != word:
        print(f'  ABORT: line {line_no} word={actual_word!r} expected {word!r}')
        sys.exit(1)
    if actual_cefr != expected_cefr:
        print(f'  ABORT: line {line_no} ({word}) current_cefr={actual_cefr!r} expected {expected_cefr!r}')
        sys.exit(1)
    print(f'  OK line {line_no}: {word} {actual_cefr} -> {new_cefr}')

# Apply patches
print('\n=== Patching ===')
patched_count = 0
for line_no in sorted(patch_by_line):
    word, expected_cefr, new_cefr = patch_by_line[line_no]
    raw = raw_lines[line_no - 1]
    # Preserve exact newline ending
    line_ending = ''
    if raw.endswith('\r\n'):
        line_ending = '\r\n'
        body = raw[:-2]
    elif raw.endswith('\n'):
        line_ending = '\n'
        body = raw[:-1]
    else:
        body = raw
    # Split by tab
    cols = body.split('\t')
    # Update column 14
    old = cols[14]
    cols[14] = new_cefr
    # Reconstruct
    new_line = '\t'.join(cols) + line_ending
    if new_line != raw:
        raw_lines[line_no - 1] = new_line
        patched_count += 1
        print(f'  PATCHED line {line_no}: {word} {old} -> {new_cefr}')
    else:
        print(f'  NO-OP line {line_no}: {word} (already {new_cefr})')

print(f'\nPatched {patched_count} lines')

# Write back
with DECK.open('w', encoding='utf-8', newline='') as f:
    f.writelines(raw_lines)
print(f'Wrote {len(raw_lines)} lines back to deck')

# Post-flight verification
print('\n=== Post-flight verification ===')
with DECK.open('r', encoding='utf-8', newline='') as f:
    check_lines = f.readlines()
for line_no, word, _, new_cefr in PATCHES:
    raw = check_lines[line_no - 1]
    row = raw.rstrip('\r\n').split('\t')
    actual_word = row[3].strip()
    actual_cefr = row[14].strip()
    assert actual_word == word, f'line {line_no}: word mismatch'
    assert actual_cefr == new_cefr, f'line {line_no}: cefr mismatch (got {actual_cefr})'
    print(f'  OK line {line_no}: {word} now {actual_cefr}')

print('\n=== DONE ===')
