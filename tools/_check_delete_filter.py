"""Check if delete tag is being filtered properly."""
import json

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Find pace records
pace_records = [r for r in records if r['word'] == 'pace']
print(f'pace records in audit: {len(pace_records)}')
for r in pace_records:
    print(f"  {r['word']}|{r['pos']}|{r['cefr']}: status={r['gate_status']}")

# Check txt for pace entries
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    content = f.read()
for l in content.split('\n'):
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) >= 16 and p[3] == 'pace':
        print(f"\nTxt line for pace:")
        print(f"  word={p[3]!r}, pos={p[4]!r}, cefr={p[14]!r}")
        print(f"  tags={p[15]!r}")
        print(f"  'delete' in tags.split(): {'delete' in p[15].split()}")
