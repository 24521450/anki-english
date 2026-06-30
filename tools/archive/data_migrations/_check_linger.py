import json
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/oxford_merged.jsonl', encoding='utf-8')]
for r in oxford:
    if r.get('word','').lower() == 'linger':
        for pd in r.get('pos_data') or []:
            for d in pd.get('definitions') or []:
                t = d.get('text') or ''
                print(f'  cefr={d.get("cefr")} text={t[:80]!r}')
