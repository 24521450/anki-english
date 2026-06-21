"""List remaining Stream C — last 25 concrete + abstract + multi-pos first batch."""
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

by_cat = {'concrete': [], 'abstract': [], 'multi-pos': []}
for j in jobs:
    key = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
    if key not in mod.M3_VERDICTS:
        cat = detect_category(j['def'], j['pos'])
        by_cat[cat].append((key, j['def']))

for cat in by_cat:
    by_cat[cat].sort()

print('Counts:')
for k, v in by_cat.items():
    print('  {}: {}'.format(k, len(v)))

print('\n=== Remaining concrete ===')
for k, d in by_cat['concrete']:
    print('{}: {}'.format(k, d[:150]))
    print('---')

print('\n=== Abstract (first 40) ===')
for k, d in by_cat['abstract'][:40]:
    print('{}: {}'.format(k, d[:150]))
    print('---')