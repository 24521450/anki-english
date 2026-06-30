import json
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/oxford_merged.jsonl', encoding='utf-8')]
for r in oxford:
    if r.get('word','').lower() == 'pace':
        badge = r.get('oxford_badge')
        lists = r.get('oxford_lists')
        print(f'badge={badge}, lists={lists}')
        for pd in r.get('pos_data') or []:
            pos = pd.get('pos')
            for d in pd.get('definitions') or []:
                text = d.get('text') or ''
                print(f'  pos={pos} cefr={d.get("cefr")} text={text[:60]!r}')
