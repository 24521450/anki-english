"""
tools/fix_audit_semicolons.py
=============================
Fixes the bug where semicolon ';' is incorrectly used as a sense separator
instead of '|' in both deck_audit.jsonl and anki_notes.txt.

Only applies when the original def_before has multiple senses (contains '|').
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from src.config import ProjectPaths

paths = ProjectPaths()
ROOT = paths.root
AUDIT_FILE = paths.deck_audit_jsonl
DECK_FILE = paths.anki_notes_txt
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

DRY_RUN = "--dry-run" in sys.argv

def main():
    print("=" * 60)
    print("fix_audit_semicolons.py")
    print(f"DRY RUN: {DRY_RUN}")
    print("=" * 60)

    # 1. Read and fix audit lines
    print("\n[1/3] Processing audit file...")
    fixed_audit_records = {} # key -> new_gloss
    new_audit_lines = []
    
    with open(AUDIT_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                new_audit_lines.append(line)
                continue
            r = json.loads(line)
            gloss = r.get("gloss_after", "")
            def_before = r.get("def_before", "")
            
            has_semicolon = (r.get("separator") == ";") or (";" in gloss)
            has_multiple_senses = "|" in def_before
            
            if has_semicolon and has_multiple_senses:
                # Replace semicolons with pipes
                raw_new_gloss = gloss.replace(";", " |")
                # Normalize spaces
                new_gloss = " | ".join(part.strip() for part in raw_new_gloss.split("|") if part.strip())
                
                # Update record
                r["gloss_after"] = new_gloss
                r["separator"] = "|"
                
                key = (r["word"].strip().lower(), r["pos"].strip().lower(), r["cefr"].strip().upper())
                fixed_audit_records[key] = new_gloss
                
            new_audit_lines.append(json.dumps(r, ensure_ascii=False) + "\n")
            
    print(f"      Total audit records fixed: {len(fixed_audit_records)}")

    # 2. Update deck file
    print("\n[2/3] Processing deck file...")
    with open(DECK_FILE, encoding="utf-8") as f:
        deck_lines = f.readlines()
        
    updated_deck_count = 0
    new_deck_lines = []
    for line in deck_lines:
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
        key = (word, pos, cefr)
        
        if key in fixed_audit_records:
            new_gloss = fixed_audit_records[key]
            # Only update if different
            if parts[6].strip() != new_gloss:
                parts[6] = new_gloss
                updated_deck_count += 1
                if updated_deck_count <= 10:
                    print(f"  Deck update {word} ({pos}, {cefr}): {new_gloss}")
                    
        new_deck_lines.append("\t".join(parts) + "\n")
        
    print(f"      Total deck lines to update: {updated_deck_count}")

    # 3. Write changes
    if not DRY_RUN:
        # Backup Audit
        audit_backup = AUDIT_FILE.parent / (AUDIT_FILE.name + f".bak_semicolon_{TIMESTAMP}")
        shutil.copy2(AUDIT_FILE, audit_backup)
        print(f"\nAudit backup created: {audit_backup.name}")
        
        # Write Audit
        with open(AUDIT_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_audit_lines)
        print(f"Audit file updated: {AUDIT_FILE}")
        
        # Backup Deck
        deck_backup = DECK_FILE.parent / (DECK_FILE.name + f".bak_semicolon_{TIMESTAMP}")
        shutil.copy2(DECK_FILE, deck_backup)
        print(f"Deck backup created: {deck_backup.name}")
        
        # Write Deck
        with open(DECK_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_deck_lines)
        print(f"Deck file updated: {DECK_FILE}")
    else:
        print("\n[DRY RUN] No files written.")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Audit records fixed: {len(fixed_audit_records)}")
    print(f"  Deck cards updated:  {updated_deck_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
