"""Fix 16 cards in known_leak_unfixed bucket (pace excluded as separate task).

Surgical 1-chunk replacement for 14 cards; no-gloss for 2 (behalf, meantime).
All 14 rewrites get reasoning="HIDDEN SELF-REF fix: ..." for audit consistency.

Approach: load gloss_all_verdicts.json, locate each card by (word, pos, cefr),
update gloss or set decision=no-gloss, validate via gate, write back.
"""
import json
import hashlib
import shutil
import sys

PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'
VERDICTS_PATH = f'{PROJECT_ROOT}/data/simplify_diff/gloss_all_verdicts.json'
BACKUP_PATH = f'{VERDICTS_PATH}.bak_pre_known_leak_fix_20260618'

# Surgical 1-chunk replacements: (word, pos, cefr, old_gloss, new_gloss, sep)
# old_gloss is the full current gloss; new_gloss is the surgically-replaced version
# sep is unchanged from the verdict
SURGICAL_FIXES = [
    # 4 cards source=original_100pct: need reasoning to classify as pass
    ('blade', 'noun', 'C1', 'cutting edge; propeller blade', 'cutting edge; rotating flat part', ';', 'original_100pct'),
    ('deployment', 'noun', 'C1', 'military deployment', 'troop positioning', 'none', 'original_100pct'),
    ('gender', 'noun', 'B2', 'gender identity', 'social sex role', 'none', 'original_100pct'),
    ('stall', 'noun', 'B2', 'market stall', 'vendor booth', 'none', 'original_100pct'),
    # 10 cards source=rerun_v2_streamA: reasoning still added for audit consistency
    ('adoption', 'noun', 'C1', 'child adoption; acceptance', 'adopt a child; acceptance', ';', 'rerun_v2_streamA'),
    ('balloon', 'noun', 'B2', 'rubber bag; hot-air balloon', 'rubber bag; rising hot-air craft', ';', 'rerun_v2_streamA'),
    ('bass', 'noun', 'C1', 'low pitch; bass guitar', 'low pitch; low-note guitar', ';', 'rerun_v2_streamA'),
    ('boom', 'noun', 'C1', 'economic boom; sudden popularity', 'rapid growth; sudden popularity', ';', 'rerun_v2_streamA'),
    ('canvas', 'noun', 'C1', 'cloth material; painting on canvas', 'cloth material; painting surface', ';', 'rerun_v2_streamA'),
    ('cutting', 'noun', 'C1', 'article clipping | plant cutting', 'article clipping | plant offshoot', '|', 'rerun_v2_streamA'),
    ('horn', 'noun', 'C1', 'animal protrusion | car horn', 'animal protrusion | warning device', '|', 'rerun_v2_streamA'),
    ('slot', 'noun', 'C1', 'opening; time slot', 'opening; scheduled time', ';', 'rerun_v2_streamA'),
    ('snap', 'verb', 'C1', 'break; snap photo', 'break; take photo', ';', 'rerun_v2_streamA'),
    ('thumb', 'noun', 'B2', 'finger; thumb piece', 'finger; glove covering', ';', 'rerun_v2_streamA'),
]

# No-gloss decisions: (word, pos, cefr, expected_old_gloss)
NO_GLOSS = [
    ('behalf', 'noun', 'C1', 'on behalf of'),
    ('meantime', 'adverb', 'C1', 'in the meantime'),
]

# Load gate module for validation
sys.path.insert(0, PROJECT_ROOT)
import importlib.util as u
spec = u.spec_from_file_location('gloss_llm', f'{PROJECT_ROOT}/src/deck_builder/gloss_llm.py')
mod = u.module_from_spec(spec)
sys.modules['gloss_llm'] = mod
spec.loader.exec_module(mod)

# Helper: has_hidden_leak check (headword in multi-word chunk)
def has_hidden_leak(word, gloss):
    if not word or not gloss:
        return False
    word_lower = word.lower().strip()
    gloss_lower = gloss.lower()
    chunks = [c.strip() for c in gloss_lower.replace('|', ';').split(';') if c.strip()]
    if any(c == word_lower for c in chunks):
        return False
    for c in chunks:
        words = c.split()
        if len(words) > 1 and word_lower in words:
            return True
    return False

# Load verdicts
with open(VERDICTS_PATH, encoding='utf-8') as f:
    data = json.load(f)
all_v = data['verdicts']

