"""List violations sorted by word, with original def + violation reasons."""
import json
import sys

jobs_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl'
v_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_violations.json'

jobs = [json.loads(l) for l in open(jobs_path, encoding='utf-8') if l.strip()]
violations = json.load(open(v_path, encoding='utf-8'))

job_by_key = {'{}|{}|{}'.format(j['word'], j['pos'], j['cefr']): j for j in jobs}

# Sort by key for review
sorted_keys = sorted(violations.keys())
print('Total keys to fix: {}'.format(len(sorted_keys)))

# Print first 30
for k in sorted_keys[:30]:
    j = job_by_key.get(k)
    if not j:
        print('  {}: NO JOB'.format(k))
        continue
    print('\n--- {} ---'.format(k))
    print('  DEF: {}'.format(j['def']))
    print('  ERR: {}'.format(violations[k]))