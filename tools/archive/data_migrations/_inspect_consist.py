"""Search consist HTML for definition."""
import re

html = open(r"C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_consist_(verb).html", encoding="utf-8").read()

print(f"HTML size: {len(html):,} chars")
print()

# Find all <... class="def" ...> blocks
defs = re.findall(r'<[^>]*class="def"[^>]*>(.*?)</[^>]+>', html, re.DOTALL)
print(f"def tags found: {len(defs)}")
for i, d in enumerate(defs[:5]):
    text = re.sub(r"<[^>]+>", " ", d).strip()
    text = re.sub(r"\s+", " ", text)
    print(f"  [{i}] {text[:200]}")
print()

# Look for any of the expected def text
for kw in ["made of various", "made up of", "specific things", "consist of", "consist in"]:
    matches = re.findall(r".{0,80}" + re.escape(kw) + r".{0,80}", html, re.IGNORECASE)
    if matches:
        print(f"Keyword [{kw}] found:")
        for m in matches[:3]:
            print("   ", re.sub(r"<[^>]+>", " ", m).strip()[:200])
    else:
        print(f"Keyword [{kw}] NOT in HTML")
