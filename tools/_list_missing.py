"""List missing jobs by category."""
import json
import sys
import importlib.util

sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.deck_builder.gloss_llm import detect_category

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl', encoding='utf-8') if l.strip()]
missing_by_cat = {}
for j in jobs:
    key = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
    if key not in mod.M3_VERDICTS:
        c = detect_category(j['def'], j['pos'])
        missing_by_cat.setdefault(c, []).append((key, j['def']))

for c in ['multi-sense-3+', 'concrete', 'multi-pos', 'abstract']:
    print('=== {}: {} ==='.format(c, len(missing_by_cat.get(c, []))))
    for k, d in missing_by_cat.get(c, []):
        print('  {}: {}'.format(k, d[:200]))
    print()