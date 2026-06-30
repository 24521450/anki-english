"""Find changes by GUID (not by (word, pos) which has dupes)."""
from pathlib import Path

txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt.bak_pre_cefr_only_20260618')

def parse_guid(path):
    rows = {}
    for l in Path(path).read_text(encoding='utf-8').splitlines():
        if l.startswith('#') or not l.strip(): continue
        p = l.split('\t')
        if len(p) >= 16:
            rows[p[0]] = p
    return rows

old = parse_guid(backup)
new = parse_guid(txt)

print(f'old: {len(old)} GUIDs, new: {len(new)} GUIDs')

added = set(new.keys()) - set(old.keys())
removed = set(old.keys()) - set(new.keys())
common = set(new.keys()) & set(old.keys())
print(f'added: {len(added)}, removed: {len(removed)}, common: {len(common)}')

changed = []
for guid in common:
    if old[guid] != new[guid]:
        diffs = [(i, old[guid][i], new[guid][i]) for i in range(16) if old[guid][i] != new[guid][i]]
        changed.append((guid, diffs))

print(f'Changed (by GUID): {len(changed)}')

# Group by which column
from collections import Counter
col_count = Counter()
for g, d in changed:
    for c, _, _ in d:
        col_count[c] += 1
print(f'\nBy column: {dict(col_count)}')

# Show non-col-14
print('\nNon-col-14 changes:')
non_cefr = [(g, d) for g, d in changed if any(c != 14 for c, _, _ in d)]
print(f'  count: {len(non_cefr)}')
for g, d in non_cefr[:20]:
    word = d[0][1].split('|')[0] if d else '?'
    print(f'  guid={g[:15]}... {[(c, o, n) for c, o, n in d if c != 14]}')
