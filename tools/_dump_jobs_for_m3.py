"""Read 258 multi-sense-3+ jobs and dump to text for M3 generation."""
import json
import sys
from pathlib import Path
sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.deck_builder.gloss_llm import detect_category

JOBS_PATH = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl')
OUT = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_input.txt')

jobs = [json.loads(l) for l in JOBS_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]

# Filter multi-sense-3+ and sort
ms3 = [j for j in jobs if detect_category(j['def'], j['pos']) == 'multi-sense-3+']
ms3.sort(key=lambda j: (j['word'], j['pos'], j['cefr']))

lines = [f'{len(ms3)} multi-sense-3+ jobs:', '=' * 60]
for i, j in enumerate(ms3, 1):
    w, p, c = j['word'], j['pos'], j['cefr']
    d = j['def']
    lines.append(f'\n[{i:3}] {w}|{p}|{c}')
    lines.append(f'     def: {d}')

OUT.write_text('\n'.join(lines), encoding='utf-8')
print(f'Wrote {len(ms3)} multi-sense-3+ jobs to {OUT}')
