"""Compare CEFR between current txt and new oxford_merged.jsonl."""
import json
from collections import Counter

# Load txt
txt_cards = {}  # (word, pos) -> cefr
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    for line in f:
        if line.startswith('#') or not line.strip():
            continue
        p = line.split('\t')
        if len(p) < 15:
            continue
        word = p[3].strip()
        pos = p[4].strip()
        cefr = p[14].strip() or 'UNCLASSIFIED'
        txt_cards[(word, pos)] = cefr

# Load oxford_merged
oxford = []
with open(r'C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl', encoding='utf-8') as f:
    for line in f:
        oxford.append(json.loads(line))

# Index oxford by (word_lower, pos) -> list of cefrs
oxford_cefrs = {}
for r in oxford:
    if r.get('_skip'):
        continue
    word = r.get('word', '').lower()
    for pd in r.get('pos_data') or []:
        pos = pd.get('pos', '')
        # Get word-level cefr
        word_cefr = r.get('oxford_badge') or 'UNCLASSIFIED'
        oxford_cefrs[(word, pos)] = word_cefr

# Compare
same = 0
different = []
in_txt_only = 0
in_oxford_only = 0
for key, txt_cefr in txt_cards.items():
    word_lower = key[0].lower()
    ox_key = (word_lower, key[1])
    if ox_key in oxford_cefrs:
        ox_cefr = oxford_cefrs[ox_key]
        if txt_cefr == ox_cefr:
            same += 1
        else:
            different.append((key, txt_cefr, ox_cefr))
    else:
        in_txt_only += 1

for key in oxford_cefrs:
    if key not in txt_cards and (key[0], key[1]) not in txt_cards:
        in_oxford_only += 1

print(f'Same: {same}')
print(f'Different: {len(different)}')
print(f'In txt only (not in oxford): {in_txt_only}')
print(f'In oxford only (not in txt): {in_oxford_only}')
print(f'\nFirst 10 different:')
for key, txt_c, ox_c in different[:10]:
    print(f'  {key}: txt={txt_c!r}, oxford={ox_c!r}')
