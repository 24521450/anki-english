import json
jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_jobs.jsonl', encoding='utf-8')]
print('Total jobs:', len(jobs))
targets = ['albeit', 'auto', 'bliss', 'furious', 'greatly', 'info', 'newly', 'predominantly', 'primarily', 'spectacular', 'pace']
for j in jobs:
    if j['word'] in targets:
        word = j['word']
        pos = j['pos']
        cefr = j['cefr']
        defn = j['def'][:80]
        print(f'  {word}|{pos}|{cefr}: {defn!r}')
