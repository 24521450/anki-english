import json
import hashlib
jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_jobs.jsonl', encoding='utf-8')]
ab = [j for j in jobs if j.get('word') == 'abdominal']
for j in ab:
    print('hash:', j.get('hash'))
    print('def:', repr(j.get('def', '')))
    key = j['word'] + '|' + j['pos'] + '|' + j['cefr'] + '|' + j['def']
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    print('computed:', h)
    print('key:', repr(key))
