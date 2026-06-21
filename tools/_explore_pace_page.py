"""Search Oxford pace page for any links to alternate homonyms."""
import re

with open(r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_pace_1_(noun).html', encoding='utf-8') as f:
    html = f.read()

# Look for homonym navigation
print('=== Links to /pace* ===')
for m in re.finditer(r'href="(/definition/english/pace[^"]*)"', html):
    print(f'  {m.group(1)}')

# Look for navigation to other pos
print('\n=== Navigation pos (look for tabs/dropdowns) ===')
pos_tabs = re.findall(r'<a[^>]+href="(/definition/english/pace[^"]*)"[^>]*>([^<]+)</a>', html)
for url, text in pos_tabs:
    print(f'  {text.strip()}: {url}')

# Look for any mention of "speed" or "rate"
print('\n=== Mentions of speed/rate ===')
for kw in ['speed', 'rate of', 'pace_2', 'pace_3', 'noun', 'verb']:
    matches = re.findall(rf'.{{0,50}}{kw}.{{0,50}}', html, re.IGNORECASE)
    if matches:
        print(f'  {kw}: {matches[:2]}')

# Look for class="result" or similar (search results)
print('\n=== Result/title patterns ===')
title = re.search(r'<title>([^<]+)</title>', html)
print(f'  title: {title.group(1) if title else "NOT FOUND"}')
