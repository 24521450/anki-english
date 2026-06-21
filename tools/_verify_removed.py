"""Verify 49 removed cards: were they all _skip=True in oxford_merged?"""
import json

# Load oxford_merged
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data/oxford_merged.jsonl', encoding='utf-8')]
print(f'oxford_merged: {len(oxford)} records, _skip count: {sum(1 for r in oxford if r.get("_skip"))}')

# Load old txt
old_keys = set()
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt.bak_pre_rebuild_20260618', encoding='utf-8') as f:
    for l in f:
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 15:
            old_keys.add((p[3], p[4]))

# Load new txt
new_keys = set()
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    for l in f:
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 15:
            new_keys.add((p[3], p[4]))

removed = old_keys - new_keys
print(f'\nRemoved: {len(removed)} cards')

# Check each removed: does it exist in oxford_merged with _skip=True?
oxford_index = {}
for r in oxford:
    word = r.get('word', '')
    for pd in r.get('pos_data') or []:
        oxford_index[(word, pd.get('pos'))] = r

removed_with_skip = 0
removed_no_match = 0
removed_with_senses = 0
for key in removed:
    r = oxford_index.get(key)
    if r is None:
        removed_no_match += 1
        continue
    if r.get('_skip'):
        removed_with_skip += 1
    else:
        # Has senses but wasn't in vocab_list?
        for pd in r.get('pos_data') or []:
            if pd.get('pos') == key[1]:
                if pd.get('definitions'):
                    removed_with_senses += 1
                    break

print(f'  _skip=True in oxford: {removed_with_skip}')
print(f'  no match in oxford: {removed_no_match}')
print(f'  in oxford with senses (not _skip): {removed_with_senses}')

# Show a few removed
print('\nFirst 5 removed:')
for k in sorted(removed)[:5]:
    r = oxford_index.get(k)
    if r:
        is_skip = r.get('_skip')
        badge = r.get('oxford_badge')
        lists = r.get('oxford_lists')
        print(f'  {k}: _skip={is_skip}, badge={badge}, lists={lists}')
    else:
        print(f'  {k}: NOT IN OXFORD_MERGED')
