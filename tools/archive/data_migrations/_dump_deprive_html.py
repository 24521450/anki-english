"""Dump the actual structure of deprive.html to find where definitions live."""
import lxml.html
import re

# Show the first 4000 chars of body text
path = r"C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_deprive.html"
with open(path, "rb") as f:
    tree = lxml.html.fromstring(f.read())
root = tree

# Get headword + pos
hw = root.cssselect("h1.headword")
pos = root.cssselect("span.pos")
print(f"Headword: {hw[0].text_content() if hw else 'NONE'}")
print(f"Top-level pos: {[p.text_content() for p in pos[:5]]}")
print()

# Get entry div content as text
entry = root.cssselect(".entry")
if entry:
    text = entry[0].text_content()
    # First 2000 chars
    print("=== entry.text_content() (first 2000 chars) ===")
    print(text[:2000])
    print()

# Look for span.def, span[hclass='def'], or similar
print("=== Possible def markup ===")
for sel in ["span.def", "span[hclass='def']", ".def", "[hclass='def']", "span.definition", "[class*='def']", "[hclass*='def']"]:
    found = root.cssselect(sel)
    if found:
        print(f"  {sel}: {len(found)} matches")
        for f in found[:3]:
            print(f"    text: {f.text_content()[:100]}")

# Check if there's content in a different format
print()
print("=== Check page structure (entry's direct children + grandchildren) ===")
if entry:
    for c in entry[0]:
        cls = c.get("class") or c.get("hclass") or ""
        tag = c.tag
        print(f"  {tag} class='{cls[:40]}' children={len(c)}")
        # Grandchildren
        for gc in c[:5]:
            gc_cls = gc.get("class") or gc.get("hclass") or ""
            gc_tag = gc.tag
            print(f"    {gc_tag} class='{gc_cls[:40]}'")
