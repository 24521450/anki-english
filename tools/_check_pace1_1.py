import requests
import re

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
url = 'https://www.oxfordlearnersdictionaries.com/definition/english/pace1_1'
resp = requests.get(url, headers={'User-Agent': UA, 'Accept': 'text/html'}, timeout=30, allow_redirects=True)
print(f'HTTP {resp.status_code}, {len(resp.content)} bytes')
html = resp.content.decode('utf-8', errors='replace')

m = re.search(r'<h1[^>]+class="[^"]*headword[^"]*"[^>]*>([^<]+)</h1>', html)
print(f'headword: {m.group(1).strip() if m else None}')

m = re.search(r'<span[^>]+class="[^"]*pos[^"]*"[^>]*>([^<]+)</span>', html)
print(f'pos: {m.group(1).strip() if m else None}')

b2 = ('ox3ksym_b2' in html) or ('ox5ksym_b2' in html)
print(f'B2 badge: {b2}')

defs = re.findall(r'<span[^>]+class="def"[^>]*>([^<]+)</span>', html)
print(f'defs: {len(defs)}')
for d in defs[:5]:
    print(f'  {d.strip()[:140]}')

m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
print(f'canonical: {m.group(1) if m else None}')
