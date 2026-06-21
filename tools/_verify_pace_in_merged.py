import json

with open(r'C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        if r.get('word', '').lower() == 'pace' or r.get('word', '') == 'PACE':
            word = r.get('word')
            skip = r.get('_skip')
            skip_reason = r.get('_skip_reason')
            badge = r.get('oxford_badge')
            ol = r.get('oxford_lists')
            print(f'word={word!r}, _skip={skip}, _skip_reason={skip_reason}')
            print(f'  oxford_badge={badge}, oxford_lists={ol}')
            for pd in r.get('pos_data') or []:
                pos = pd.get('pos')
                defs = pd.get('definitions', [])
                print(f'  pos={pos!r}, defs={len(defs)}')
                for d in defs[:5]:
                    cefr = d.get('cefr')
                    text = d.get('text', '')[:80]
                    print(f'    [{cefr}] {text}')
