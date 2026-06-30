"""Inspect homonym HTML structure to find where the digit comes from."""
import lxml.html
import re

for word in ["bass1", "bass2", "bow1", "bow2"]:
    # Find file with this pattern
    import os
    cache = r"C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford"
    candidates = [f for f in os.listdir(cache) if f.startswith(f"oxford_{word}")]
    if not candidates:
        print(f"--- {word} --- NO FILE FOUND")
        continue
    fname = candidates[0]
    path = os.path.join(cache, fname)
    with open(path, "rb") as f:
        tree = lxml.html.fromstring(f.read())
    root = tree

    print(f"=== {fname} ===")
    # Check headword
    hw = root.cssselect("h1.headword")
    if hw:
        print(f"  h1.headword text: {hw[0].text_content()!r}")
    # Check for homnum class
    homnum = root.cssselect(".homnum, [class*='homnum'], [hclass*='homnum']")
    print(f"  .homnum matches: {len(homnum)}")
    for h in homnum[:3]:
        cls = h.get("class") or h.get("hclass") or ""
        print(f"    class='{cls}', text='{h.text_content()[:50]}'")
    # Check url patterns
    url = root.cssselect("link[rel='canonical']")
    if url:
        print(f"  canonical URL: {url[0].get('href', 'N/A')[:120]}")
    # Page source (top-g) for digits
    top_g = root.cssselect(".top-g")
    if top_g:
        for tg in top_g[:1]:
            # Get full text
            print(f"  top-g text: {tg.text_content()[:200]!r}")
    # Look for trailing digit in the page text near headword
    pos = root.cssselect("span.pos")
    if pos:
        print(f"  first pos: {pos[0].text_content()!r}")
    print()
