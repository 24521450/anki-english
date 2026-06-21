import sys
sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.scraper.oxford import _extract_pos_sections
import lxml.html as LH
with open(r'C:\Users\admin\Downloads\ankideck/data/.cache_html/oxford/oxford_accordance_(noun).html', 'rb') as f:
    html = f.read()
root = LH.fromstring(html)
sections = _extract_pos_sections(root)
print(f'sections: {len(sections)}')
for s in sections:
    pos = s.get('pos', '?')
    defs = s.get('definitions', [])
    print(f'  pos={pos!r}, defs={len(defs)}')
    for d in defs:
        text = d.get('text') or ''
        print(f'    cefr={d.get("cefr")} text={text[:80]!r}')
