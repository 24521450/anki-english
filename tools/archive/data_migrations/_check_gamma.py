import json
data = json.load(open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8'))
verdicts = data.get('verdicts', [])
# Find accordance
for v in verdicts:
    ctx = v.get('context', '') or ''
    if 'accordance' in ctx.lower():
        print(f'hash={v.get("hash")}')
        print(f'  context={ctx[:200]}')
        dec = v.get('decision')
        gloss = v.get('gloss', '')
        print(f'  decision={dec}, gloss={gloss!r}')
        print()
print(f'Total verdicts: {len(verdicts)}')
