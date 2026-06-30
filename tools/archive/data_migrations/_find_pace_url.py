"""Try alternate pace URLs to find the actual pace noun page (not PACE Act)."""
import re
import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Try a few URLs
for url in [
    "https://www.oxfordlearnersdictionaries.com/definition/english/pace_2",
    "https://www.oxfordlearnersdictionaries.com/definition/english/pace_2_1",
    "https://www.oxfordlearnersdictionaries.com/definition/english/pace_3",
]:
    print(f'\n=== Trying: {url} ===')
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=30, allow_redirects=True)
        print(f'  HTTP {resp.status_code}, {len(resp.content)} bytes')
        if resp.status_code == 200:
            html = resp.content.decode('utf-8', errors='replace')
            # headword
            m = re.search(r'<h1[^>]+class="[^"]*headword[^"]*"[^>]*>([^<]+)</h1>', html)
            print(f'  headword: {m.group(1).strip() if m else "NOT FOUND"}')
            # POS
            m = re.search(r'<span[^>]+class="[^"]*pos[^"]*"[^>]*>([^<]+)</span>', html)
            print(f'  pos: {m.group(1).strip() if m else "NOT FOUND"}')
            # B2 badge
            b2 = 'ox3ksym_b2' in html or 'ox5ksym_b2' in html
            print(f'  B2 badge: {b2}')
            # canonical
            m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
            print(f'  canonical: {m.group(1) if m else "NOT FOUND"}')
            # defs
            defs = re.findall(r'<span[^>]+class="def"[^>]*>([^<]+)</span>', html)
            print(f'  defs: {len(defs)}')
            for d in defs[:3]:
                print(f'    {d.strip()[:120]}')
    except Exception as e:
        print(f'  Error: {e}')
