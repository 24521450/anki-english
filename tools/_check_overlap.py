"""Check overlap between 98 spot-audit sample and 17 reclassified cards.
This affects the P3 extrapolation: if any of the 17 were in the 98 sample,
the denominator for "~14 issues in 1,439" should be adjusted."""
import json

# Load spot sample
spot = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/spot_audit_sample.jsonl', encoding='utf-8')]
spot_keys = set((s['word'], s['pos'], s['cefr']) for s in spot)
print(f'Spot sample: {len(spot)} cards ({len(spot_keys)} unique keys)')

# Load 17 reclassified cards
reclassified = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_hidden_leaks_remaining_17.json', encoding='utf-8')]
reclassified_keys = set((h['word'], h['pos'], h['cefr']) for h in reclassified)
print(f'Reclassified (17): {len(reclassified)} cards')

# Overlap
overlap = spot_keys & reclassified_keys
print(f'\nOverlap: {len(overlap)} cards')
if overlap:
    for k in sorted(overlap):
        print(f'  {k}')

# Implication
n_spot_clean = len(spot_keys) - len(overlap)
print(f'\nImplication:')
print(f'  Spot sample clean for tone/accuracy: {n_spot_clean} (was 98, minus overlap)')
print(f'  Rate: 1 violation / {n_spot_clean} samples')
print(f'  Extrapolation to 1,439 1-sense: {1,439 * 1 / n_spot_clean:.1f} issues (was ~14)')

# But wait: reclassified cards are TYPE_2/3 (hidden leak), not tone/accuracy
# The spot sample had 1 tone/accuracy issue (trigger). The 17 reclassified are different category.
# So the overlap doesn't directly affect tone/accuracy extrapolation, but it does affect
# the "1,470 -> 1,439" denominator claim.

print(f'\nNote: 17 reclassified are HIDDEN LEAK (different category from tone/accuracy)')
print(f'  So the 1 tone/accuracy in spot sample is still valid; denominator unchanged')
print(f'  But the ~14 estimate uses (1,470 - 31 already-fixed) = 1,439, which is the 1-sense unverified count')
print(f'  Check: 1-sense unverified after reclassify: ', end='')
# Load full audit, count 1-sense unverified
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]
one_sense_unverified = [r for r in records if r['gate_status'] == 'unverified_rule_a' and r.get('separator') in (None, 'none')]
print(f'{len(one_sense_unverified)}')
