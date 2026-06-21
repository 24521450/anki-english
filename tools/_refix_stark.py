"""Re-fix stark: use 'harsh | contrasting' to capture both C1 senses and fix example alignment."""
import json
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')

# 1. Load gloss_all_verdicts.json
verdicts_path = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_all_verdicts.json'
with open(verdicts_path, encoding='utf-8') as f:
    data = json.load(f)

# 2. Get the original definition from the TXT file to compute hash
txt_path = PROJECT_ROOT / 'English Academic Vocabulary.txt'
with open(txt_path, encoding='utf-8') as f:
    lines = f.read().split('\n')

txt_defs = {}
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) < 15:
        continue
    txt_defs[(p[3].strip(), p[4].strip(), p[14].strip() or 'UNCLASSIFIED')] = p[6] if len(p) > 6 else ''

key = ('stark', 'adjective', 'C1')
defn = txt_defs.get(key, '')
new_hash = hashlib.sha256(f'{key[0]}|{key[1]}|{key[2]}|{defn}'.encode()).hexdigest()[:16]

# 3. Find and update stark verdict
found = False
for v in data['verdicts']:
    if (v['word'], v['pos'], v['cefr']) == key:
        print(f"RE-FIX: {key}")
        print(f"  old: {v}")
        v['gloss'] = 'harsh | contrasting'
        v['hash'] = new_hash
        v['rule_applied'] = '2sense_distinct'
        v['separator'] = '|'
        v['count'] = 2
        v['category'] = 'multi-sense-3+'
        v['reasoning'] = 'Fix stark: capture both harsh and contrasting senses, and align with the 2-chunk examples'
        print(f"  new: {v}")
        found = True
        break

if not found:
    print(f"ERROR: stark verdict not found in gloss_all_verdicts.json")
else:
    # 4. Save updated gloss_all_verdicts.json
    with open(verdicts_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'Wrote {verdicts_path}')
