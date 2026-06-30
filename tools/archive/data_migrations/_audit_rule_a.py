import json
from collections import Counter

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    merged = json.load(f)['verdicts']

with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_rerun_verdicts.json', encoding='utf-8') as f:
    rerun = json.load(f)
if isinstance(rerun, dict) and 'verdicts' in rerun:
    rerun = rerun['verdicts']

# Distribution of 2-chunk (`;`) in rerun vs kept
def has_2chunk_semicolon(x):
    gloss = (x.get('gloss') or '').strip()
    if not gloss or gloss.lower() == 'no-gloss':
        return False
    return ';' in gloss

rerun_2c = sum(1 for x in rerun if has_2chunk_semicolon(x))
kept_2c = sum(1 for x in merged if x.get('hash') not in {x.get('hash') for x in rerun} and has_2chunk_semicolon(x))
print(f'rerun: {len(rerun)} verdicts, {rerun_2c} 2-chunk (semicolon) = {rerun_2c/len(rerun)*100:.1f}%')
print(f'kept: {1588} verdicts, {kept_2c} 2-chunk (semicolon) = {kept_2c/1588*100:.1f}%')

# Cross-check: 200-batch pilot rate of 6-10% on the kept
# 1588 × 6-10% = 95-159 estimated Rule A violations
# But only kept_2c=20 are 2-chunk (`;`) — so the 6-10% must be measuring
# different things, or the kept set has Rule A issues in 1-chunk forms too

# Look at 1-chunk kept that might be Rule B violations (3+ senses that M3 collapsed wrong)
# Not easily detectable without original defs. Just note the limitation.

# Show rule_applied distribution in kept
rule_dist = Counter(x.get('rule_applied') for x in merged if x.get('hash') not in {x.get('hash') for x in rerun})
print(f'\nKept rule_applied dist: {dict(rule_dist)}')

# Look at 1-chunk kept where the headword has form "...something" — could be "adverb form"
# rule_applied=0 or '' (empty) means M3 didn't tag a rule
no_rule = sum(1 for x in merged if x.get('hash') not in {x.get('hash') for x in rerun} and not x.get('rule_applied'))
print(f'Kept with no rule_applied: {no_rule}')

# Likely Rule A in 1-chunk form: M3 collapsed 2 near-synonyms into 1 word, that's OK
# Rule A violation in 1-chunk: M3 picked a 1-word gloss that doesn't cover either sense well
# — undetectable without re-reading defs
