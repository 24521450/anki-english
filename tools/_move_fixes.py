"""Move my inserts from middle of dict to end (before closing brace).
Fixes Python dict literal last-wins bug where existing entries override my fixes."""
from pathlib import Path

p = Path(r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
text = p.read_text(encoding='utf-8')
lines = text.split('\n')

# Find my insert block boundaries
# Lines 299-478 contain my inserts (Step 3b header + entries)
# Line 298 ends multi-sense-3+ section ('worthy')
# Line 479 starts original concrete batch 1 ('absurd')
# Line 841 ends concrete batches ('restoration')
# Line 842 is '}'

# Find line numbers by content
insert_start = None
insert_end = None
dict_end = None
for i, line in enumerate(lines):
    if line.strip().startswith('# === Step 3b'):
        insert_start = i
    elif insert_start is not None and insert_end is None:
        if line.strip().startswith("'absurd|adjective|C1'"):
            insert_end = i
    if line.strip() == '}' and i > 700:
        dict_end = i
        break

print('insert_start={}, insert_end={}, dict_end={}'.format(insert_start, insert_end, dict_end))

# Extract insert block (with leading comment)
insert_block = lines[insert_start:insert_end]
print('Insert block: {} lines'.format(len(insert_block)))

# Build new structure:
# - lines[0:insert_start] (before my inserts)
# - lines[insert_end:dict_end] (original concrete batches)
# - insert_block (my fixes)
# - '}'
# - lines[dict_end+1:] (rest: def main(), etc.)

new_lines = (
    lines[:insert_start]
    + lines[insert_end:dict_end]
    + ['']  # blank line
    + ['    # === M3 REGEN FIXES (must be LAST in dict for last-wins semantics) ===']
    + insert_block[1:]  # skip the "# === Step 3b" comment
    + lines[dict_end:]
)

p.write_text('\n'.join(new_lines), encoding='utf-8')
print('Wrote {} lines'.format(len(new_lines)))