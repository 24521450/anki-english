"""Diagnose why some keys exist in dict but are reported missing."""
import json
import importlib.util

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl', encoding='utf-8') if l.strip()]

# Show absence job
for j in jobs:
    if j['word'] == 'absence':
        print('Job absence:', repr(j['word']), repr(j['pos']), repr(j['cefr']))
        key = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
        print('  Job key:', repr(key))
        print('  In dict?', key in mod.M3_VERDICTS)
        break

# Show orient job
for j in jobs:
    if j['word'] == 'orient':
        print('Job orient:', repr(j['word']), repr(j['pos']), repr(j['cefr']))
        key = '{}|{}|{}'.format(j['word'], j['pos'], j['cefr'])
        print('  Job key:', repr(key))
        print('  In dict?', key in mod.M3_VERDICTS)
        break

# Show some in dict but not in jobs
dict_keys = set(mod.M3_VERDICTS.keys())
job_keys = set('{}|{}|{}'.format(j['word'], j['pos'], j['cefr']) for j in jobs)
in_dict_not_jobs = dict_keys - job_keys
print('\nIn dict but NOT in jobs (first 10):', list(in_dict_not_jobs)[:10])
print('  count:', len(in_dict_not_jobs))
print('\nIn jobs but NOT in dict (first 10):', list(job_keys - dict_keys)[:10])
print('  count:', len(job_keys - dict_keys))