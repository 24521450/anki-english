"""Check if 35 removed cards exist in Cambridge data."""
import json
import os

# Old txt
old_cards = {}  # (word, pos) -> {cefr, def, tags}
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt.bak_pre_rebuild_20260618', encoding='utf-8') as f:
    for l in f:
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 15:
            old_cards[(p[3], p[4])] = {'cefr': p[14], 'def': p[6][:60], 'tags': p[15]}

# New txt
new_keys = set()
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    for l in f:
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 15:
            new_keys.add((p[3], p[4]))

removed = set(old_cards.keys()) - new_keys
print(f'Removed: {len(removed)}')

# Check Cambridge cache
cambridge_dir = r'C:\Users\admin\Downloads\ankideck\data\.cache_html\cambridge'
have_cambridge_cache = 0
for w, p in removed:
    # Cambridge cache prefix
    cfile = os.path.join(cambridge_dir, f'cambridge_{w}.html')
    if os.path.exists(cfile):
        have_cambridge_cache += 1
print(f'Have cambridge cache for: {have_cambridge_cache}')

# Look at sources
print('\nSource tags for removed cards:')
sources = {}
for k in removed:
    tags = old_cards[k]['tags']
    src = 'unknown'
    if 'Cambridge' in tags:
        src = 'cambridge'
    elif 'Oxford' in tags:
        src = 'oxford'
    sources[src] = sources.get(src, 0) + 1
print(f'  {sources}')

# Look at CEFR
print('\nCEFR distribution:')
from collections import Counter
cefrs = Counter(old_cards[k]['cefr'] for k in removed)
print(f'  {dict(cefrs)}')
