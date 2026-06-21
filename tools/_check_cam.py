import json
oxford = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/oxford_merged.jsonl', encoding='utf-8')]
cambridge = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/cambridge_full.jsonl', encoding='utf-8')]

def safe_lower(s):
    return (s or '').lower()

for w in ['accordance', 'accused', 'blink of an eye', 'byproducts']:
    in_ox = [r for r in oxford if safe_lower(r.get('word')) == w.lower()]
    in_cam = [r for r in cambridge if safe_lower(r.get('word')) == w.lower()]
    print(f'  {w!r}: oxford={len(in_ox)} cambridge={len(in_cam)}')
    if in_cam:
        r = in_cam[0]
        print(f'    cam sample: word={r.get("word")!r}, cefr={r.get("cefr")}, _skip={r.get("_skip")}')
