"""Spot check: run resolve_cards on real records from oxford_merged.jsonl.

Verifies that the builder works on real-world data, not just synthetic test
records. Picks 6 representative records: simple, multi-CEFR, sense cap, homonym,
phrasal-verb-fold, proper-noun-skip.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder import resolve_cards  # noqa: E402

PATH = r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl"

with open(PATH, encoding="utf-8") as f:
    records = [json.loads(l) for l in f]

# Pick test cases
TARGETS = ["sick", "aggregate", "like", "run", "bass", "deprive", "Buck Rogers", "DVD", "Ambition"]

print("Real-world spot check on resolve_cards:")
print()
for w in TARGETS:
    matches = [r for r in records if r["word"] == w]
    if not matches:
        print(f"  {w}: NOT IN DATA")
        continue
    for r in matches:
        skip = r.get("_skip")
        notes = resolve_cards(r)
        cefrs = sorted(n["CEFRLevel"] for n in notes)
        print(f"  {w:15s} (h={r.get('homonym_index')}, _skip={skip}): "
              f"{len(notes)} notes, CEFRs={cefrs}")
        # Show first note's fields for verification
        if notes:
            n = notes[0]
            print(f"    Word={n['Word']!r} CEFRLevel={n['CEFRLevel']!r} "
                  f"POS={n['PartOfSpeech']!r}")
            print(f"    Definition={n['Definition'][:80]!r}{'...' if len(n['Definition']) > 80 else ''}")
            if n['AudioUK'] or n['AudioUS']:
                print(f"    AudioUK={'yes' if n['AudioUK'] else 'no'} "
                      f"AudioUS={'yes' if n['AudioUS'] else 'no'}")
            if n['Collocations']:
                print(f"    Collocations: {len(n['Collocations'].split('|'))} chips")
            if n['Tags']:
                print(f"    Tags: {n['Tags']}")
        print()
