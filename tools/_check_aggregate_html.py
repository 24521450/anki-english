import re

for f in ['oxford_aggregate_(adj).html', 'oxford_aggregate_(verb).html',
          'oxford_aggregate_1_(noun).html', 'oxford_audition_(noun).html']:
    p = r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\\' + f
    with open(p, encoding='utf-8', errors='ignore') as fh:
        html = fh.read()
    m = re.search(r'<li[^>]+class="[^"]*sense[^"]*"[^>]*>', html)
    if m:
        first = m.group(0)
        has_cefr = 'cefr=' in first
        has_fkcefr = 'fkcefr=' in first
        cefr_val = re.search(r'cefr="([^"]*)"', first)
        fkcefr_val = re.search(r'fkcefr="([^"]*)"', first)
        print(f'{f}:')
        print(f'  has_cefr={has_cefr} val={cefr_val.group(1) if cefr_val else None!r}')
        print(f'  has_fkcefr={has_fkcefr} val={fkcefr_val.group(1) if fkcefr_val else None!r}')
