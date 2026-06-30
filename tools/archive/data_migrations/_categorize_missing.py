"""Check the 46 missing cards: are they words that exist in oxford_merged? vocab_list? AWL?"""
import json
from collections import Counter

# Load the missing 46
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_txt_no_verdict.json', encoding='utf-8') as f:
    missing = json.load(f)

print(f'Missing cards: {len(missing)}')

# Check each in oxford_merged.jsonl
oxford_words = set()
oxford_records = {}
with open(r'C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl', encoding='utf-8') as f:
    for l in f:
        r = json.loads(l)
        oxford_words.add(r.get('word'))
        oxford_records[r.get('word')] = r

# Vocab list files
import os
vocab_dir = r'C:\Users\admin\Downloads\ankideck\vocab_list'
vocab_words = set()
if os.path.exists(vocab_dir):
    for f in os.listdir(vocab_dir):
        if f.endswith(('.md', '.txt', '.json', '.yml', '.yaml')):
            try:
                with open(os.path.join(vocab_dir, f), encoding='utf-8') as vf:
                    content = vf.read().lower()
                # Crude word extraction
                import re
                for w in re.findall(r'\b[a-z][a-z\-\']+\b', content):
                    vocab_words.add(w)
            except Exception as e:
                pass

print(f'Oxford words: {len(oxford_words)}')
print(f'Vocab list words: {len(vocab_words)}')

# Categorize missing
in_oxford = []
not_in_oxford = []
in_vocab = []
for c in missing:
    word_lower = c['word'].lower()
    # oxford may have word without inflections — check base form
    if word_lower in oxford_words:
        in_oxford.append(c)
    else:
        not_in_oxford.append(c)
    if word_lower in vocab_words:
        in_vocab.append(c)

print(f'\nIn Oxford: {len(in_oxford)}')
print(f'NOT in Oxford: {len(not_in_oxford)}')
print(f'In vocab list: {len(in_vocab)}')

print('\nNOT in Oxford:')
for c in not_in_oxford[:30]:
    print(f'  {c["word"]}|{c["pos"]}|{c["cefr"]}')

# Check: are missing words all UNCLASSIFIED?
cefr_dist = Counter(c['cefr'] for c in missing)
print(f'\nCEFR distribution: {dict(cefr_dist)}')

# Check if they all have UNCLASSIFIED specifically
print(f'\nAre they in oxford_merged as (word, pos, UNCLASSIFIED)?')
# For each missing, check if there's a (word, pos) record in oxford
in_ox_with_unclass = 0
in_ox_no_unclass = 0
in_ox_not_found = 0
for c in missing:
    word = c['word'].lower()
    rec = oxford_records.get(word)
    if not rec:
        in_ox_not_found += 1
        continue
    # Check if (word, pos) has UNCLASSIFIED in any sense
    has_unclass = False
    for p in rec.get('pos_data') or []:
        if p.get('pos') == c['pos']:
            for s in p.get('definitions', []):
                if s.get('cefr') is None or s.get('cefr') == '':
                    has_unclass = True
                    break
    if has_unclass:
        in_ox_with_unclass += 1
    else:
        in_ox_no_unclass += 1

print(f'  In Oxford, has UNCLASSIFIED sense: {in_ox_with_unclass}')
print(f'  In Oxford, NO UNCLASSIFIED sense: {in_ox_no_unclass}')
print(f'  NOT in Oxford: {in_ox_not_found}')
