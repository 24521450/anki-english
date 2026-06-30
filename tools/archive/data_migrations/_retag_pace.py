"""Re-tag rác pace card with delete (was stripped by apply step)."""
import shutil

path = r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt'
backup = path + '.bak_pre_retag_20260618'
shutil.copy(path, backup)
print(f'Backup: {backup}')

with open(path, encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('#') or not line.strip():
        continue
    p = line.rstrip('\n').split('\t')
    if len(p) < 16:
        continue
    if p[3] == 'pace' and p[4] == 'unknown, unknown' and p[14] == 'UNCLASSIFIED':
        old_tags = p[15]
        if 'delete' not in old_tags.split():
            new_tags = old_tags + ' delete' if old_tags else 'delete'
            p[15] = new_tags
            lines[i] = '\t'.join(p) + '\n'
            print(f'  TAGGED line {i}: old={old_tags!r}, new={new_tags!r}')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
