"""Check overlap between sep_mismatch and other violation categories."""
import json
from collections import Counter

v = json.load(open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_violations.json', encoding='utf-8'))

# Categorize each key's violations
only_sep = []
only_count = []
sep_with_other = []
no_sep_at_all = []
all_categories = Counter()

for key, errs in v.items():
    cats = set()
    for e in errs:
        cat = e.split(':', 1)[0].split('[')[0]
        cats.add(cat)
        all_categories[cat] += 1
    has_sep = 'separator_mismatch' in cats
    has_count = 'count_mismatch' in cats
    if has_sep and cats == {'separator_mismatch'}:
        only_sep.append(key)
    elif has_count and cats == {'count_mismatch'}:
        only_count.append(key)
    elif has_sep or has_count:
        sep_with_other.append(key)
    else:
        no_sep_at_all.append(key)

print('=== OVERLAP ANALYSIS ===')
print('only_sep_mismatch: {}'.format(len(only_sep)))
print('only_count_mismatch: {}'.format(len(only_count)))
print('sep_or_count WITH other violations: {}'.format(len(sep_with_other)))
print('no sep/count at all: {}'.format(len(no_sep_at_all)))
print()
print('=== All violation categories ===')
for k, c in all_categories.most_common():
    print('  {}: {}'.format(k, c))
print()
print('=== Sample pure_sep entries ===')
for k in only_sep[:10]:
    print('  {}'.format(k))

# Also: how many total unique keys need regen (= bucket size for Stream A)
total_unique = len(v)
print()
print('=== Stream A scope ===')
print('Total unique keys with violations: {}'.format(total_unique))