import json
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/oxford_merged.jsonl', encoding='utf-8')]
for w in ['accordance', 'behalf', 'consist']:
    print(f'=== {w} ===')
    for r in oxford:
        if r.get('word','').lower() == w.lower():
            print(f'  _skip={r.get("_skip")}')
            for pd in r.get('pos_data') or []:
                pos = pd.get('pos', '')
                defs = pd.get('definitions') or []
                print(f'  pos={pos}: {len(defs)} defs')
                for d in defs:
                    text = d.get('text') or ''
                    print(f'    cefr={d.get("cefr")} text={text[:80]!r}')
