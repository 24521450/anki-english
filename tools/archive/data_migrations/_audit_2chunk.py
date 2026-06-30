import json
from collections import Counter

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    merged = json.load(f)['verdicts']

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_verdicts.json', encoding='utf-8') as f:
    rerun = json.load(f)
if isinstance(rerun, dict) and 'verdicts' in rerun:
    rerun = rerun['verdicts']

rerun_hashes = {x.get('hash') for x in rerun}
kept = [x for x in merged if x.get('hash') not in rerun_hashes]

def is_self_ref(x):
    word = (x.get('word') or '').lower().strip()
    if not word:
        return False
    gloss = (x.get('gloss') or '').lower()
    chunks = [c.strip().strip('"') for c in gloss.replace('|', ';').split(';') if c.strip()]
    return any(c == word for c in chunks)

clean_kept = [x for x in kept if not is_self_ref(x)]

# Look at 2-chunk verdicts — Rule A candidates
two_chunk = [x for x in clean_kept if x.get('gloss') and ';' in x.get('gloss', '')]
print(f'2-chunk (`;`) clean kept: {len(two_chunk)}')
for x in two_chunk[:25]:
    print(f"  {x.get('word')}|{x.get('pos')}|{x.get('cefr')}: '{x.get('gloss')}'")

# Also look at `|` (distinct domain) cases
pipe_chunk = [x for x in clean_kept if x.get('gloss') and '|' in x.get('gloss', '')]
print(f'\n2-chunk (`|`) clean kept: {len(pipe_chunk)}')
for x in pipe_chunk[:25]:
    print(f"  {x.get('word')}|{x.get('pos')}|{x.get('cefr')}: '{x.get('gloss')}'")
