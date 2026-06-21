import sys
sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.scraper.oxford import parse_oxford
with open(r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_kilometre_(noun).html', 'rb') as f:
    parsed = parse_oxford(f.read())
for pd in parsed.get('pos_data') or []:
    for d in pd.get('definitions') or []:
        pos = pd['pos']
        cefr = d.get('cefr')
        text = d.get('text', '')[:60]
        print(f'  pos={pos!r} cefr={cefr!r} text={text!r}')
