"""Extract the 108 remaining multi-sense-3+ jobs to a file for review."""
import json
import sys
import importlib.util

sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.deck_builder.gloss_llm import detect_category

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl', encoding='utf-8') if l.strip()]
multi_3plus = []
for j in jobs:
    key = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
    if key not in mod.M3_VERDICTS and detect_category(j['def'], j['pos']) == 'multi-sense-3+':
        multi_3plus.append(j)

print('Multi-sense-3+ missing: {}'.format(len(multi_3plus)))
# Sort alphabetically by word for review
multi_3plus.sort(key=lambda x: x['word'])

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\_review_multi_3plus.txt', 'w', encoding='utf-8') as f:
    for j in multi_3plus:
        f.write('{}|{}|{}\n'.format(j['word'], j['pos'], j['cefr']))
        f.write('  DEF: {}\n'.format(j['def']))
        f.write('---\n')

print('Wrote review file.')