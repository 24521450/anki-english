"""Extract 46 missing cards' info (word, pos, cefr, def, ex) from txt → jobs file."""
import json
import re

# Read txt
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

# Read verdicts to find which cards are missing
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    verdicts = json.load(f)['verdicts']
verdict_keys = set((v['word'], v['pos'], v['cefr']) for v in verdicts)

# Parse txt
missing = []
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) < 15:
        continue
    card = {
        'word': p[3].strip(),
        'pos': p[4].strip(),
        'cefr': p[14].strip() or 'UNCLASSIFIED',
        'definition': p[6] if len(p) > 6 else '',
        'example': p[7] if len(p) > 7 else '',
    }
    key = (card['word'], card['pos'], card['cefr'])
    if key not in verdict_keys:
        missing.append(card)

print(f'Found {len(missing)} missing cards')

# Write to jobs file
out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_streamD.jsonl'
with open(out_path, 'w', encoding='utf-8') as f:
    for c in missing:
        f.write(json.dumps(c, ensure_ascii=False) + '\n')
print(f'Wrote {len(missing)} jobs to {out_path}')

# Print summary
for i, c in enumerate(missing):
    print(f'\n{i+1:2d}. [{c["cefr"]}] {c["word"]} ({c["pos"]})')
    print(f'    def: {c["definition"][:100]}')
    if c['example']:
        print(f'    ex:  {c["example"][:80]}')
