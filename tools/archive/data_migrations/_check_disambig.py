import json
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]
for r in records:
    if r['word'] in ['counter (argue against)', 'counter (long flat surface)', 'grave (for dead person)', 'grave (serious)', 'strip (long narrow piece)', 'strip (remove clothes/a layer)']:
        gs = r['gate_status']
        word = r['word']
        pos = r['pos']
        cefr = r['cefr']
        src = r['source']
        gl = r['gloss_after']
        print(f"{gs:20s} {word:35s} | {pos:10s} | {cefr:13s} | source={src:30s} | gloss={gl!r}")
