"""Check phrasal verb coverage."""
import os
import glob
import lxml.html

CACHE = r"C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford"
all_files = glob.glob(os.path.join(CACHE, "oxford_*.html"))
phrasal = [f for f in all_files if "phrasal_verb" in f]
print(f"Total Oxford files: {len(all_files)}")
print(f"Phrasal verb files: {len(phrasal)}")
if phrasal:
    print("Sample:")
    for f in phrasal[:10]:
        print(f"  {os.path.basename(f)}")

# Check phrasal_verb_links in main entries
phrasal_redirect_count = 0
sampled = 0
for f in all_files[:200]:  # smaller sample to avoid timeout
    try:
        with open(f, "rb") as fh:
            tree = lxml.html.fromstring(fh.read())
        pv = tree.cssselect("aside.phrasal_verb_links")
        if pv:
            phrasal_redirect_count += 1
        sampled += 1
    except Exception as e:
        pass
print(f"\nSample {sampled} files: {phrasal_redirect_count} have aside.phrasal_verb_links ({100*phrasal_redirect_count/sampled:.1f}%)")
