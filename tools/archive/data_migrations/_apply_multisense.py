"""Apply 10 multi-sense Rule A fixes."""
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

fixes = [
    ('aesthetic', 'adjective', 'C1', 'artistic; beauty-related', 'artistic', 'rule_b_pick1'),
    ('assemble', 'verb', 'C1', 'gather; construct', 'gather', 'rule_b_pick1'),
    ('closure', 'noun', 'C1', 'permanent closure; temporary closing', 'shutdown', 'rule_b_pick1'),
    ('depict', 'verb', 'C1', 'show; describe', 'show', 'rule_b_pick1'),
    ('interval', 'noun', 'B2', 'time gap; pause', 'time gap', '2sense_samedomain'),  # 2-word gloss, no ;
    ('legitimate', 'adjective', 'C1', 'lawful; justified', 'lawful', 'rule_b_pick1'),
    ('precious', 'adjective', 'B2', 'valuable; dear', 'valuable', 'rule_b_pick1'),
    ('provoke', 'verb', 'C1', 'incite; trigger', 'incite', 'rule_b_pick1'),
    ('seeker', 'noun', 'B2', 'hunter; searcher', 'hunter', 'rule_b_pick1'),
    ('variation', 'noun', 'B2', 'change; variant', 'change', 'rule_b_pick1'),
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
                v['reasoning'] = f'RULE A fix: {old_gloss} (near-synonym pair) -> {new_gloss}'
                applied += 1
                print(f'  FIX: {key}: {old_gloss!r} -> {new_gloss!r}')
            else:
                print(f'  SKIP: {key} (current gloss != expected: {v["gloss"]!r} vs {old_gloss!r})')
            break

import shutil
backup_path = r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json.bak_pre_multisense_20260618'
shutil.copy(r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json', backup_path)
print(f'\nBackup: {backup_path}')

out_path = r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Wrote {out_path}, applied {applied} fixes')
