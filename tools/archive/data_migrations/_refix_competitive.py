"""Re-fix competitive: use 'wanting to win' to avoid self-ref."""
import json
import hashlib

with open(r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8') as f:
    data = json.load(f)

with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

txt_defs = {}
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) < 15:
        continue
    txt_defs[(p[3].strip(), p[4].strip(), p[14].strip() or 'UNCLASSIFIED')] = p[6] if len(p) > 6 else ''

key = ('competitive', 'adjective', 'B1')
defn = txt_defs.get(key, '')
new_hash = hashlib.sha256(f'{key[0]}|{key[1]}|{key[2]}|{defn}'.encode()).hexdigest()[:16]

for v in data['verdicts']:
    if (v['word'], v['pos'], v['cefr']) == key:
        print(f"  RE-FIX: {key}")
        print(f"    old: gloss={v['gloss']!r}, rule={v.get('rule_applied','')}")
        v['gloss'] = 'wanting to win'
        v['hash'] = new_hash
        v['rule_applied'] = '2sense_samedomain'
        v['reasoning'] = 'RULE A fix: rivalry-driven and ambitious are near-synonyms; use 2-word gloss to avoid self-ref'
        print(f"    new: gloss={v['gloss']!r}, rule={v.get('rule_applied','')}")
        break

out_path = r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Wrote {out_path}')
