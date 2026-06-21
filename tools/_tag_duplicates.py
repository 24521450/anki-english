"""Tag duplicate cards (multi-row same word+pos) with 'delete' tag.
Keep the BEST one (proper CEFR, recent tags), tag the others.
"""
from pathlib import Path
from collections import defaultdict

txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup = txt.with_suffix('.txt.bak_pre_delete_20260618')

# Backup
if not backup.exists():
    import shutil
    shutil.copy2(txt, backup)
    print(f'Backup: {backup.name}')

lines = txt.read_text(encoding='utf-8').splitlines()
header = [l for l in lines if l.startswith('#') or not l.strip()]
data = [l for l in lines if l.strip() and not l.startswith('#')]

# Group by (word, pos)
groups = defaultdict(list)
for l in data:
    p = l.split('\t')
    if len(p) >= 16:
        groups[(p[3], p[4])].append(p)

# Find duplicates
dupes = {k: lst for k, lst in groups.items() if len(lst) > 1}
print(f'Total rows: {len(data)}')
print(f'Unique (word,pos): {len(groups)}')
print(f'Duplicate groups: {len(dupes)}')

# For each dupe group, pick the BEST one to keep
# Best = has real CEFR (not UNCLASSIFIED) + has idioms tag + oxford_badge in tags
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
for k, lst in dupes.items():
    # Sort by score DESC, keep the first, delete the rest
    scored = sorted(lst, key=score, reverse=True)
    keep = scored[0]
    for p in scored[1:]:
        to_delete.append(p)

print(f'Cards to delete: {len(to_delete)}')

# Tag them with 'delete'
deleted_guids = set()
for p in to_delete:
    guid = p[0]
    word = p[3]
    pos = p[4]
    cefr = p[14]
    tags = p[15]
    if 'delete' not in tags:
        if tags.strip():
            p[15] = tags.rstrip() + ' delete\n'
        else:
            p[15] = 'delete\n'
    deleted_guids.add(guid)
    print(f'  DELETE: {word}|{pos}|cefr={cefr}|guid={guid[:12]}...')

# Write back
out_lines = header + [p if isinstance(p, str) else '\t'.join(p) for p in data]
# Remove duplicates (header lines)
out_data = []
for p in data:
    out_data.append('\t'.join(p))

txt.write_text('\n'.join([l for l in lines if l.startswith('#') or not l.strip()]) + '\n', encoding='utf-8')
# Now write properly
final_lines = []
for l in lines:
    if l.startswith('#') or not l.strip():
        final_lines.append(l)
    else:
        p = l.split('\t')
        if len(p) >= 16:
            guid = p[0]
            if guid in deleted_guids:
                # Add delete tag
                tags = p[15]
                if 'delete' not in tags:
                    if tags.strip():
                        p[15] = tags.rstrip() + ' delete'
                    else:
                        p[15] = 'delete'
            final_lines.append('\t'.join(p))
        else:
            final_lines.append(l)

txt.write_text('\n'.join(final_lines) + '\n', encoding='utf-8')

# Verify
n_delete = sum(1 for l in txt.read_text(encoding='utf-8').splitlines() if '\tdelete' in l or l.endswith('\tdelete'))
print(f'\nCards with delete tag: {n_delete}')
