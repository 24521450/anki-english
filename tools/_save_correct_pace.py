"""Save the correct pace page (URL: /pace1_1, NOT /pace_1)."""
import shutil
import requests
import re

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
url = 'https://www.oxfordlearnersdictionaries.com/definition/english/pace1_1'

resp = requests.get(url, headers={'User-Agent': UA, 'Accept': 'text/html'}, timeout=30, allow_redirects=True)
print(f'HTTP {resp.status_code}, {len(resp.content)} bytes')

if resp.status_code == 200:
    target = r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_pace_1_(noun).html'
    # Backup old
    backup = target + '.wrong_pace_act'
    shutil.copy(target, backup)
    print(f'Backed up old (PACE Act): {backup}')

    with open(target, 'wb') as f:
        f.write(resp.content)
    print(f'Saved correct pace noun: {target} ({len(resp.content)} bytes)')

    # Verify
    html = resp.content.decode('utf-8', errors='replace')
    pos = re.search(r'<span[^>]+class="[^"]*pos[^"]*"[^>]*>([^<]+)</span>', html)
    print(f'pos: {pos.group(1).strip() if pos else None}')
    badge = re.search(r'ox[35]ksym_([a-c][12])', html)
    print(f'oxford_badge: {badge.group(1) if badge else None}')
    defs = re.findall(r'<span[^>]+class="def"[^>]*>([^<]+)</span>', html)
    print(f'defs ({len(defs)}):')
    for d in defs[:6]:
        print(f'  {d.strip()[:120]}')
else:
    print(f'FAILED: HTTP {resp.status_code}')
