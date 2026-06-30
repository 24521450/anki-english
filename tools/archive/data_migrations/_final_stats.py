"""Final stats."""
import json
import importlib.util
import sys
sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl', encoding='utf-8') if l.strip()]
from src.deck_builder.gloss_llm import detect_category
total = len(jobs)
matched = sum(1 for j in jobs if '{}|{}|{}'.format(j['word'], j['pos'], j['cefr']) in mod.M3_VERDICTS)
print('Jobs: {}, M3 verdicts: {}, Pass rate: {}%'.format(total, matched, 100*matched//total))
from collections import Counter
rules = Counter(v[3] for v in mod.M3_VERDICTS.values())
print('Rules distribution:')
for r, c in rules.most_common():
    print('  {}: {}'.format(r, c))