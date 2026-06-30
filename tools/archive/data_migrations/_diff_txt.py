"""Diff txt vs backup to see exactly what changed."""
from pathlib import Path

txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt.bak_pre_cefr_only_20260618')

def parse_lines(path):
    rows = {}
    for l in path.read_text(encoding='utf-8').splitlines():
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 16:
            rows[(p[3], p[4])] = p
    return rows

old = parse_lines(backup)
new = parse_lines(txt)

print(f'old: {len(old)} rows, new: {len(new)} rows')

# Find rows with ANY column changed
changed = []
for k in old:
    if k in new:
        if old[k] != new[k]:
            # Find which cols differ
            diff_cols = [(i, old[k][i], new[k][i]) for i in range(16) if old[k][i] != new[k][i]]
            changed.append((k, diff_cols))

print(f'Changed: {len(changed)}')
print('\nBy column:')
from collections import Counter
col_count = Counter()
for k, diffs in changed:
    for col_idx, _, _ in diffs:
        col_count[col_idx] += 1
for col, n in col_count.most_common():
    print(f'  col {col}: {n}')

# Show first 20 with details
print('\nFirst 20 changes:')
for k, diffs in changed[:20]:
    print(f'\n  {k[0]}|{k[1]}:')
    for col_idx, o, n in diffs:
        print(f'    col {col_idx}: {o!r} → {n!r}')
