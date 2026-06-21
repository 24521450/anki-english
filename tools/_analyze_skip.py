import json
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl', encoding='utf-8')]
skip = [r for r in records if r['gate_status'] == 'skip_fallback']
src_count = {}
for r in skip:
    s = r.get('source') or 'NONE'
    src_count[s] = src_count.get(s, 0) + 1
print('skip_fallback by source:', src_count)
print()
print('skip_fallback with non-None source:')
for r in skip:
    if r.get('source'):
        word = r['word']
        pos = r['pos']
        cefr = r['cefr']
        src = r['source']
        db = r['def_before'][:60]
        print(f'  {word}|{pos}|{cefr}: source={src}, def_before={db!r}')
