import re

with open(r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_pace_1_(noun).html', encoding='utf-8') as f:
    html = f.read()

# headword
m = re.search(r'<h1[^>]+class="[^"]*headword[^"]*"[^>]*>([^<]+)</h1>', html)
print('headword:', m.group(1).strip() if m else 'NOT FOUND')

# POS
m = re.search(r'<span[^>]+class="[^"]*pos[^"]*"[^>]*>([^<]+)</span>', html)
print('pos:', m.group(1).strip() if m else 'NOT FOUND')

# B2 badge (ox3ksym or ox5ksym)
b2 = 'ox3ksym_b2' in html or 'ox5ksym_b2' in html
print('B2 badge present:', b2)

# Extract def text
defs = re.findall(r'<span[^>]+class="def"[^>]*>([^<]+)</span>', html)
print('definitions found:', len(defs))
for d in defs[:5]:
    print('  ', d.strip()[:140])

# Extract sensenum
senses = re.findall(r'<li[^>]+class="[^"]*sense[^"]*"[^>]*cefr="([^"]*)"', html, re.IGNORECASE)
print('sense cefr values:', senses[:5])

# Get oxford_badge
badge = re.search(r'ox[35]ksym_([a-c][12])', html)
print('oxford_badge:', badge.group(1) if badge else 'NOT FOUND')
