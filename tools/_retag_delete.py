"""Re-add delete tag to the 82 duplicate (word,pos) cards.
Strategy: use (word, pos) to find both cards, score them, tag the lower one.
"""
import re
from pathlib import Path
from collections import defaultdict

txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup = txt.with_suffix('.txt.bak_pre_redelete_20260618')

if not backup.exists():
    import shutil
    shutil.copy2(txt, backup)
    print(f'Backup: {backup.name}')

lines = txt.read_text(encoding='utf-8').splitlines()
data = []
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) >= 16:
        data.append(p)

# Group by (word, pos)
groups = defaultdict(list)
for p in data:
    groups[(p[3], p[4])].append(p)

def score(p):
    tags = p[15]
    cefr = p[14]
    s = 0
    if cefr and cefr != 'UNCLASSIFIED':
        s += 10
    if 'Oxford_3000' in tags or 'Oxford_5000' in tags:
        s += 5
    if 'idioms' in tags:
        s += 3
    if 'Source::Oxford' in tags:
        s += 2
    if 'Audio::Cambridge' in tags:
        s += 1
    return s

to_delete = []
for k, lst in groups.items():
    if len(lst) > 1:
        scored = sorted(lst, key=score, reverse=True)
        keep = scored[0]
        for p in scored[1:]:
            to_delete.append(p)

print(f'Cards to retag with delete: {len(to_delete)}')

# Apply delete tag
delete_guids = set()
for p in to_delete:
    guid = p[0]
    delete_guids.add(guid)
    tags = p[15]
    if 'delete' not in tags:
        if tags.strip():
            p[15] = tags.rstrip() + ' delete'
        else:
            p[15] = 'delete'

# Write back
out = []
for l in lines:
    if l.startswith('#') or not l.strip():
        out.append(l)
        continue
    p = l.split('\t')
    if len(p) < 16:
        out.append(l)
        continue
    if p[0] in delete_guids:
        tags = p[15]
        if 'delete' not in tags:
            if tags.strip():
                p[15] = tags.rstrip() + ' delete'
            else:
                p[15] = 'delete'
    out.append('\t'.join(p))

txt.write_text('\n'.join(out) + '\n', encoding='utf-8')

# Verify
n = 0
for l in txt.read_text(encoding='utf-8').splitlines():
    if l.startswith('#') or not l.strip(): continue
    p = l.split('\t')
    if len(p) < 16: continue
    if 'delete' in p[15]:
        n += 1
print(f'Delete tags now: {n}')
