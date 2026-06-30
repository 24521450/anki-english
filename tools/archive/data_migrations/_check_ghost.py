import json
v = json.load(open(r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8'))['verdicts']
for x in v:
    if x['word'] in ['grave', 'strip', 'counter']:
        print(f"{x['word']}|{x['pos']}|{x['cefr']}: gloss={x['gloss']!r}, rule={x.get('rule_applied','')}")
