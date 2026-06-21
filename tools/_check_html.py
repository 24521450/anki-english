import re
html = open(r'C:\Users\admin\Downloads\ankideck/data/.cache_html/oxford/oxford_accordance_(noun).html', encoding='utf-8').read()
senses = re.findall(r'<li[^>]*hclass="sense"', html)
print(f'sense li count: {len(senses)}')
defs = re.findall(r'<span class="def"[^>]*>([^<]*)', html)
for d in defs[:5]:
    print(f'def: {d[:80]}')
