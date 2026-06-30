"""List all 18 remaining suspicious."""
import json
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

suspicious = []
for r in records:
    db = r.get('def_before', '') or ''
    gl = r.get('gloss_after')
    if gl is None:
        continue
    if db.strip() == gl.strip():
        suspicious.append(r)
    elif len(db.split()) <= 2 and gl.strip() in db:
        suspicious.append(r)

print(f'Total suspicious: {len(suspicious)}')
for r in suspicious:
    word = r['word']
    pos = r['pos']
    cefr = r['cefr']
    db = r['def_before']
    gl = r['gloss_after']
    print(f'\n  {word}|{pos}|{cefr}:')
    print(f'    def_before: {db!r}')
    print(f'    gloss_after: {gl!r}')
