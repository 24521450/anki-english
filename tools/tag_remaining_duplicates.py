import json
from pathlib import Path

root = Path(r"C:\Users\admin\Downloads\ankideck")
txt_path = root / "English Academic Vocabulary.txt"
jsonl_path = root / "data" / "anki_notes.jsonl"

# Redundant card GUIDs to tag with delete:
TO_DELETE = {
    "oBVbeIKh6)": "short-sighted",
    ":#6S8]_#y_": "proceeding",
    "gL,-0[9FQX": "accuse",
    "D]U4cAU!~#": "diplomatic"
}

def tag_txt():
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    tagged_count = 0
    for line in lines:
        if line.startswith("#") or not line.strip():
            new_lines.append(line)
            continue
        parts = line.split("\t")
        if len(parts) >= 17:
            guid = parts[0].strip('"')
            if guid in TO_DELETE:
                tags = parts[16].split()
                if "delete" not in tags:
                    tags.append("delete")
                    parts[16] = " ".join(tags)
                    tagged_count += 1
                    print(f"Tagged TXT GUID {guid} ({TO_DELETE[guid]}) with 'delete'")
        new_lines.append("\t".join(parts))
    txt_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Total tagged in TXT: {tagged_count}")

def tag_jsonl():
    if not jsonl_path.exists():
        return
    rows = [json.loads(l) for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    tagged_count = 0
    for r in rows:
        guid = r["guid"]
        if guid in TO_DELETE:
            tags = r["tags"].split()
            if "delete" not in tags:
                tags.append("delete")
                r["tags"] = " ".join(tags)
                tagged_count += 1
                print(f"Tagged JSONL GUID {guid} ({TO_DELETE[guid]}) with 'delete'")
    
    tmp_path = jsonl_path.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp_path.replace(jsonl_path)
    print(f"Total tagged in JSONL: {tagged_count}")

if __name__ == "__main__":
    tag_txt()
    tag_jsonl()
