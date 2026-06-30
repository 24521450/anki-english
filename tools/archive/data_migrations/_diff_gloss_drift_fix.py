"""Generate a diff-style report of audit + TXT changes for the user.

Side-by-side: old -> new, for each touched row.
"""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
AUDIT = ROOT / "data" / "audit_full_deck_v2.jsonl"
TXT = ROOT / "English Academic Vocabulary.txt"

# 1) AUDIT diff
bak_audit = sorted((ROOT / "data").glob("audit_full_deck_v2.jsonl.bak_pre_glossdriftfix_*"))[-1]
old_audit_rows = [json.loads(l) for l in bak_audit.read_text(encoding="utf-8").splitlines() if l.strip()]
new_audit_rows = [json.loads(l) for l in AUDIT.read_text(encoding="utf-8").splitlines() if l.strip()]

# Index by (word, pos, cefr) for both
def key(r):
    return (r.get("word"), r.get("pos"), r.get("cefr"))

old_idx = {}
for r in old_audit_rows:
    old_idx.setdefault(key(r), []).append(r)
new_idx = {}
for r in new_audit_rows:
    new_idx.setdefault(key(r), []).append(r)

# Find keys where any field changed
keys = set(old_idx) | set(new_idx)
changed = []
for k in sorted(keys):
    olds = old_idx.get(k, [])
    news = new_idx.get(k, [])
    if olds and news and len(olds) == len(news):
        for o, n in zip(olds, news):
            if o != n:
                changed.append((k, o, n))

lines = []
lines.append("# AUDIT file: data/audit_full_deck_v2.jsonl\n")
lines.append(f"Old: {bak_audit.name}\n")
lines.append(f"New: audit_full_deck_v2.jsonl\n\n")
lines.append(f"Total rows changed: {len(changed)}\n\n")
lines.append("| key | old `gloss_after` (sep, wc) | new `gloss_after` (sep, wc) |")
lines.append("|---|---|---|")
for k, o, n in changed:
    lines.append(
        f"| `{k[0]}|{k[1]}|{k[2]}` | "
        f"`{o['gloss_after']}` (sep={o['separator']!r}, wc={o['gloss_word_count']}) | "
        f"`{n['gloss_after']}` (sep={n['separator']!r}, wc={n['gloss_word_count']}) |"
    )

# 2) TXT diff
bak_txt = sorted(ROOT.glob("English Academic Vocabulary.txt.bak_pre_glossdriftfix_*"))[-1]
old_txt = bak_txt.read_text(encoding="utf-8").splitlines()
new_txt = TXT.read_text(encoding="utf-8").splitlines()


def parse_line(line):
    parts = line.split("\t")
    if len(parts) < 17:
        return None
    return {
        "guid": parts[0],
        "word": parts[3],
        "pos": parts[4],
        "ipa": parts[5],
        "def": parts[6],
        "cefr": parts[14],
        "tags": parts[16],
    }


old_txt_idx = {}
for line in old_txt:
    if not line.strip():
        continue
    p = parse_line(line)
    if p:
        old_txt_idx.setdefault((p["word"], p["pos"], p["cefr"]), []).append(p)
new_txt_idx = {}
for line in new_txt:
    if not line.strip():
        continue
    p = parse_line(line)
    if p:
        new_txt_idx.setdefault((p["word"], p["pos"], p["cefr"]), []).append(p)

txt_changed = []
keys = set(old_txt_idx) | set(new_txt_idx)
for k in sorted(keys):
    olds = old_txt_idx.get(k, [])
    news = new_txt_idx.get(k, [])
    if olds and news and len(olds) == len(news):
        for o, n in zip(olds, news):
            if o["def"] != n["def"]:
                txt_changed.append((k, o, n))

lines.append("\n\n# TXT file: English Academic Vocabulary.txt\n")
lines.append(f"Old: {bak_txt.name}\n")
lines.append(f"New: English Academic Vocabulary.txt\n\n")
lines.append(f"Total rows changed: {len(txt_changed)}\n\n")
lines.append("| key | old def | new def |")
lines.append("|---|---|---|")
for k, o, n in txt_changed:
    lines.append(
        f"| `{k[0]}|{k[1]}|{k[2]}` | `{o['def']}` | `{n['def']}` |"
    )

out_path = ROOT / "data" / "gloss_drift_fix_report.md"
out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Report written to: {out_path}")
print()
print("\n".join(lines))