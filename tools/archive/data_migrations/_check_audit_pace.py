"""Check pace in audit."""
import json
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]
for r in records:
    if r['word'] == 'pace':
        word = r['word']
        pos = r['pos']
        cefr = r['cefr']
        db = r['def_before']
        gl = r['gloss_after']
        print(f'{word}|{pos}|{cefr}:')
        print(f'  def_before: {db!r}')
        print(f'  gloss_after: {gl!r}')
