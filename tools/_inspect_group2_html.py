"""Inspect actual HTML structure of group 2 words."""
import lxml.html
import sys

sys.path.insert(0, r"C:\Users\admin\Downloads\ankideck")

for word in ["deprive", "derive", "devote", "rely"]:
    candidates = [
        rf"C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_{word}.html",
        rf"C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_{word}_(verb).html",
    ]
    path = None
    for c in candidates:
        import os
        if os.path.exists(c):
            path = c
            break
    if not path:
        print(f"--- {word} --- NOT FOUND")
        continue

    with open(path, "rb") as f:
        tree = lxml.html.fromstring(f.read())
    root = tree

    print(f"=== {word} (file: {path.split(chr(92))[-1]}) ===")

    # Count all ol elements
    all_ols = root.cssselect("ol")
    print(f"  Total <ol> elements: {len(all_ols)}")
    for o in all_ols:
        cls = o.get("class") or ""
        print(f"    ol.{cls[:60]}")

    # Count li.sense and li[hclass='sense']
    li_sense = root.cssselect("li.sense, li[hclass='sense']")
    print(f"  li.sense total: {len(li_sense)}")

    # For each li.sense, walk up to find its parent ol
    if li_sense:
        for i, s in enumerate(li_sense[:5], 1):
            cur = s
            chain = []
            for _ in range(8):
                if cur is None:
                    break
                cls = cur.get("class") or cur.get("hclass") or ""
                tag = cur.tag
                chain.append(f"{tag}.{cls[:30]}")
                cur = cur.getparent()
            print(f"    parent chain li.sense[{i}]:")
            for c in chain:
                print(f"      {c}")
        if len(li_sense) > 5:
            print(f"    ... and {len(li_sense) - 5} more li.sense")

    # Also check entry div and what its direct children are
    entry = root.cssselect(".entry")
    print(f"  .entry divs: {len(entry)}")
    for e in entry:
        # Direct ol children
        direct_ols = [c for c in e if c.tag == "ol"]
        print(f"    direct ol children: {len(direct_ols)}")
        for o in direct_ols:
            cls = o.get("class") or ""
            print(f"      ol.{cls[:50]}")

    # span.idm-g (idiom blocks)
    idm = root.cssselect("span.idm-g")
    print(f"  span.idm-g: {len(idm)}")
    print()
