"""Manually clear gloss for behalf and meantime no-gloss verdicts."""
import json

path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json'
with open(path, encoding='utf-8') as f:
    data = json.load(f)

for v in data['verdicts']:
    if v.get('decision') == 'no-gloss' and v.get('gloss'):
        word = v.get('word')
        pos = v.get('pos')
        cefr = v.get('cefr')
        old = v.get('gloss')
        v['gloss'] = ''
        print(f'  CLEARED: {word}|{pos}|{cefr}: was={old!r}')

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print('Done')
