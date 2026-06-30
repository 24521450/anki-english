import re

with open(r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_pace_1_(noun).html', encoding='utf-8') as f:
    html = f.read()

# Find all sense elements with cefr
senses = re.findall(r'<li[^>]+class="[^"]*sense[^"]*"[^>]*cefr="([^"]*)"[^>]*>(.*?)</li>', html, re.DOTALL | re.IGNORECASE)
print(f'Total senses with cefr: {len(senses)}')
for i, (cefr, content) in enumerate(senses):
    # Get def text
    def_m = re.search(r'<span[^>]+class="def"[^>]*>([^<]+)</span>', content)
    if def_m:
        print(f'  [{cefr}] {def_m.group(1).strip()[:120]}')

# Find badge
badge = re.search(r'ox[35]ksym_([a-c][12])', html)
print(f'\noxford_badge: {badge.group(1) if badge else None}')

# Check oxford_lists
ol_match = re.search(r'Oxford_(\d+)', html)
print(f'oxford_lists match: Oxford_{ol_match.group(1) if ol_match else "None"}')
