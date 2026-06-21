"""Check audit for fkcefr-fixed words."""
import json
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

for word in ['audition', 'aggregate', 'absorbing', 'absolute', 'abstract']:
    for r in records:
        if r['word'].lower() == word:
            db = r['def_before']
            gl = r['gloss_after']
            print(f"{word}|{r['pos']}|{r['cefr']}:")
            print(f"  def_before: {db[:80]!r}")
            print(f"  gloss_after: {gl!r}")
            break
