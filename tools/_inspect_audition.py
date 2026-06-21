import sys
sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.scraper.oxford import parse_oxford

with open(r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_audition_(noun).html', 'rb') as f:
    result = parse_oxford(f.read())

print('pos:', result['pos'])
print('pos_data count:', len(result['pos_data']))
for pd in result['pos_data']:
    pos = pd.get('pos')
    defs = pd.get('definitions', [])
    print(f'  pos={pos!r} defs={len(defs)}')
    for i, d in enumerate(defs):
        cefr = d.get('cefr')
        text = d.get('text', '')[:60]
        print(f'    [{i}] cefr={cefr!r} text={text!r}')
