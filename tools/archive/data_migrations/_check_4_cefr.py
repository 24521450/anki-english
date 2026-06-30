"""Check if 4 C1/B1 cards are in oxford_merged."""
import json
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/oxford_merged.jsonl', encoding='utf-8')]
cambridge = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/cambridge_full.jsonl', encoding='utf-8')]

def safe_lower(s):
    return (s or '').lower()

for w, p in [('accordance', 'noun'), ('accused', 'noun'), ('behalf', 'noun'), ('consist', 'verb')]:
    print(f'\n=== {w}|{p} ===')
    in_ox = [r for r in oxford if safe_lower(r.get('word')) == w.lower()]
    in_cam = [r for r in cambridge if safe_lower(r.get('word')) == w.lower()]
    print(f'  oxford: {len(in_ox)} records, _skip={[r.get("_skip") for r in in_ox]}')
    print(f'  cambridge: {len(in_cam)} records')

    for r in in_ox:
        for pd in r.get('pos_data') or []:
            if pd.get('pos') == p:
                print(f'  oxford pos: badge={r.get("oxford_badge")}, lists={r.get("oxford_lists")}')
                defs = pd.get('definitions', [])
                print(f'  sense count: {len(defs)}')
                for d in defs:
                    print(f'    [{d.get("cefr")}] {d.get("text","")[:60]}')

    # Check cache
    import os
    ox_cache = os.path.join(r'C:\Users\admin\Downloads\ankideck/data/.cache_html/oxford', f'oxford_{w}.html')
    if w == 'accordance':
        # multi-word
        for fn in os.listdir(os.path.dirname(ox_cache)):
            if w in fn.lower():
                print(f'  cache: {fn}')
                break
    else:
        print(f'  cache oxford: exists={os.path.exists(ox_cache)}')
