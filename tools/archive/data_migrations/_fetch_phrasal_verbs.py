"""Issue A — One-shot fixer: fetch 2 missing Oxford phrasal-verb pages.

Oxford's main-word page for pattern-heavy verbs (deprive, derive, devote, rely)
is a stub that redirects to a separate phrasal-verb page (e.g. "deprive of").
We cache all such phrasal-verb pages so the Phrasal Verb Folding step in
merge.py can fold them into the main word's record.

This script is IDEMPOTENT — if the cache file already exists, it skips.

Per AGENTS.md:
- One-shot fixer pattern (like _add_def_cefr.py, _rescrape_missing.py)
- Target files in data/.cache_html/oxford/ — gitignored
- Don't crash on per-URL network errors; log and continue

Usage:
    python -m tools._fetch_phrasal_verbs
"""
from __future__ import annotations

import os
import sys
import time
import requests

PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")

# (url, target_filename) — Oxford's actual phrasal-verb pages
PHRASAL_VERB_TARGETS = [
    # deprive, derive, devote, rely — main pages are stubs.
    # 2 of 4 phrasal-verb pages already exist (deprive-of, derive-from).
    # These 2 are missing:
    (
        "https://www.oxfordlearnersdictionaries.com/definition/english/devote-to",
        "oxford_devote-to_(phrasal_verb).html",
    ),
    (
        "https://www.oxfordlearnersdictionaries.com/definition/english/rely-on_1",
        "oxford_rely-on_(phrasal_verb).html",
    ),
]

# Note on `rely-on_1`: Oxford sometimes disambiguates phrasal-verb pages with
# a trailing `_1` when the same particle has 2+ senses. We try `_1` first
# (canonical homonym index) and follow the redirect if Oxford returns one.

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_one(url: str, target_name: str) -> tuple[bool, str]:
    """Fetch URL and save to data/.cache_html/oxford/<target_name>.

    Returns (success, message). Idempotent: skips if target file already exists.
    On error, returns (False, error_msg) without raising.
    """
    target_path = os.path.join(CACHE_DIR, target_name)
    if os.path.exists(target_path):
        return True, f"already cached ({os.path.getsize(target_path)} bytes)"

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=30,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code} for {url}"

        # Save raw bytes (lxml handles encoding detection via <meta> or
        # response.apparent_encoding at parse time)
        with open(target_path, "wb") as f:
            f.write(resp.content)

        return True, f"fetched {len(resp.content)} bytes"

    except requests.RequestException as e:
        return False, f"network error: {e}"


def main() -> int:
    print(f"Target dir: {CACHE_DIR}")
    if not os.path.isdir(CACHE_DIR):
        print(f"ERROR: cache dir does not exist: {CACHE_DIR}")
        return 1

    t0 = time.time()
    fetched = 0
    skipped = 0
    failed = 0

    for url, target_name in PHRASAL_VERB_TARGETS:
        ok, msg = fetch_one(url, target_name)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {target_name}")
        print(f"         {url}")
        print(f"         {msg}")
        if ok:
            if "already cached" in msg:
                skipped += 1
            else:
                fetched += 1
        else:
            failed += 1

    print(f"\nSummary: {fetched} fetched, {skipped} skipped (cached), {failed} failed")
    print(f"Elapsed: {time.time() - t0:.1f}s")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
