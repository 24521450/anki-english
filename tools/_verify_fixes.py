"""Verify state of dict + violations."""
import importlib.util
import json

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from src.deck_builder.gloss_llm import validate_verdict

# Find headword_in_chunk[0] entries still
v = json.load(open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_violations.json', encoding='utf-8'))
jobs = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl', encoding='utf-8') if l.strip()]
job_by_key = {'{}|{}|{}'.format(j['word'], j['pos'], j['cefr']): j for j in jobs}

# Check the recently-fixed entries still in violations
recent_keys = [
    'intervention|noun|C1', 'kit|noun|B2', 'lane|noun|B2', 'lens|noun|B2',
    'logic|noun|C1', 'marker|noun|B2', 'misery|noun|C1', 'mortality|noun|UNCLASSIFIED',
    'limitation|noun|B2', 'intermediate|adjective|C1', 'intimate|adjective|C1',
    'invoke|verb|C1', 'ironically|adverb|C1', 'just|adjective|C1',
    'kidney|noun|C1', 'labor|noun|B2', 'ladder|noun|B2', 'landlord|noun|C1',
    'landmark|noun|C1', 'legacy|noun|C1', 'legendary|adjective|C1', 'liable|adjective|C1',
    'liberation|noun|C1', 'line-up|noun|C1', 'linear|adjective|C1', 'listing|noun|C1',
    'liver|noun|C1', 'loom|verb|C1', 'lottery|noun|B2', 'majority|noun|B2',
    'manifest|verb|C1', 'manipulation|noun|C1', 'manuscript|noun|C1', 'marginal|adjective|C1',
    'marine|adjective|C1', 'maximize|verb|C1', 'mechanical|adjective|B2', 'mediate|verb|C2',
    'mere|adjective|C1', 'merge|verb|C1', 'migration|noun|C1', 'mill|noun|C1',
    'minimize|verb|C1', 'minute|adjective|C1', 'modest|adjective|B2', 'monopoly|noun|C1',
    'monthly|adjective|B2', 'morph|verb|UNCLASSIFIED'
]
print('=== Recently-fixed keys still in violations ===')
for k in recent_keys:
    if k in v:
        cur = mod.M3_VERDICTS.get(k)
        if cur:
            g, s, c, r = cur
            j = job_by_key.get(k)
            errs = validate_verdict(k.split('|')[0], g, s, c)
            print('  {}: gloss={!r}, validate={}'.format(k, g, errs))
        else:
            print('  {}: NOT IN DICT'.format(k))
    else:
        print('  {}: PASSED ✓'.format(k))