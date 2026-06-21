"""Find non-col-14 changes in txt."""
from pathlib import Path

txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt.bak_pre_cefr_only_20260618')

def parse(path):
    rows = {}
    for l in Path(path).read_text(encoding='utf-8').splitlines():
        if l.startswith('#') or not l.strip(): continue
        p = l.split('\t')
        if len(p) >= 16:
            rows[(p[3], p[4], p[0])] = p
    return rows

old = parse(backup)
new = parse(txt)

# Find rows that differ in non-col-14
non_cefr_changes = []
for k in old:
    if k in new and old[k] != new[k]:
        diffs = [(i, old[k][i], new[k][i]) for i in range(16) if old[k][i] != new[k][i]]
        non_cefr = [d for d in diffs if d[0] != 14]
        if non_cefr:
            non_cefr_changes.append((k, non_cefr))

print(f'Non-col-14 changes: {len(non_cefr_changes)}')
for k, diffs in non_cefr_changes[:20]:
    word, pos, guid = k
    print(f'\n  {word}|{pos}:')
    for col_idx, o, n in diffs:
        print(f'    col {col_idx}: {o!r} → {n!r}')
