"""Step 2 of Task B: Fetch Oxford page for pace_1 (the real 'pace' noun B2).

This is the IDEMPOTENT one-shot fetcher. After fetch, verify the
<link rel="canonical"> in the saved HTML points to /definition/english/pace_1
(not PACE Act stub). If canonical is wrong, the page is the wrong one
— delete cache file and try alternate URL.

Usage:
    python -m tools._fetch_pace
"""
from __future__ import annotations
import os
import re
import sys
import requests

PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")
TARGET_NAME = "oxford_pace_1_(noun).html"
URL = "https://www.oxfordlearnersdictionaries.com/definition/english/pace_1"
ALT_URL = "https://www.oxfordlearnersdictionaries.com/definition/english/pace_1_1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_one(url: str, target_path: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=30,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code} for {url}"
        with open(target_path, "wb") as f:
            f.write(resp.content)
        return True, f"fetched {len(resp.content)} bytes from {url}"
    except requests.RequestException as e:
        return False, f"RequestException: {e}"


def verify_canonical(target_path: str) -> tuple[bool, str]:
    """Read <link rel="canonical"> from saved HTML and verify it points to pace_1."""
    try:
        with open(target_path, encoding='utf-8') as f:
            html = f.read()
    except UnicodeDecodeError:
        with open(target_path, 'rb') as f:
            html = f.read().decode('utf-8', errors='replace')
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not m:
        return False, 'No <link rel="canonical"> found'
    canonical = m.group(1)
    # Normalize: extract the slug (last segment)
    slug = canonical.rstrip('/').split('/')[-1].lower()
    if 'pace_1' in slug or slug == 'pace':
        return True, f'canonical OK: {canonical} (slug={slug})'
    return False, f'canonical WRONG: {canonical} (slug={slug}) — expected pace_1/pace, got PACE Act?'


def main() -> int:
    target_path = os.path.join(CACHE_DIR, TARGET_NAME)
    os.makedirs(CACHE_DIR, exist_ok=True)

    if os.path.exists(target_path):
        print(f'Already cached: {target_path} ({os.path.getsize(target_path)} bytes)')
    else:
        # Try primary URL
        print(f'Fetching: {URL}')
        ok, msg = fetch_one(URL, target_path)
        print(f'  {msg}')
        if not ok:
            # Try alternate URL
            print(f'Retrying with alternate: {ALT_URL}')
            ok, msg = fetch_one(ALT_URL, target_path)
            print(f'  {msg}')
            if not ok:
                print('FATAL: both URLs failed')
                return 1

    # Verify canonical
    ok, msg = verify_canonical(target_path)
    print(f'\nCanonical verify:')
    print(f'  {msg}')
    if not ok:
        print('\nFATAL: canonical URL is wrong. Deleting cache file.')
        os.remove(target_path)
        return 1

    print(f'\nSUCCESS: pace_1 cache file at {target_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
