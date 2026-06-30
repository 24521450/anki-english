"""Check 12 missing cards in oxford_merged (relaxed search)."""
import json
from collections import defaultdict

PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'
oxford = []
with open(f'{PROJECT_ROOT}/data/oxford_merged.jsonl', encoding='utf-8') as f:
    for l in f:
        oxford.append(json.loads(l))

# Index by (word_lower, pos) → list of (cefr, text)
oxford_by_pos = defaultdict(list)
for r in oxford:
    if r.get('_skip'):
        continue
    word = r.get('word', '').lower()
    for pd in r.get('pos_data') or []:
        pos = pd.get('pos', '')
        for d in pd.get('definitions') or []:
            cefr = d.get('cefr')
            text = d.get('text', '')
            if text:
                oxford_by_pos[(word, pos)].append((cefr, text))

# 12 missing cards
missing = [
    ('albeit', 'conjunction', 'C1'),
    ('auto', 'noun', 'C1'),
    ('bliss', 'noun', 'UNCLASSIFIED'),
    ('furious', 'adjective', 'B2'),
    ('greatly', 'adverb', 'B2'),
    ('info', 'noun', 'B2'),
    ('newly', 'adverb', 'B2'),
    ('predominantly', 'adverb', 'C1'),
    ('primarily', 'adverb', 'B2'),
    ('spectacular', 'adjective', 'B2'),
    ('accordance', 'noun', 'C1'),
    ('accused', 'noun', 'C1'),
]

for w, p, c in missing:
    key = (w, p)
    if key in oxford_by_pos:
        print(f'{w}|{p}|{c}: FOUND')
        for cefr, text in oxford_by_pos[key][:2]:
            print(f'  [{cefr}] {text[:100]!r}')
    else:
        print(f'{w}|{p}|{c}: NOT FOUND in oxford_merged')
