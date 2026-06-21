import json
import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
JSONL_PATH = ROOT / "data" / "anki_notes.jsonl"
TXT_PATH = ROOT / "English Academic Vocabulary.txt"

# Actions defines how to modify cards by GUID:
# - To delete: (guid, "delete")
# - To change POS: (guid, "pos", new_pos)
ACTIONS = {
    # 1. evolve (same POS verb: keep B2, delete UNCLASSIFIED)
    '"D#.J*hAq*`"': ("delete",),
    
    # 2. eliminate (same POS verb: keep B2, delete UNCLASSIFIED)
    "9xt7Ft@EfZ": ("delete",),
    
    # 3. resilient (same POS adjective: keep C2, delete UNCLASSIFIED)
    "FGe;(pa3z{": ("delete",),
    
    # 4. harbour (different POS: keep B2 noun, keep UNCLASSIFIED verb)
    "m}g1cKg({G": ("pos", "verb"),  # Change from 'noun, verb' to 'verb'
    
    # 5. designate (different POS: keep C1 verb, keep UNCLASSIFIED adjective)
    # xKlE{U(XC3 is already adjective, wZ=c(ksyun is already verb. No POS modification needed.
    
    # 6. mainland (different POS: keep C1 noun, keep UNCLASSIFIED adjective)
    "K_[xKnI.vU": ("pos", "noun"),  # Change from 'adjective, noun' to 'noun'
    
    # 7. well-being (same POS noun: keep C1, delete UNCLASSIFIED)
    "Z0=7qzO${t": ("delete",),
    
    # 8. invade (same POS verb: keep B2, delete UNCLASSIFIED)
    "bV|Nk8ga}t": ("delete",),
}

def _add_delete_tag(tags_str: str) -> str:
    tokens = tags_str.split() if tags_str else []
    if "delete" not in tokens:
        tokens.append("delete")
    return " ".join(tokens)

def tag_jsonl():
    if not JSONL_PATH.exists():
        print("anki_notes.jsonl not found, skipping tag_jsonl")
        return
    
    # Backup JSONL
    backup_path = JSONL_PATH.with_suffix(".jsonl.bak_pre_unclass_dup_20260621")
    shutil.copy2(JSONL_PATH, backup_path)
    print(f"Backed up JSONL to {backup_path.name}")
    
    cards = []
    with JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cards.append(json.loads(line))

    updated_pos = 0
    tagged_del = 0

    for card in cards:
        guid = card.get("guid")
        if guid in ACTIONS:
            action = ACTIONS[guid]
            if action[0] == "delete":
                old_tags = card.get("tags", "")
                new_tags = _add_delete_tag(old_tags)
                if new_tags != old_tags:
                    card["tags"] = new_tags
                    tagged_del += 1
                    print(f"Tagged JSONL card {guid} ({card.get('word')}) with 'delete'")
            elif action[0] == "pos":
                new_pos = action[1]
                if card.get("pos") != new_pos:
                    card["pos"] = new_pos
                    updated_pos += 1
                    print(f"Updated JSONL card {guid} ({card.get('word')}) POS to {new_pos}")

    # Write back
    tmp_path = JSONL_PATH.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    tmp_path.replace(JSONL_PATH)

    print(f"JSONL: POS updated: {updated_pos}, Delete tagged: {tagged_del}")

def tag_txt():
    if not TXT_PATH.exists():
        print("TXT file not found, skipping tag_txt")
        return

    # Backup TXT
    backup_path = TXT_PATH.parent / (TXT_PATH.name + ".bak_pre_unclass_dup_20260621")
    shutil.copy2(TXT_PATH, backup_path)
    print(f"Backed up TXT to {backup_path.name}")

    lines = TXT_PATH.read_text(encoding="utf-8").splitlines()
    header_lines = []
    body_lines = []
    for line in lines:
        if line.startswith("#") or not line.strip():
            header_lines.append(line)
        else:
            body_lines.append(line)

    updated_pos = 0
    tagged_del = 0

    new_body = []
    for line in body_lines:
        parts = line.split("\t")
        if len(parts) < 17:
            new_body.append(line)
            continue
        guid = parts[0]

        if guid in ACTIONS:
            action = ACTIONS[guid]
            if action[0] == "delete":
                old_tags = parts[16]
                new_tags = _add_delete_tag(old_tags)
                if new_tags != old_tags:
                    parts[16] = new_tags
                    tagged_del += 1
                    print(f"Tagged TXT card {guid} ({parts[3]}) with 'delete'")
            elif action[0] == "pos":
                new_pos = action[1]
                if parts[4] != new_pos:
                    parts[4] = new_pos
                    updated_pos += 1
                    print(f"Updated TXT card {guid} ({parts[3]}) POS to {new_pos}")

        new_body.append("\t".join(parts))

    new_txt = "\n".join(header_lines + new_body) + "\n"
    TXT_PATH.write_text(new_txt, encoding="utf-8")

    print(f"TXT:   POS updated: {updated_pos}, Delete tagged: {tagged_del}")

def main():
    print("Tagging and POS-merging 8 UNCLASSIFIED duplicate groups...")
    tag_jsonl()
    tag_txt()

if __name__ == "__main__":
    main()
