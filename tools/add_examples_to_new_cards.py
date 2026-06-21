"""
tools/add_examples_to_new_cards.py
==================================
Enriches the newly added 10 cards with examples from oxford_merged.jsonl
(using the first matching CEFR sense) and tags deposit noun C2 as 'Delete'.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DECK_FILE = ROOT / "English Academic Vocabulary.txt"
OXFORD_FILE = ROOT / "data" / "oxford_merged.jsonl"
BACKUP_SUFFIX = f".bak_pre_examples_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

DRY_RUN = "--dry-run" in sys.argv

TARGET_CARDS = {
    ("labor", "noun", "C2"),
    ("craft", "noun", "C2"),
    ("deposit", "noun", "C1"),
    ("fit", "noun", "B2"),
    ("migrate", "verb", "B2"),
    ("navigate", "verb", "B2"),
    ("sanctuary", "noun", "C1"),
    ("total", "verb", "C2"),
    ("pop", "verb", "C2"),
    ("trigger", "verb", "C2"),
}

DELETE_CARD = ("deposit", "noun", "C2")

def load_oxford_examples(path: Path) -> dict:
    """
    Returns {(word_lower, pos_lower, cefr_upper): example_string}
    where example_string is examples separated by '|' from the first matching sense.
    """
    examples_map = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            word = r.get("word", "").strip().lower()
            for pos_data in r.get("pos_data", []):
                pos = pos_data.get("pos", "").strip().lower()
                
                # We want to find the first sense for each CEFR level
                cefr_seen = set()
                for d in pos_data.get("definitions", []):
                    cefr = (d.get("cefr") or "").strip().upper()
                    if not cefr:
                        continue
                    
                    key = (word, pos, cefr)
                    if key in TARGET_CARDS and cefr not in cefr_seen:
                        cefr_seen.add(cefr)
                        
                        # Extract examples
                        exs = [e.get("text", "").strip() for e in d.get("examples", []) if e.get("text")]
                        if exs:
                            examples_map[key] = " | ".join(exs)
    return examples_map

def main():
    print("=" * 60)
    print("add_examples_to_new_cards.py")
    print(f"DRY RUN: {DRY_RUN}")
    print("=" * 60)

    # 1. Load Oxford Examples
    print("\n[1/3] Loading Oxford examples...")
    examples_map = load_oxford_examples(OXFORD_FILE)
    for key, exs in examples_map.items():
        print(f"  {key[0]} ({key[1]}, {key[2]}): {exs[:80]}...")

    # 2. Load Deck File
    print("\n[2/3] Loading deck file...")
    with open(DECK_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    print(f"      Deck lines loaded: {len(lines)}")

    # 3. Process lines
    print("\n[3/3] Processing cards...")
    updated_ex_count = 0
    tagged_delete_count = 0
    
    new_lines = []
    for line in lines:
        if line.startswith("#") or not line.strip():
            new_lines.append(line)
            continue
            
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 16:
            new_lines.append(line)
            continue
            
        word = parts[3].strip().lower()
        pos = parts[4].strip().lower()
        cefr = parts[14].strip().upper()
        key = (word, pos, cefr)
        
        # Check if this is the deposit C2 card to delete
        if key == DELETE_CARD:
            tags = parts[15].strip().split()
            if "Delete" not in tags:
                tags.append("Delete")
                parts[15] = " ".join(tags)
                tagged_delete_count += 1
                print(f"  TAGGED DELETE: {word} {pos} {cefr}")
            
        # Check if this is one of the 10 target cards and has empty examples
        elif key in TARGET_CARDS and parts[7].strip() == "":
            exs = examples_map.get(key)
            if exs:
                parts[7] = exs
                updated_ex_count += 1
                print(f"  ADDED EXAMPLES to {word} {pos} {cefr}: {exs[:80]}")
            else:
                print(f"  WARNING: No examples found in Oxford for {word} {pos} {cefr}")
                
        new_lines.append("\t".join(parts) + "\n")

    # 4. Save file
    if not DRY_RUN:
        # Create Backup
        backup_path = DECK_FILE.parent / (DECK_FILE.name + BACKUP_SUFFIX)
        shutil.copy2(DECK_FILE, backup_path)
        print(f"\nBackup created: {backup_path.name}")
        
        with open(DECK_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Deck written: {DECK_FILE}")
    else:
        print("\n[DRY RUN] No file written.")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Examples added: {updated_ex_count}")
    print(f"  Tagged Delete:  {tagged_delete_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
