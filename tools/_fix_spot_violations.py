"""Fix 2 violations from spot-audit + update audit + apply."""
import json
import hashlib

# Load all_verdicts
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    data = json.load(f)
all_v = data['verdicts']

# Read txt for def lookup
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

# Find the 2 violations in verdicts and replace
fixes = [
    {
        'word': 'competitive', 'pos': 'adjective', 'cefr': 'B1',
        'old_gloss': 'rivalry-driven; ambitious',
        'new_gloss': 'competitive',
        'new_separator': 'none',
        'new_count': 1,
        'new_rule': '2sense_samedomain',  # collapsed 2 same-domain to 1 (Rule A)
        'reason': 'RULE A: rivalry-driven and ambitious are near-synonyms in this context',
    },
    {
        'word': 'trigger', 'pos': 'verb', 'cefr': 'C2',
        'old_gloss': 'traumatize',
        'new_gloss': 'cause distress',
        'new_separator': 'none',
        'new_count': 1,
        'new_rule': 'concrete_1sense',
        'reason': 'GLOSS TOO STRONG: def says upset/anxious, gloss says traumatize',
    },
]

for fix in fixes:
    key = (fix['word'], fix['pos'], fix['cefr'])
    defn = txt_defs.get(key, '')
    new_hash = hashlib.sha256(f'{key[0]}|{key[1]}|{key[2]}|{defn}'.encode()).hexdigest()[:16]
    # Find and update the verdict
    for v in all_v:
        if (v['word'], v['pos'], v['cefr']) == key:
            print(f"  FIX: {key}")
            print(f"    old: gloss={v['gloss']!r}, rule={v.get('rule_applied','')}")
            v['gloss'] = fix['new_gloss']
            v['hash'] = new_hash
            v['rule_applied'] = fix['new_rule']
            v['reasoning'] = fix['reason']
            print(f"    new: gloss={v['gloss']!r}, rule={v.get('rule_applied','')}")
            break

# Backup
import shutil
backup_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json.bak_pre_spotfix_20260618'
shutil.copy(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', backup_path)
print(f'\nBackup: {backup_path}')

# Save
out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Wrote {out_path}')
