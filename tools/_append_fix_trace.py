"""Append the 16 known-leak fixes to the fix trace."""
import json

path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\fix_trace_20260618.jsonl'
with open(path, encoding='utf-8') as f:
    existing = [json.loads(l) for l in f]

new_fixes = [
    # Surgical 1-chunk replaces
    {'word': 'adoption', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'adopt a child; acceptance', 'old_gloss': 'child adoption; acceptance',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: child adoption; acceptance -> adopt a child; acceptance'},
    {'word': 'balloon', 'pos': 'noun', 'cefr': 'B2', 'issue_type': 'hidden_leak',
     'new_gloss': 'rubber bag; rising hot-air craft', 'old_gloss': 'rubber bag; hot-air balloon',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: rubber bag; hot-air balloon -> rubber bag; rising hot-air craft'},
    {'word': 'bass', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'low pitch; low-note guitar', 'old_gloss': 'low pitch; bass guitar',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: low pitch; bass guitar -> low pitch; low-note guitar'},
    {'word': 'blade', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'cutting edge; rotating flat part', 'old_gloss': 'cutting edge; propeller blade',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: cutting edge; propeller blade -> cutting edge; rotating flat part'},
    {'word': 'boom', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'rapid growth; sudden popularity', 'old_gloss': 'economic boom; sudden popularity',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: economic boom; sudden popularity -> rapid growth; sudden popularity'},
    {'word': 'canvas', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'cloth material; painting surface', 'old_gloss': 'cloth material; painting on canvas',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: cloth material; painting on canvas -> cloth material; painting surface'},
    {'word': 'cutting', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'article clipping | plant offshoot', 'old_gloss': 'article clipping | plant cutting',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: article clipping | plant cutting -> article clipping | plant offshoot'},
    {'word': 'deployment', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'troop positioning', 'old_gloss': 'military deployment',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: military deployment -> troop positioning'},
    {'word': 'gender', 'pos': 'noun', 'cefr': 'B2', 'issue_type': 'hidden_leak',
     'new_gloss': 'social sex role', 'old_gloss': 'gender identity',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: gender identity -> social sex role'},
    {'word': 'horn', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'animal protrusion | warning device', 'old_gloss': 'animal protrusion | car horn',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: animal protrusion | car horn -> animal protrusion | warning device'},
    {'word': 'slot', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'opening; scheduled time', 'old_gloss': 'opening; time slot',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: opening; time slot -> opening; scheduled time'},
    {'word': 'snap', 'pos': 'verb', 'cefr': 'C1', 'issue_type': 'hidden_leak',
     'new_gloss': 'break; take photo', 'old_gloss': 'break; snap photo',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: break; snap photo -> break; take photo'},
    {'word': 'stall', 'pos': 'noun', 'cefr': 'B2', 'issue_type': 'hidden_leak',
     'new_gloss': 'vendor booth', 'old_gloss': 'market stall',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: market stall -> vendor booth'},
    {'word': 'thumb', 'pos': 'noun', 'cefr': 'B2', 'issue_type': 'hidden_leak',
     'new_gloss': 'finger; glove covering', 'old_gloss': 'finger; thumb piece',
     'current_bucket': 'pass', 'reasoning': 'HIDDEN SELF-REF fix: finger; thumb piece -> finger; glove covering'},
    # No-gloss
    {'word': 'behalf', 'pos': 'noun', 'cefr': 'C1', 'issue_type': 'no_gloss_phrase',
     'new_gloss': '', 'old_gloss': 'on behalf of',
     'current_bucket': 'skip_fallback', 'reasoning': 'NO-GLOSS: phrase-only, headword unavoidable (on behalf of)'},
    {'word': 'meantime', 'pos': 'adverb', 'cefr': 'C1', 'issue_type': 'no_gloss_phrase',
     'new_gloss': '', 'old_gloss': 'in the meantime',
     'current_bucket': 'skip_fallback', 'reasoning': 'NO-GLOSS: phrase-only, headword unavoidable (in the meantime)'},
]

# Append
with open(path, 'w', encoding='utf-8') as f:
    for fix in existing:
        f.write(json.dumps(fix, ensure_ascii=False) + '\n')
    for fix in new_fixes:
        f.write(json.dumps(fix, ensure_ascii=False) + '\n')

print(f'Appended {len(new_fixes)} fixes. Total: {len(existing) + len(new_fixes)}')
