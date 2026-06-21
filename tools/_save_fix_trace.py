"""Save fix trace as proper table — replaces the vague '3 fixed' narrative."""
import json
from collections import Counter

verdicts = json.load(open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8'))['verdicts']
records = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/audit_full_deck.jsonl', encoding='utf-8')]

audit_by_key = {}
for r in records:
    audit_by_key[(r['word'], r['pos'], r['cefr'])] = r

# Build trace
trace = []
for v in verdicts:
    r = v.get('reasoning', '').strip()
    if not (r.startswith('RULE A fix:') or r.startswith('HIDDEN SELF-REF fix:') or r.startswith('GLOSS TOO STRONG')):
        continue
    if r.startswith('RULE A fix:'):
        issue = 'rule_a'
    elif r.startswith('HIDDEN SELF-REF fix:'):
        issue = 'hidden_leak'
    elif r.startswith('GLOSS TOO STRONG'):
        issue = 'tone_accuracy'
    else:
        issue = 'unknown'
    key = (v['word'], v['pos'], v['cefr'])
    audit = audit_by_key.get(key, {})
    trace.append({
        'word': v['word'],
        'pos': v['pos'],
        'cefr': v['cefr'],
        'issue_type': issue,
        'new_gloss': v['gloss'],
        'old_gloss': '',  # can be recovered from reasoning
        'current_bucket': audit.get('gate_status', 'unknown'),
        'reasoning': r,
    })

# Sort by issue_type then word
trace.sort(key=lambda t: (t['issue_type'], t['word']))

# Save
out_path = r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/fix_trace_20260618.jsonl'
with open(out_path, 'w', encoding='utf-8') as f:
    for t in trace:
        f.write(json.dumps(t, ensure_ascii=False) + '\n')
print(f'Saved {len(trace)} fixes to {out_path}')

# Print as a clean table
print('\n=== Fix trace (all 24 fixes) ===')
print(f'{"word":15s} | {"pos":10s} | {"cefr":5s} | {"issue_type":15s} | {"current_bucket":20s}')
print('-' * 80)
for t in trace:
    word = t['word']
    pos = t['pos']
    cefr = t['cefr']
    issue = t['issue_type']
    cur = t['current_bucket']
    print(f"{word:15s} | {pos:10s} | {cefr:5s} | {issue:15s} | {cur:20s}")

# Counts
print()
issue_count = Counter(t['issue_type'] for t in trace)
print(f'By issue_type: {dict(issue_count)}')
cur_count = Counter(t['current_bucket'] for t in trace)
print(f'By current_bucket: {dict(cur_count)}')
