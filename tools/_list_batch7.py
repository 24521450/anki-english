"""List 40-80 for batch 7."""
import json
jobs_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl'
v_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_violations.json'
jobs = [json.loads(l) for l in open(jobs_path, encoding='utf-8') if l.strip()]
violations = json.load(open(v_path, encoding='utf-8'))
job_by_key = {'{}|{}|{}'.format(j['word'], j['pos'], j['cefr']): j for j in jobs}
sorted_keys = sorted(violations.keys())
for k in sorted_keys[40:80]:
    j = job_by_key.get(k)
    if not j: continue
    print('\n{}:'.format(k))
    print('  DEF: {}'.format(j['def'][:200]))
    print('  ERR: {}'.format(violations[k]))