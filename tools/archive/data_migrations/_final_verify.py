"""Verify final state and add overlap note for P3."""
import json
from collections import Counter

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Stratify current unverified
unverified = [r for r in records if r['gate_status'] == 'unverified_rule_a']
multi = [r for r in unverified if r.get('separator') in ('|', ';')]
one = [r for r in unverified if r.get('separator') in (None, 'none')]
print(f'Current unverified_rule_a: {len(unverified)}')
print(f'  multi-sense: {len(multi)}')
print(f'  1-sense: {len(one)}')

# Spot sample
spot = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/spot_audit_sample.jsonl', encoding='utf-8')]
spot_keys = set((s['word'], s['pos'], s['cefr']) for s in spot)
print(f'\nSpot sample: {len(spot)} cards')

# Reclassified 17
reclassified = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_hidden_leaks_remaining_17.json', encoding='utf-8')]
reclassified_keys = set((h['word'], h['pos'], h['cefr']) for h in reclassified)

# Overlap
overlap = spot_keys & reclassified_keys
print(f'Overlap (spot ∩ reclassified): {len(overlap)}')
for k in sorted(overlap):
    print(f'  {k}')

# Spot sample broken down
spot_pass = [s for s in spot if s['gate_status'] == 'pass']
spot_known_leak = [s for s in spot if s['gate_status'] == 'known_leak_unfixed']
spot_unverified = [s for s in spot if s['gate_status'] == 'unverified_rule_a']
spot_skip = [s for s in spot if s['gate_status'] == 'skip_fallback']
print(f'\nSpot sample (n=100) by current status:')
print(f'  pass: {len(spot_pass)}')
print(f'  unverified_rule_a: {len(spot_unverified)}')
print(f'  skip_fallback: {len(spot_skip)}')
print(f'  known_leak_unfixed: {len(spot_known_leak)}')

# Tone/accuracy: 1 violation in 100 spot
# But the 100 spot has 1 reclassified (gender) — different category
# So tone/accuracy rate is 1/100 = 1% (unaffected by reclassify)

# But for P3 extrapolation to 1,446 1-sense unverified (current), the rate of 1% implies ~14 issues
# However, the spot was taken from 1,470 pre-fix unverified. Of those, 1 (gender) was reclassified.
# The 1 reclassified is in 1-sense (gender is 1-sense). It wasn't a tone/accuracy issue (it was a hidden leak).
# So the 1% rate is still valid; just the denominator changes.

# What was the spot sample's effective denominator for tone/accuracy?
# The spot had 1 tone/accuracy violation (trigger) and 99 non-violations
# Of the 99 non-violations, 1 was reclassified (gender) but gender was a hidden leak, not tone
# So the tone/accuracy count is still 1 violation in 100 samples = 1%
# The relevant 1-sense denominator was originally 1,451 (pre-fix) or 1,446 (post-fix)
# 1% of 1,446 = ~14 issues (vs 1% of 1,451 = ~14.5 issues — same)
# No significant change.

print(f'\n=== P3 denominator analysis ===')
print(f'Pre-fix 1-sense unverified: ~1,451')
print(f'Post-fix 1-sense unverified: ~{len(one)}')
print(f'Spot sample: 100 cards, 1 tone/accuracy violation')
print(f'Rate: 1%')
print(f'Extrapolation to post-fix 1,446: {1446 * 0.01:.1f} issues')
print(f'Extrapolation to pre-fix 1,451: {1451 * 0.01:.1f} issues')
print(f'Note: 1 overlap (gender) was in spot AND reclassified (hidden_leak, NOT tone)')
print(f'  => gender being reclassified does not affect tone/accuracy rate estimate')
