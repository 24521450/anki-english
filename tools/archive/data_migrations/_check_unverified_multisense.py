"""Compute multi-sense vs 1-sense distribution in unverified_rule_a set."""
import json
from collections import Counter

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]
unverified = [r for r in records if r['gate_status'] == 'unverified_rule_a']
print(f'Total unverified_rule_a: {len(unverified)}')

# Categorize
multi = [r for r in unverified if r.get('separator') in ('|', ';')]
one = [r for r in unverified if r.get('separator') in (None, 'none')]
print(f'  1-sense (sep=none/None): {len(one)}')
print(f'  multi-sense (sep in |,;): {len(multi)}')
print(f'  multi-sense rate: {len(multi)/len(unverified)*100:.1f}%')

# Show multi-sense cards
print(f'\n=== Multi-sense cards ({len(multi)}) ===')
for r in multi:
    print(f"  {r['word']:35s} | {r['pos']:10s} | {r['cefr']:13s} | gloss={r['gloss_after']!r} [sep={r.get('separator')}]")