# Load txt for def lookup (for hash recompute)
with open(f'{PROJECT_ROOT}/English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')
txt_defs = {}
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) < 15:
        continue
    txt_defs[(p[3].strip(), p[4].strip(), p[14].strip() or 'UNCLASSIFIED')] = p[6] if len(p) > 6 else ''

# Backup
shutil.copy(VERDICTS_PATH, BACKUP_PATH)
print(f'Backup: {BACKUP_PATH}')

# Apply surgical fixes
surgical_applied = 0
surgical_skipped = 0
surgical_violations = []

for word, pos, cefr, old_gloss, new_gloss, sep, expected_source in SURGICAL_FIXES:
    key = (word, pos, cefr)
    found = False
    for v in all_v:
        if (v['word'], v['pos'], v['cefr']) == key:
            found = True
            if v['gloss'] != old_gloss:
                print(f'  SKIP {key}: current gloss != expected (current={v["gloss"]!r}, expected={old_gloss!r})')
                surgical_skipped += 1
                break
            # Validate gate
            chunks = [c.strip() for c in new_gloss.replace('|', ';').split(';') if c.strip()]
            count = len(chunks)
            gate_violations = mod.validate_verdict(word, new_gloss, sep, count)
            if gate_violations:
                print(f'  GATE FAIL {key}: {gate_violations}')
                surgical_violations.append((key, gate_violations))
                surgical_skipped += 1
                break
            # Post-fix hidden leak check
            if has_hidden_leak(word, new_gloss):
                print(f'  HIDDEN LEAK {key}: new gloss {new_gloss!r} still has headword in chunk')
                surgical_violations.append((key, ['hidden_leak_remaining']))
                surgical_skipped += 1
                break
            # Recompute hash from current txt def
            defn = txt_defs.get(key, '')
            new_hash = hashlib.sha256(f'{word}|{pos}|{cefr}|{defn}'.encode()).hexdigest()[:16]
            v['gloss'] = new_gloss
            v['hash'] = new_hash
            v['rule_applied'] = 'concrete_1sense' if sep == 'none' else ('2sense_samedomain' if sep == ';' else '2sense_distinct')
            v['reasoning'] = f'HIDDEN SELF-REF fix: {old_gloss} -> {new_gloss}'
            surgical_applied += 1
            print(f'  FIX {key}: {old_gloss!r} -> {new_gloss!r}')
            break
    if not found:
        print(f'  NOT FOUND: {key}')
        surgical_skipped += 1

# Apply no-gloss
no_gloss_applied = 0
for word, pos, cefr, expected_old in NO_GLOSS:
    key = (word, pos, cefr)
    found = False
    for v in all_v:
        if (v['word'], v['pos'], v['cefr']) == key:
            found = True
            if v.get('decision') == 'no-gloss':
                print(f'  ALREADY NO-GLOSS {key}')
                break
            v['decision'] = 'no-gloss'
            # Clear gloss so audit's is_applied check returns False (no-gloss means
            # "don't apply, keep original Oxford def"). Otherwise audit sees
            # is_applied=True if txt has the old phrase, then has_hidden_leak
            # fires, putting it in known_leak_unfixed incorrectly.
            v['gloss'] = ''
            v['reasoning'] = f'NO-GLOSS: phrase-only, headword unavoidable ({expected_old})'
            no_gloss_applied += 1
            print(f'  NO-GLOSS {key}: {expected_old!r}')
            break
    if not found:
        print(f'  NOT FOUND: {key}')
        no_gloss_applied = 0  # count as not applied

# Write back
with open(VERDICTS_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'\nWrote {VERDICTS_PATH}')

# Summary
print(f'\n=== Summary ===')
print(f'Surgical applied: {surgical_applied}/{len(SURGICAL_FIXES)}')
print(f'  Skipped: {surgical_skipped}')
print(f'  Violations: {len(surgical_violations)}')
if surgical_violations:
    for k, v in surgical_violations:
        print(f'    {k}: {v}')
print(f'No-gloss applied: {no_gloss_applied}/{len(NO_GLOSS)}')
print(f'Total: {surgical_applied + no_gloss_applied}/{len(SURGICAL_FIXES) + len(NO_GLOSS)}')

# Verify
if surgical_violations:
    print('\nFix script completed with violations. Audit rebuild may still show known_leak_unfixed.')
    sys.exit(1)
print('\nFix script completed successfully. Now run:')
print('  python -m tools._build_audit')
print('  python -m tools._apply_glosses_to_txt')
print('  python -m tools._verify_audit_standard')
print('  pytest')
