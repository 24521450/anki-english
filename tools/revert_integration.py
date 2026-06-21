from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
DECK_FILE = ROOT / "English Academic Vocabulary.txt"
ANKI_NOTES_JSONL = ROOT / "data" / "anki_notes.jsonl"
AUDIT_FILE = ROOT / "data" / "audit_full_deck_v2.jsonl"

def revert_append(file_path, num_lines=30):
    if not file_path.exists():
        return
    lines = file_path.read_text(encoding="utf-8").splitlines()
    if len(lines) >= num_lines:
        new_lines = lines[:-num_lines]
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print(f"Reverted last {num_lines} lines from {file_path.name}")
    else:
        print(f"File {file_path.name} is too short, skipping.")

revert_append(DECK_FILE, 30)
revert_append(ANKI_NOTES_JSONL, 30)
revert_append(AUDIT_FILE, 30)
print("Revert complete!")
