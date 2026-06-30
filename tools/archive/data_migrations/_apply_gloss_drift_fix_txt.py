"""Apply semantic gloss drift fix to English Academic Vocabulary.txt.

Per task spec (2026-06-21):
- 7 TXT rows get new def column (column 6) to match audit fixes
- CEFR/Card Identity unchanged
- Column order preserved (tab-delimited)
"""
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
TXT = ROOT / "English Academic Vocabulary.txt"

# (word, pos, cefr) -> new def (column 6, English Academic Vocabulary)
# Only rows that exist in TXT get updated.
TARGETS = {
    ("concrete", "adjective, noun", "B2"): "cement-based building material",
    ("deposit", "noun", "B2"): "down payment; security",
    ("fit", "noun", "C1"): "sudden attack",
    ("manual", "noun", "C2"): "stick-shift car",
    ("pitch", "noun", "B2"): "sports field",
    ("sake", "noun", "C1"): "Japanese rice wine",
    ("sanctuary", "noun", "C1"): "wildlife refuge",
}


def main():
    # Read raw bytes to preserve original encoding exactly
    raw = TXT.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    updated = 0
    new_lines = []

    for ln in lines:
        if not ln.strip():
            new_lines.append(ln)
            continue
        parts = ln.split("\t")
        if len(parts) < 17:
            new_lines.append(ln)
            continue
        # columns: 0=GUID, 1=notetype, 2=deck, 3=word, 4=pos, 5=IPA, 6=def,
        # 7=example, 8=?, 9=?, 10=UK_audio, 11=US_audio, 12=src1, 13=src2,
        # 14=cefr, 15=?, 16=tags
        word = parts[3]
        pos = parts[4]
        cefr = parts[14]
        key = (word, pos, cefr)
        if key in TARGETS:
            parts[6] = TARGETS[key]
            updated += 1
        new_lines.append("\t".join(parts))

    out = "\n".join(new_lines) + "\n"
    if not raw.endswith(b"\n"):
        # original didn't end with newline? keep as-is
        out = "\n".join(new_lines)

    tmp = TXT.with_suffix(".txt.tmp_glossdrift")
    tmp.write_bytes(out.encode("utf-8"))
    tmp.replace(TXT)
    print(f"Updated {updated} TXT rows in {TXT.name}")
    print(f"Total target rows: {len(TARGETS)}")


if __name__ == "__main__":
    main()