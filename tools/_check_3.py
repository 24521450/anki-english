import json
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/oxford_merged.jsonl', encoding='utf-8')]
for w, p in [('accordance', 'noun'), ('behalf', 'noun'), ('consist', 'verb')]:
    print(f'=== {w}|{p} ===')
    for r in oxford:
        if r.get('word','').lower() == w.lower():
            print(f'  source_files={r.get("source_files")}')
            print(f'  oxford_badge={r.get("oxford_badge")}, lists={r.get("oxford_lists")}')
            for pd in r.get('pos_data') or []:
                if pd.get('pos') == p:
                    defs = pd.get('definitions') or []
                    print(f'  senses: {len(defs)}')
                    for d in defs:
                        text = d.get('text') or ''
                        print(f'    cefr={d.get("cefr")} text={text[:50]}')
