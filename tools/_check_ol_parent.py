import re
with open(r'C:\Users\admin\Downloads\ankideck/data/.cache_html/oxford/oxford_accordance_(noun).html', encoding='utf-8') as f:
    html = f.read()

# Find sense_single ol and its parent
m = re.search(r'(<[^>]*class="[^"]*sense_single[^"]*"[^>]*>)', html)
if m:
    print(f'ol tag: {m.group(1)[:200]}')

# Find the parent (idm-g) context
idx = html.find('sense_single')
if idx >= 0:
    # Back up to find <span
    start = html.rfind('<span', 0, idx)
    if start < 0:
        start = html.rfind('<div', 0, idx)
    end = html.find('>', idx) + 1
    print(f'context (500 chars): {html[start:start+500]!r}')
