"""Fix 12 type_1 hidden self-ref leaks (pure self-ref: 'slam'->'slam shut').

Skip type_2 (legit compound: 'blade'->'propeller blade') and type_3 (idiom).
"""
import json
import hashlib

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
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

# (word, pos, cefr, old_gloss, new_gloss, new_rule)
fixes = [
    ('slam', 'verb', 'C1', 'slam shut', 'shut forcefully', 'concrete_1sense'),
    ('monthly', 'adjective', 'B2', 'per month; monthly fee', 'per month', 'concrete_1sense'),
    ('stark', 'adjective', 'C1', 'harsh; stark contrast', 'harsh', 'rule_b_pick1'),
    ('bat', 'verb', 'C1', 'hit with a bat', 'strike with stick', 'concrete_1sense'),
    ('firework', 'noun', 'B2', 'explosive firework', 'pyrotechnic device', 'concrete_1sense'),
    ('hook', 'verb', 'B2', 'fasten with hook', 'fasten with curve', 'concrete_1sense'),
    ('jet', 'noun', 'B2', 'jet plane', 'fast aircraft', 'concrete_1sense'),
    ('punk', 'noun', 'B2', 'punk rocker', 'rebellious youth', 'concrete_1sense'),
    ('radar', 'noun', 'C1', 'radar system', 'radio detector', 'concrete_1sense'),
    ('reporting', 'noun', 'B2', 'news reporting', 'news coverage', 'concrete_1sense'),
    ('tackle', 'noun', 'C1', 'football tackle', 'football block', 'concrete_1sense'),
    ('rip', 'verb', 'C1', 'tear; rip off', 'tear', 'rule_b_pick1'),
]

applied = 0
for word, pos, cefr, old_gloss, new_gloss, new_rule in fixes:
    key = (word, pos, cefr)
    defn = txt_defs.get(key, '')
    new_hash = hashlib.sha256(f'{word}|{pos}|{cefr}|{defn}'.encode()).hexdigest()[:16]
    for v in data['verdicts']:
        if (v['word'], v['pos'], v['cefr']) == key:
            if v['gloss'] == old_gloss:
                v['gloss'] = new_gloss
                v['hash'] = new_hash
                v['rule_applied'] = new_rule
                v['reasoning'] = f'HIDDEN SELF-REF fix: {old_gloss} -> {new_gloss}'
                applied += 1
                print(f'  FIX: {key}: {old_gloss!r} -> {new_gloss!r}')
            else:
                print(f'  SKIP: {key} (current gloss != expected: {v["gloss"]!r} vs {old_gloss!r})')
            break

import shutil
backup_path = r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json.bak_pre_hidden_fix_20260618'
shutil.copy(r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json', backup_path)
print(f'\nBackup: {backup_path}')

out_path = r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Wrote {out_path}, applied {applied} fixes')
