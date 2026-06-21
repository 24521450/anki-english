"""Check if inflected forms' bases exist in oxford."""
import json
import re

OX = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"
AUDIT = r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl"

# Get all oxford words (lowercase)
ox_words = set()
with open(OX, encoding="utf-8") as f:
    for ln in f:
        r = json.loads(ln)
        ox_words.add(r["word"].lower())
        # also strip (verb), (noun), etc
        clean = re.sub(r"_\([a-z]+\)", "", r["word"].lower())
        ox_words.add(clean)

# Suspicious inflected forms from audit-only
inflected_audit = [
    "accordance", "accused", "behalf", "byproducts", "criteria",
    "curated", "dabbler", "designated", "destabilizing", "downtown",
    "eliminated", "evolved", "extrapolated", "foraging", "full-time",
    "gouging", "harbor", "hyperfocus", "interweave", "invading",
    "ligaments", "logistical", "part-time", "randomized", "relay",
    "resilient", "shortsighted", "shunned", "solo", "soullessly",
    "unfiltered", "untethered", "vertebrae", "wellbeing", "worship",
    "zigzagging",
]

print(f"Oxford has {len(ox_words)} unique words (incl. cleaned).")
print()
print("Audit-only words: base-form check")
print("-" * 80)


def possible_bases(w):
    """Try to derive plausible base forms."""
    cands = {w}
    # strip common suffixes
    suffixes = [
        ("ies", "y"), ("ied", "y"), ("ying", "y"),
        ("ed", ""), ("ing", ""), ("ly", ""),
        ("es", ""), ("s", ""), ("er", ""), ("est", ""),
    ]
    for suf, repl in suffixes:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            cands.add(w[: -len(suf)] + repl)
    # irregular plurals
    irregular = {"criteria": "criterion", "vertebrae": "vertebra",
                 "ligaments": "ligament"}
    if w in irregular:
        cands.add(irregular[w])
    # hyphenated
    if "-" in w:
        cands.add(w.replace("-", ""))
        cands.add(w.replace("-", " "))
    return cands


for w in sorted(inflected_audit):
    bases = possible_bases(w)
    matches = [b for b in bases if b in ox_words]
    status = "✓ base in oxford: " + ",".join(matches) if matches else "✗ NO base in oxford"
    print(f"  {w:<20} {status}")
