"""Tag the PACE Act card with 'delete' so it can be filtered and removed in Anki.

This is Step 1 of Task B (pace scraper fix). Tag must be applied BEFORE
the new pace|noun|B2 card is created via scrape + build, to avoid having
2 pace cards in deck simultaneously.
"""
import shutil
from datetime import datetime

path = r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt'
backup = path + '.bak_pre_pace_delete_tag_20260618'

shutil.copy(path, backup)
print(f'Backup: {backup}')

with open(path, encoding='utf-8') as f:
    lines = f.readlines()

modified = False
for i, line in enumerate(lines):
    if line.startswith('#') or not line.strip():
        continue
    p = line.rstrip('\n').split('\t')
    if len(p) < 16:
        continue
    if p[3] == 'pace' and p[4] == 'unknown, unknown' and p[14] == 'UNCLASSIFIED':
        # Found the rác card
        # Tags is field[15] (last field)
        old_tags = p[15]
        if 'delete' not in old_tags:
            new_tags = old_tags + ' delete' if old_tags else 'delete'
            p[15] = new_tags
            lines[i] = '\t'.join(p) + '\n'
            print(f'  TAGGED line {i}: {p[3]}|{p[4]}|{p[14]}')
            print(f'    old tags: {old_tags!r}')
            print(f'    new tags: {new_tags!r}')
        else:
            print(f'  ALREADY TAGGED: {p[3]}|{p[4]}')
        modified = True

if not modified:
    print('WARNING: pace line not found')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
