"""Check Oxford pace entries."""
import re
import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Try without trailing _1
for url in [
    "https://www.oxfordlearnersdictionaries.com/definition/english/pace",
    "https://www.oxfordlearnersdictionaries.com/definition/english/pace_1_1",
]:
    print(f'\n=== Trying: {url} ===')
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=30, allow_redirects=True)
        print(f'  HTTP {resp.status_code}, {len(resp.content)} bytes')
        if resp.status_code == 200:
            html = resp.content.decode('utf-8', errors='replace')
            m = re.search(r'<h1[^>]+class="[^"]*headword[^"]*"[^>]*>([^<]+)</h1>', html)
            print(f'  headword: {m.group(1).strip() if m else "NOT FOUND"}')
            m = re.search(r'<span[^>]+class="[^"]*pos[^"]*"[^>]*>([^<]+)</span>', html)
            print(f'  pos: {m.group(1).strip() if m else "NOT FOUND"}')
            b2 = 'ox3ksym_b2' in html or 'ox5ksym_b2' in html
            print(f'  B2 badge: {b2}')
            defs = re.findall(r'<span[^>]+class="def"[^>]*>([^<]+)</span>', html)
            print(f'  defs: {len(defs)}')
            for d in defs[:3]:
                print(f'    {d.strip()[:120]}')
    except Exception as e:
        print(f'  Error: {e}')
