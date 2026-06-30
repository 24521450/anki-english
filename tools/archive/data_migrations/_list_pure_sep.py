"""Dump 14 pure-sep entries with their current dict values."""
import importlib.util
import json

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

v = json.load(open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_violations.json', encoding='utf-8'))

print('=== 14 pure-sep entries (current vs fixed) ===')
print()
for key, errs in v.items():
    cats = set(e.split(':', 1)[0].split('[')[0] for e in errs)
    if cats != {'separator_mismatch'}:
        continue
    if key not in mod.M3_VERDICTS:
        print('  {}: NOT IN DICT'.format(key))
        continue
    gloss, sep, count, rule = mod.M3_VERDICTS[key]
    # Decide what sep SHOULD be
    actual_sep = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
    print('  {}: declared={}, actual={}, gloss={!r}'.format(key, sep, actual_sep, gloss))
    print('    current rule: {}'.format(rule))