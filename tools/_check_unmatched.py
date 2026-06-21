import json
v = json.load(open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8'))['verdicts']
fixed = [x for x in v if x.get('reasoning', '').strip()]
print(f'total with reasoning: {len(fixed)}')
for x in fixed:
    r = x.get('reasoning', '')
    if not (r.startswith('RULE A fix:') or r.startswith('HIDDEN SELF-REF fix:') or r.startswith('GLOSS TOO STRONG')):
        word = x.get('word')
        pos = x.get('pos')
        cefr = x.get('cefr')
        rs = r[:60]
        print(f'  unmatched: {word}|{pos}|{cefr}: reasoning={rs!r}')
