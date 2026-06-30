"""Save fix trace + update P3 caveat."""
import json
from collections import Counter

# Build fix trace table
# Each fixed card: word, original_bucket, issue_type, final_bucket, fix_method

records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

# Identify cards that have reasoning starting with fix markers
# (these were fixed in this session)
verdicts = json.load(open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8'))['verdicts']
fixed_verdicts = [v for v in verdicts if v.get('reasoning', '').strip().startswith(('RULE A fix:', 'HIDDEN SELF-REF fix:', 'GLOSS TOO STRONG fix:'))]

# For each fixed verdict, determine original bucket
# original bucket = bucket before fix
# current bucket = bucket in current audit

# We need historical data: what bucket was each card in before fix?
# Approximate: use the original_100pct / rerun_v2_streamA / streamD source
# The apply's gate check on the OLD gloss would have been:
# - If OLD gloss was exact self-ref, the verdict would have been skip_fallback
# - If OLD gloss was in 'pass' (rerun or streamD with valid old gloss), then it was 'pass'
# - If OLD gloss was in 'unverified_rule_a' (kept with valid old gloss), then it was 'unverified'

# For hidden leak fixes: the OLD gloss had headword in chunk. The gate would NOT catch it.
# So the card was in 'pass' (for rerun) or 'unverified_rule_a' (for kept).
# For the 12 hidden fixes I did: source=original_100pct (kept pre-fix), so all 12 were in unverified_rule_a.
# For the 10 multi-sense fixes: also kept pre-fix, so all 10 were in unverified_rule_a.
# For the 1 tone fix (trigger): also kept pre-fix, in unverified_rule_a.

# So all 23 fixes I did were originally in unverified_rule_a (the kept pre-fix set).
# After fix: 23 moved to 'pass' (since they have reasoning now and no hidden leak).

# But wait, my earlier claim was "3 fixed vẫn ở pass". Let me re-verify.

# Let me check the audit BEFORE this session's final reclassify to see bucket distribution

# Actually, the audit was rebuilt multiple times. Let me just check the current state of all 23 fixed cards
# and figure out what their CURRENT bucket is.

audit_by_key = {}
for r in records:
    audit_by_key[(r['word'], r['pos'], r['cefr'])] = r

trace = []
for v in fixed_verdicts:
    key = (v['word'], v['pos'], v['cefr'])
    r = audit_by_key.get(key, {})
    reasoning = v.get('reasoning', '')
    if reasoning.startswith('RULE A fix:'):
        issue = 'rule_a'
    elif reasoning.startswith('HIDDEN SELF-REF fix:'):
        issue = 'hidden_leak'
    elif reasoning.startswith('GLOSS TOO STRONG fix:'):
        issue = 'tone_accuracy'
    else:
        issue = 'unknown'
    trace.append({
        'word': v['word'],
        'pos': v['pos'],
        'cefr': v['cefr'],
        'issue_type': issue,
        'old_gloss': '',  # need to recover
        'new_gloss': v['gloss'],
        'source_in_verdicts': v.get('source', 'unknown'),  # may not be set
        'current_bucket': r.get('gate_status'),
        'reasoning': reasoning,
    })

# Build a more detailed trace by checking what bucket the OLD gloss would have been in
# For hidden_leak fixes: the OLD gloss contained headword in chunk. The gate would not catch this.
# So bucket depends on source:
# - If source was kept (original_100pct) AND gate passed, bucket was 'unverified_rule_a' (if no manual fix marker)
# - If source was rerun, bucket was 'pass'

# But I need to check: in the audit logic, the bucket decision is:
# 1. If not is_applied: skip_fallback
# 2. elif has_hidden_leak: known_leak_unfixed (post-fix; pre-fix this didn't exist)
# 3. elif source==original_100pct AND has reasoning: pass
# 4. elif source==original_100pct: unverified_rule_a
# 5. else: pass

# So pre-fix, hidden_leak cards in 'pass' were 'pass' because:
# - is_applied was True (txt had the new gloss)
# - has_hidden_leak was NOT checked (it was added later)
# - source was original_100pct OR rerun_v2_streamA OR streamD

# For my 12 hidden_leak fixes:
# - bat, hook, jet, punk, radar, reporting, slam, monthly, stark, rip, firework, tackle
# - All had source=original_100pct
# - Pre-fix: bucket was 'unverified_rule_a' (no reasoning, source=original)
# - After fix: bucket becomes 'pass' (has reasoning)

# For 10 multi-sense fixes:
# - aesthetic, assemble, closure, depict, interval, legitimate, precious, provoke, seeker, variation
# - All had source=original_100pct
# - Pre-fix: bucket was 'unverified_rule_a'
# - After fix: bucket becomes 'pass'

# For 1 tone fix (trigger):
# - source=original_100pct
# - Pre-fix: unverified_rule_a
# - After fix: pass

# So all 23 fixes: original_bucket = unverified_rule_a, new_bucket = pass

# Now let me verify the bucket math from the user:
# 1,470 (unverified pre-fix) - 10 multi-sense - 9 hidden-leak - 1 tone = 1,450 → close to 1,445 (off by 5)
# Wait, my multi-sense fixes were 10, but in the bucket math I calculated only 19 moves total.
# Let me recheck.

# 10 multi-sense + 12 hidden + 1 tone = 23 fixes
# But bucket math showed: 1,470 - 1,451 = 19 moves
# So only 19 actually moved bucket, not 23. Why?

# Some fixes were in 'unverified_rule_a' (no reasoning) and after fix, became 'pass' (has reasoning).
# Others might have been in 'pass' (e.g. trigger was in unverified pre-fix because kept; but closure was in pass because of source=original_100pct + reasoning="RULE A fix" already set?)

# Actually wait, closure was in pass because it had a hidden_leak "permanent closure; temporary closing" (2 chunks, headword in first chunk). Pre-fix audit logic didn't check hidden_leak, so closure was 'pass' (source=original_100pct, no reasoning, no other check). After fix, closure is 'pass' (source=original_100pct, has reasoning).

# Hmm, that contradicts my earlier claim. Let me actually compute the original bucket by looking at the issue type:

# For hidden_leak fixes:
#   - closure (C1): was 'pass' (source=original_100pct, no reasoning pre-fix, no hidden_leak check pre-fix)
#   - 11 others (bat, hook, jet, ...): all were 'unverified_rule_a' (single-chunk gloss, no hidden_leak possible, source=original_100pct)

# Wait no, hidden_leak requires multi-word chunk. The 12 fixed: 11 are 2-word chunks, 1 is 3-word (slam shut, monthly fee, etc.).
# Pre-fix audit logic: for source=original_100pct, bucket is 'unverified_rule_a' (no reasoning pre-fix).
# So all 12 were 'unverified_rule_a' pre-fix.
# After fix: bucket is 'pass' (has reasoning).
# So 12 moved unverified → pass.

# But 1 of those 12 (closure) was also in the multi-sense review (closure was in the 19 multi-sense cards).
# Multi-sense review fixed 10 cards, all moved unverified → pass.
# So total moves: 10 multi-sense + 12 hidden + 1 tone = 23 moves.

# But bucket math showed 19 moves. Where are the 4 missing?

# Oh, some hidden_leak fixes might have ALREADY been in 'pass' because they were in rerun (not kept).
# Let me check: which of the 12 hidden_leak fixes had source != original_100pct?

# I'll check by looking at the verdicts file

# Print the trace
print('=== Fix trace ===')
for t in trace:
    word = t['word']
    pos = t['pos']
    cefr = t['cefr']
    issue = t['issue_type']
    cur_bucket = t['current_bucket']
    reasoning = t['reasoning']
    print(f"  {word:15s} | {pos:10s} | {cefr:5s} | {issue:15s} | now={cur_bucket:20s} | {reasoning}")
