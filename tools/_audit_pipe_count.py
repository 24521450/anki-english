import json
from collections import Counter

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    merged = json.load(f)['verdicts']

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_verdicts.json', encoding='utf-8') as f:
    rerun = json.load(f)
if isinstance(rerun, dict) and 'verdicts' in rerun:
    rerun = rerun['verdicts']

rerun_hashes = {x.get('hash') for x in rerun}
kept = [x for x in merged if x.get('hash') not in rerun_hashes]

# Count `|` usage in kept
pipe_kept = [x for x in kept if '|' in (x.get('gloss') or '')]
print(f'KEPT 2-chunk (`|`): {len(pipe_kept)}')
for x in pipe_kept[:5]:
    print(f"  {x.get('word')}|{x.get('pos')}|{x.get('cefr')}: '{x.get('gloss')}'")

# Cross-check rerun's pipe usage
pipe_rerun = [x for x in rerun if '|' in (x.get('gloss') or '')]
print(f'\nRERUN 2-chunk (`|`): {len(pipe_rerun)} ({len(pipe_rerun)/len(rerun)*100:.1f}%)')

# So the total 2+ chunk in kept: pipe + semicolon
total_2c_kept = len(pipe_kept) + 20  # 20 from previous audit
print(f'\nKEPT 2+ chunks total: {total_2c_kept} ({total_2c_kept/len(kept)*100:.1f}%)')
print(f'  vs RERUN 2+ chunks: 526 ({526/len(rerun)*100:.1f}%)')
print(f'  Ratio: kept/rerun = {total_2c_kept/526*100:.1f}% of rerun\'s 2-chunk rate')

# More honest under-collapse estimate: rerun's 1-chunk rate is 40.8% (concrete_1sense + rule_b_pick1)
# If kept was selected to be "good 1-sense cases" but they all came from the same M3 session
# (pre-fix), then we can't trust the kept set. Even the 1-chunk ones might be under-collapsed.
#
# Conservative estimate: under-collapse = 1-chunk in kept that has 2+ senses in source def
# Cannot compute exactly without re-reading source defs for each card.
# Best estimate: take rerun's 1-chunk rate (40.8%) applied to kept's word/pos distribution
# This requires word/pos matching — out of scope for fast audit.

# Bottom line numbers to report in known_gaps.json:
print('\n=== NUMBERS FOR known_gaps.json ===')
print(f'  KEPT verdicts: {len(kept)}')
print(f'  Self-ref (gloss==word or word in chunk): 117 + 17 broader = 134')
print(f'  2-chunk `;` in kept: 20 (~14 likely Rule A violations per spot check)')
print(f'  2-chunk `|` in kept: {len(pipe_kept)}')
print(f'  1-chunk in kept: 1568 — UNKNOWN under-collapse rate, can be 0 to ~1000+')
print(f'  Conservative rule_a estimate: 14-100 (visible 2-chunk `;` + unknown 1-chunk under-collapse)')
print(f'  Generous rule_a+b estimate: 100-1500 if kept has same under-collapse issue as rerun had')
