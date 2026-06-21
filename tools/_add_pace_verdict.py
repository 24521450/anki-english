"""Step 4 of Task B: Add pace|noun|B2 verdict to gloss_all_verdicts.json.

Oxford page pace1_1 (not pace_1) has 2 B2 senses both about "speed":
- "the speed at which somebody/something walks, runs or moves"
- "the speed at which something happens"

Rule B pick1 (both senses same domain "speed") -> 1 chunk -> "speed".
"""
import json
import hashlib
import sys

PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'
VERDICTS_PATH = f'{PROJECT_ROOT}/data/simplify_diff/gloss_all_verdicts.json'

# Load gate for validation
sys.path.insert(0, PROJECT_ROOT)
import importlib.util as u
spec = u.spec_from_file_location('gloss_llm', f'{PROJECT_ROOT}/src/deck_builder/gloss_llm.py')
mod = u.module_from_spec(spec)
sys.modules['gloss_llm'] = mod
spec.loader.exec_module(mod)

# Load existing verdicts
with open(VERDICTS_PATH, encoding='utf-8') as f:
    data = json.load(f)
all_v = data['verdicts']

# Check if pace already exists
key = ('pace', 'noun', 'B2')
existing = [v for v in all_v if (v['word'], v['pos'], v['cefr']) == key]
if existing:
    print(f'ALREADY EXISTS: {existing[0]}')
else:
    # Build new verdict
    new_verdict = {
        'word': 'pace',
        'pos': 'noun',
        'cefr': 'B2',
        'gloss': 'speed',
        'decision': 'gloss',
        'confidence': 0.95,
        'reasoning': 'B2 pace: 2 senses both about rate/speed, same domain. Rule B pick1 -> "speed".',
        'category': 'concrete',
        'rule_applied': 'rule_b_pick1',
        'hash': '',
        'separator': 'none',
        'count': 1,
    }

    # Validate gate
    errs = mod.validate_verdict('pace', 'speed', 'none', 1)
    if errs:
        print(f'GATE FAILED: {errs}')
        sys.exit(1)
    print('GATE PASS: pace|speed|none|1')

    # Compute hash from source def (from merged)
    src_def = 'the speed at which somebody/something walks, runs or moves|the speed at which something happens'  # first 2 B2 senses
    new_verdict['hash'] = hashlib.sha256(f'pace|noun|B2|{src_def}'.encode()).hexdigest()[:16]
    print(f'hash: {new_verdict["hash"]}')

    # Add to verdicts
    all_v.append(new_verdict)
    print(f'Added verdict. Total: {len(all_v)}')

# Backup + save
import shutil
backup = VERDICTS_PATH + '.bak_pre_pace_add_20260618'
shutil.copy(VERDICTS_PATH, backup)
print(f'Backup: {backup}')

with open(VERDICTS_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Wrote {VERDICTS_PATH}')
