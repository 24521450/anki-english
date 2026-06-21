"""Surgically update col 14 (CEFR) in txt from new oxford_merged.jsonl.
Only update cards where the new sense-level CEFR differs from the txt's current CEFR.
Preserve all other columns and Cambridge/AWL cards unchanged.
"""
import json
from pathlib import Path
from collections import Counter

txt_path = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
backup_path = txt_path.with_suffix('.txt.bak_pre_cefr_only_20260618')
oxford_path = Path(r'C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl')

# Backup current (2528)
if not backup_path.exists():
    import shutil
    shutil.copy2(txt_path, backup_path)
    print(f'Backup created: {backup_path.name}')

# Load oxford_merged: build (word_lower, pos) -> list of sense CEFRs
oxford_cefrs = {}  # (word_lower, pos) -> list of CEFRs
for line in oxford_path.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    word_lower = (r.get('word') or '').lower()
    for pd in r.get('pos_data') or []:
        pos = pd.get('pos') or ''
        for d in pd.get('definitions') or []:
            cefr = d.get('cefr')
            if cefr:
                oxford_cefrs.setdefault((word_lower, pos), []).append(cefr)

# For each (word, pos) -> highest CEFR (A1 < A2 < B1 < B2 < C1 < C2)
cefr_order = {'A1': 1, 'A2': 2, 'B1': 3, 'B2': 4, 'C1': 5, 'C2': 6}
def highest_cefr(cefrs):
    valid = [c for c in cefrs if c in cefr_order]
    if not valid:
        return None
    return max(valid, key=lambda c: cefr_order[c])

# Read txt
lines = txt_path.read_text(encoding='utf-8').splitlines()
out_lines = []
updated = 0
unchanged = 0
no_oxford_data = 0
samples = []
for line in lines:
    if line.startswith('#') or not line.strip():
        out_lines.append(line)
        continue
    p = line.split('\t')
    if len(p) < 16:
        out_lines.append(line)
        continue
    word = p[3]
    pos = p[4]
    old_cefr = p[14]
    word_lower = word.lower()

    # Look up new sense CEFR
    new_cefrs = oxford_cefrs.get((word_lower, pos), [])
    new_cefr = highest_cefr(new_cefrs) if new_cefrs else None

    # Conservative: only update UNCLASSIFIED → real CEFR
    # Don't change existing CEFR (preserves badge-based CEFR like B2 pace)
    if old_cefr in ('UNCLASSIFIED', '', 'unclassified'):
        if new_cefr:
            # Upgrade UNCLASSIFIED → real CEFR
            p[14] = new_cefr
            updated += 1
            if len(samples) < 15:
                samples.append((word, pos, old_cefr, new_cefr))
        else:
            no_oxford_data += 1
    else:
        unchanged += 1
    out_lines.append('\t'.join(p))

# Write back
txt_path.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')

print(f'Updated CEFR: {updated}')
print(f'Unchanged: {unchanged}')
print(f'No oxford data (preserved old): {no_oxford_data}')
print(f'\nFirst 10 updates:')
for w, p, o, n in samples:
    print(f'  {w}|{p}: {o!r} → {n!r}')
