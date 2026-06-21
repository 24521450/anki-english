"""
tools/fix_pop_verb.py
====================
Updates the definition of pop (verb, C1) in both audit_full_deck_v2.jsonl
and English Academic Vocabulary.txt to resolve the dropped sense bug.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
AUDIT_FILE = ROOT / "data" / "audit_full_deck_v2.jsonl"
DECK_FILE = ROOT / "English Academic Vocabulary.txt"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

def main():
    print("=" * 60)
    print("fix_pop_verb.py")
    print("=" * 60)

    # 1. Update Audit File
    print("\n[1/3] Updating audit file...")
    audit_updated = False
    new_audit_lines = []
    
    with open(AUDIT_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                new_audit_lines.append(line)
                continue
            r = json.loads(line)
            if r.get("word") == "pop" and r.get("pos") == "verb" and r.get("cefr") == "C1":
                r["gloss_after"] = "burst | move quickly | appear suddenly"
                r["separator"] = "|"
                audit_updated = True
                print(f"  Audit update: pop (verb, C1) -> {r['gloss_after']}")
            new_audit_lines.append(json.dumps(r, ensure_ascii=False) + "\n")
            
    if not audit_updated:
        print("  WARNING: pop (verb, C1) not found in audit file!")

    # 2. Update Deck File
    print("\n[2/3] Updating deck file...")
    deck_updated = False
    new_deck_lines = []
    
    with open(DECK_FILE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                new_deck_lines.append(line)
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 16:
                new_deck_lines.append(line)
                continue
                
            word = parts[3].strip().lower()
            pos = parts[4].strip().lower()
            cefr = parts[14].strip().upper()
            
            if word == "pop" and pos == "verb" and cefr == "C1":
                parts[6] = "burst | move quickly | appear suddenly"
                deck_updated = True
                print(f"  Deck update: pop (verb, C1) -> {parts[6]}")
                
            new_deck_lines.append("\t".join(parts) + "\n")
            
    if not deck_updated:
        print("  WARNING: pop (verb, C1) not found in deck file!")

    # 3. Save Files
    if audit_updated or deck_updated:
        # Backup & write Audit
        if audit_updated:
            audit_backup = AUDIT_FILE.parent / (AUDIT_FILE.name + f".bak_pop_{TIMESTAMP}")
            shutil.copy2(AUDIT_FILE, audit_backup)
            print(f"\nAudit backup created: {audit_backup.name}")
            with open(AUDIT_FILE, "w", encoding="utf-8") as f:
                f.writelines(new_audit_lines)
            print("Audit file updated successfully.")
            
        # Backup & write Deck
        if deck_updated:
            deck_backup = DECK_FILE.parent / (DECK_FILE.name + f".bak_pop_{TIMESTAMP}")
            shutil.copy2(DECK_FILE, deck_backup)
            print(f"Deck backup created: {deck_backup.name}")
            with open(DECK_FILE, "w", encoding="utf-8") as f:
                f.writelines(new_deck_lines)
            print("Deck file updated successfully.")
    else:
        print("\nNo updates performed.")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Audit updated: {audit_updated}")
    print(f"  Deck updated:  {deck_updated}")
    print("=" * 60)

if __name__ == "__main__":
    main()
