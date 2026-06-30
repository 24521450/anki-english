"""Dump MISSING jobs (Stream C) for batch C1."""
import json
import sys
sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.deck_builder.gloss_llm import detect_category

jobs_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl'
jobs = [json.loads(l) for l in open(jobs_path, encoding='utf-8') if l.strip()]

import importlib.util
spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

missing_by_cat = {}
for j in jobs:
    key = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
    if key not in mod.M3_VERDICTS:
        cat = detect_category(j['def'], j['pos'])
        missing_by_cat.setdefault(cat, []).append((key, j['def']))

print('=== Stream C missing by category ===')
for c, lst in sorted(missing_by_cat.items(), key=lambda x: -len(x[1])):
    print('{}: {}'.format(c, len(lst)))

# Save concrete batch C1 (first 50)
concrete = sorted(missing_by_cat.get('concrete', []))
print('\n=== First 40 concrete ===')
for k, d in concrete[:40]:
    print('{}: {}'.format(k, d[:200]))
    print('---')