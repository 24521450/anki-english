"""Properly verify dict contents via importlib."""
import json
import importlib.util

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl', encoding='utf-8') if l.strip()]
job_keys = set('{}|{}|{}'.format(j['word'], j['pos'], j['cefr']) for j in jobs)
dict_keys = set(mod.M3_VERDICTS.keys())

print('Jobs total:', len(job_keys))
print('Dict entries:', len(dict_keys))
print('Match:', len(job_keys & dict_keys))
print('Missing:', len(job_keys - dict_keys))

# Categorize the 150 matched entries
matched = []
for j in jobs:
    k = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
    if k in mod.M3_VERDICTS:
        matched.append((k, mod.M3_VERDICTS[k]))

# Group by rule
from collections import Counter
rules = Counter(m[1][3] for m in matched)
print('\nBy rule:')
for r, c in rules.most_common():
    print('  {}: {}'.format(r, c))