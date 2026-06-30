"""Pick 100 random unverified_rule_a records for spot-audit."""
import json
import random
import hashlib

# Load all audit records
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Filter to unverified_rule_a
unverified = [r for r in records if r['gate_status'] == 'unverified_rule_a']
print(f'Total unverified_rule_a: {len(unverified)}')

# Seed for reproducibility
random.seed(20260618)
sample = random.sample(unverified, 100)
sample.sort(key=lambda r: (r['word'], r['pos'], r['cefr']))

# Save sample with index for tracking
sample_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff/spot_audit_sample.jsonl'
with open(sample_path, 'w', encoding='utf-8') as f:
    for i, r in enumerate(sample):
        r['sample_idx'] = i
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print(f'Saved 100 samples to {sample_path}')

# Stats: how many have separator, single chunk, etc.
from collections import Counter
sep_dist = Counter(r.get('separator') for r in sample)
print(f'\nSeparator dist: {dict(sep_dist)}')

# Show first 5 for M3 review context
print('\n=== First 5 samples ===')
for r in sample[:5]:
    print(f"\n[{r['sample_idx']}] {r['word']} ({r['pos']}, {r['cefr']})")
    print(f"    def_before: {r['def_before'][:100]}")
    print(f"    gloss_after: {r['gloss_after']!r} [sep={r.get('separator')}, rule={r.get('rule_applied')}]")
