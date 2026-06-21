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

# Re-do chunk detection properly
def chunk_count(x):
    gloss = (x.get('gloss') or '').strip()
    if not gloss or gloss.lower() == 'no-gloss':
        return 0
    # Split on both | and ;
    chunks = [c.strip() for c in gloss.replace('|', ';').split(';') if c.strip()]
    return len(chunks)

rerun_cc = Counter(chunk_count(x) for x in rerun)
kept_cc = Counter(chunk_count(x) for x in kept)

print('RERUN chunk count distribution (post-fix, 889):')
for k in sorted(rerun_cc.keys()):
    print(f'  {k} chunks: {rerun_cc[k]} ({rerun_cc[k]/len(rerun)*100:.1f}%)')
print(f'  2+ chunks: {sum(v for k,v in rerun_cc.items() if k >= 2)} ({sum(v for k,v in rerun_cc.items() if k >= 2)/len(rerun)*100:.1f}%)')

print()
print('KEPT chunk count distribution (pre-fix, 1588):')
for k in sorted(kept_cc.keys()):
    print(f'  {k} chunks: {kept_cc[k]} ({kept_cc[k]/len(kept)*100:.1f}%)')
print(f'  2+ chunks: {sum(v for k,v in kept_cc.items() if k >= 2)} ({sum(v for k,v in kept_cc.items() if k >= 2)/len(kept)*100:.1f}%)')

# Naive under-collapse estimate: if kept should have 2+ chunks at same rate as rerun (47.1%),
# then expected_undercollapsed = kept_total * rerun_2chunk_rate - kept_actual_2chunk
expected_2plus = int(len(kept) * 0.471)
actual_2plus = sum(v for k,v in kept_cc.items() if k >= 2)
print(f'\nUnder-collapse estimate:')
print(f'  If kept had rerun-like 47.1% 2+ chunk rate, would expect {expected_2plus} 2+ chunk verdicts')
print(f'  Actually have {actual_2plus} 2+ chunk verdicts')
print(f'  -> Up to {expected_2plus - actual_2plus} verdicts MAY be under-collapsed (1-chunk that should be 2)')

# CAVEAT: kept and rerun are not directly comparable. Rerun was selected for cases that
# failed the original structural check (multi-sense-3+ + rule violations). Kept was the
# "good" cases. So kept should have LOWER 2+ chunk rate than rerun by design.

# Better estimate: compare to the "concrete_1sense" rule (55/889) — these are explicitly
# 1-sense cases. Apply that ratio to kept: if kept is ~55/889 = 6.2% 1-sense, then
# 1,588 × 6.2% = 98 1-sense verdicts expected. Actual 1-chunk in kept = ?
actual_1chunk = sum(v for k,v in kept_cc.items() if k == 1)
print(f'\nCross-check:')
print(f'  Kept 1-chunk: {actual_1chunk} ({actual_1chunk/len(kept)*100:.1f}%)')
print(f'  Rerun "concrete_1sense" rate: 6.2%')
print(f'  If kept matched, expected 1-chunk: {int(0.062*len(kept))}')
