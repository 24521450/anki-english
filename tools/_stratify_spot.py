"""Stratify the 100 spot-audit sample by multi-sense vs 1-sense.

Multi-sense = gloss has '|' or ';' separator (2+ chunks).
1-sense = single chunk (no separator).

Rule A only applies to multi-sense (where there's a 2+ chunk decision to make).
The 2% rate is the rate on ALL samples, not on multi-sense.
"""
import json
from collections import Counter

# Load spot_audit_100_results (the M3 reviews)
reviews = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/spot_audit_100_results.jsonl', encoding='utf-8')]

# Load the original sample for full context
samples = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/spot_audit_sample.jsonl', encoding='utf-8')]

# Map idx -> sample
sample_by_idx = {s['sample_idx']: s for s in samples}

# For each review, look up the gloss separator
multi_sense = []
one_sense = []
for r in reviews:
    s = sample_by_idx.get(r['idx'], {})
    gloss = r.get('gloss', '')
    sep = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
    if sep in ('|', ';'):
        multi_sense.append(r)
    else:
        one_sense.append(r)

print(f'Total: {len(reviews)}')
print(f'  1-sense (sep=none): {len(one_sense)}')
print(f'  multi-sense (sep in |,;): {len(multi_sense)}')

# Stats for each
def stats(group, label):
    n = len(group)
    n_pass = sum(1 for r in group if r['decision'] == 'pass')
    n_replace = sum(1 for r in group if r['decision'] == 'replace')
    rate = n_replace / n * 100 if n else 0
    print(f'\n  {label}: {n} samples')
    print(f'    pass: {n_pass}')
    print(f'    replace: {n_replace}')
    print(f'    rate: {rate:.1f}%')
    if n_replace:
        print(f'    violations:')
        for r in group:
            if r['decision'] == 'replace':
                print(f"      [{r['idx']}] {r['word']} ({r['pos']}, {r['cefr']}): {r['gloss']!r} -> {r.get('new_gloss')!r}")

stats(one_sense, '1-SENSE (Rule A NOT applicable)')
stats(multi_sense, 'MULTI-SENSE (Rule A applicable)')

# Categorize the 2 violations
print(f'\n=== Violation categories ===')
for r in reviews:
    if r['decision'] == 'replace':
        gloss = r['gloss']
        reason = r['reason']
        if 'RULE A' in reason.upper() or 'NEAR-SYNONYM' in reason.upper():
            cat = 'rule_a_violation'
        elif 'TOO STRONG' in reason.upper() or 'TONE' in reason.upper() or 'STRENGTH' in reason.upper():
            cat = 'tone_accuracy_issue'
        else:
            cat = 'other'
        print(f"  [{r['idx']}] {r['word']}: {cat}")
        print(f"    reason: {reason}")
