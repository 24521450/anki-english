"""Update tags so CEFR::<level> in tag matches col 14 (CEFR).
Also for cards with Audio:: tags, keep but don't change.
"""
import re
from pathlib import Path

txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup = txt.with_suffix('.txt.bak_pre_tag_update_20260618')

if not backup.exists():
    import shutil
    shutil.copy2(txt, backup)
    print(f'Backup: {backup.name}')

lines = txt.read_text(encoding='utf-8').splitlines()
out = []
updated = 0
samples = []
for l in lines:
    if l.startswith('#') or not l.strip():
        out.append(l)
        continue
    p = l.split('\t')
    if len(p) < 16:
        out.append(l)
        continue
    word = p[3]
    pos = p[4]
    cefr = p[14]  # e.g. 'B1', 'C1', 'UNCLASSIFIED'
    tags = p[15]
    original_tags = tags

    # Split tag list on whitespace
    tag_list = tags.split()
    new_tag_list = []
    has_cefr_level = False
    for t in tag_list:
        # Check if tag is CEFR::<level> (level = A1/A2/B1/B2/C1/C2/UNCLASSIFIED)
        m = re.match(r'^CEFR::([A-C][12]|UNCLASSIFIED|oxford)$', t)
        if m and m.group(1) in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'UNCLASSIFIED'):
            has_cefr_level = True
            # This tag should match the new CEFR
            if m.group(1) != cefr:
                # Replace with new CEFR
                if cefr in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'):
                    new_tag_list.append(f'CEFR::{cefr}')
                # If cefr is UNCLASSIFIED, drop the level tag
                continue
        new_tag_list.append(t)

    # If no CEFR::level tag existed, add it
    if not has_cefr_level and cefr in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'):
        new_tag_list.append(f'CEFR::{cefr}')

    new_tags = ' '.join(new_tag_list)
    if new_tags != original_tags:
        p[15] = new_tags
        updated += 1
        if len(samples) < 10:
            samples.append((word, pos, original_tags.strip(), new_tags.strip()))

    out.append('\t'.join(p))

txt.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'Updated tags: {updated}')
print('First 10:')
for w, pos, o, n in samples:
    print(f'  {w}|{pos}:')
    print(f'    OLD: {o!r}')
    print(f'    NEW: {n!r}')
