import json
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl', encoding='utf-8')]
for r in oxford:
    if r.get('word','').lower() == 'contagious':
        for pd in r.get('pos_data') or []:
            for d in pd.get('definitions') or []:
                cefr = d.get('cefr')
                text = d.get('text', '')[:80]
                print(f'  [{cefr}] {text}')
        print('badge:', r.get('oxford_badge'))
        print('lists:', r.get('oxford_lists'))
