"""Audit: find all entries in M3_VERDICTS that have headword_in_chunk[0] violation
(meaning my fix didn't take)."""
import importlib.util
import json

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

v = json.load(open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_violations.json', encoding='utf-8'))

# For each violation key, show current dict value
print('=== headword_in_chunk[0] violations still failing ===')
count = 0
for k in sorted(v.keys()):
    errs = v[k]
    if not any('headword_in_chunk[0]' in e for e in errs):
        continue
    cur = mod.M3_VERDICTS.get(k)
    if cur:
        g = cur[0]
        print('  {}: gloss={!r}'.format(k, g))
        count += 1
print()
print('Total: {}'.format(count))