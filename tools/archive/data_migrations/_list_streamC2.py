"""Dump next 40 Stream C concrete."""
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

missing_concrete = []
for j in jobs:
    key = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
    if key not in mod.M3_VERDICTS and detect_category(j['def'], j['pos']) == 'concrete':
        missing_concrete.append((key, j['def']))

missing_concrete.sort()
print('Concrete remaining: {}'.format(len(missing_concrete)))
for k, d in missing_concrete[:40]:
    print('{}: {}'.format(k, d[:200]))
    print('---')