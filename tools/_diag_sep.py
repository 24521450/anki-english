"""Investigate separator_mismatch violations."""
import json
import re
from collections import Counter

v = json.load(open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_violations.json', encoding='utf-8'))
sep_mis = [(k, err) for k, errs in v.items() for err in errs if err.startswith('separator_mismatch')]
print('Total separator_mismatch: {}'.format(len(sep_mis)))

# Direction of mismatch
directions = Counter()
for k, err in sep_mis:
    m = re.search(r"declared='([^']+)', actual='([^']+)'", err)
    if m:
        directions[(m.group(1), m.group(2))] += 1
print('\nDirection (declared -> actual):')
for d, c in directions.most_common():
    print('  {} -> {}: {}'.format(d[0], d[1], c))

print('\nSample cases:')
for k, err in sep_mis[:15]:
    print('  {}: {}'.format(k, err))