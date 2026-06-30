"""Update tags so CEFR::<level> in tag matches col 14 (CEFR).
For the 2,446 cards (post Anki cleanup, no duplicates).
"""
import re
from pathlib import Path

txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup = txt.with_suffix('.txt.bak_pre_tag_resync_20260618')

if not backup.exists():
    import shutil
    shutil.copy2(txt, backup)
    print(f'Backup: {backup.name}')

lines = txt.read_text(encoding='utf-8').splitlines()
out = []
updated = 0
for l in lines:
    if l.startswith('#') or not l.strip():
        out.append(l)
        continue
    p = l.split('\t')
    if len(p) < 16:
        out.append(l)
        continue
    cefr = p[14]
    tags = p[15]
    original_tags = tags

    tag_list = tags.split()
    new_tag_list = []
    has_level = False
    for t in tag_list:
        m = re.match(r'^CEFR::(A1|A2|B1|B2|C1|C2|UNCLASSIFIED)$', t)
        if m:
            has_level = True
            if m.group(1) != cefr:
                if cefr in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'):
                    new_tag_list.append(f'CEFR::{cefr}')
                # else: drop stale level tag
                continue
        new_tag_list.append(t)

    if not has_level and cefr in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'):
        new_tag_list.append(f'CEFR::{cefr}')

    new_tags = ' '.join(new_tag_list)
    if new_tags != original_tags:
        p[15] = new_tags
        updated += 1
    out.append('\t'.join(p))

txt.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'Updated tags: {updated}')

# Verify
mismatch = []
for l in txt.read_text(encoding='utf-8').splitlines():
    if l.startswith('#') or not l.strip(): continue
    p = l.split('\t')
    if len(p) < 16: continue
    cefr = p[14]
    if cefr in ('B1','B2','C1','C2','A1','A2'):
        if f'CEFR::{cefr}' not in p[15]:
            mismatch.append((p[3], p[4], cefr, p[15].strip()[:60]))
print(f'Stale tags remaining: {len(mismatch)}')
for m in mismatch[:5]:
    print(f'  {m[0]}|{m[1]}|{m[2]}: {m[3]!r}')
