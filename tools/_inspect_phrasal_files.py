"""Inspect phrasal verb files (deprive-of, derive-from).

Reads the canonical builder input (oxford.jsonl) and locates the
phrasal-verb record by matching `fname in record.source_files` (merged
records preserve the full source_files list of contributing HTML files).
"""
import sys
import lxml.html
from pathlib import Path
from src.config import ProjectPaths

paths = ProjectPaths(Path(__file__).resolve().parents[1])

for fname in ["oxford_deprive-of_(phrasal_verb).html", "oxford_derive-from_(phrasal_verb).html"]:
    path = paths.root / "data" / ".cache_html" / "oxford" / fname
    try:
        with open(path, "rb") as f:
            tree = lxml.html.fromstring(f.read())
        root = tree
    except FileNotFoundError:
        print(f"{fname}: NOT FOUND")
        continue

    print(f"=== {fname} ===")
    hw = root.cssselect("h1.headword")
    pos = root.cssselect("span.pos")
    print(f"  Headword: {hw[0].text_content() if hw else 'NONE'}")
    print(f"  POS: {[p.text_content() for p in pos[:5]]}")
    print(f"  ol.senses_multiple: {len(root.cssselect('ol.senses_multiple'))}")
    print(f"  ol.sense_single: {len(root.cssselect('ol.sense_single'))}")
    li_sense_sel = 'li.sense, li[hclass="sense"]'
    print(f"  li.sense: {len(root.cssselect(li_sense_sel))}")

    # What does the merged record say for this? Match by source_files (any
    # record that lists this HTML as one of its contributing files).
    import json
    with open(paths.oxford_jsonl, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if fname in rec.get("source_files", []):
                print(f"  Recorded as word='{rec['word']}'")
                print(f"  source_files: {rec['source_files']}")
                print(f"  pos_data: {len(rec.get('pos_data', []))} entries")
                print(f"  idioms: {len(rec.get('idioms', []))} entries")
                if rec["pos_data"]:
                    for pd in rec["pos_data"]:
                        print(f"    [{pd['pos']}] {len(pd['definitions'])} defs")
                        for d in pd["definitions"][:2]:
                            print(f"      - {d['text'][:80]}")
                break
    print()
