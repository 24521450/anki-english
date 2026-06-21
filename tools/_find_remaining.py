import json
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]
for r in records:
    if r['gate_status'] == 'known_leak_unfixed':
        word = r['word']
        pos = r['pos']
        cefr = r['cefr']
        gloss = r['gloss_after']
        print(f"{word}|{pos}|{cefr}: gloss={gloss!r}")
