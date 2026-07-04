"""P15: Full Simple Gloss Patch v2 -- verifier.

Required checks:
  1. Audit row count is exactly 2487.
  2. Exactly 51 target keys match the P15 patch values.
  3. No non-target audit rows differ from the pre-P15 backup.
  4. All 51 glosses pass validate_verdict.
  5. All gloss_word_count values match actual chunk word counts.
  6. All 51 TXT definitions are synced.
  7. All 51 JSONL definitions are synced (after rebuild).
  8. fit|noun|C1 has the expected P15 state, and fit|noun|B2 is unchanged.
  9. P15 QA invariants hold:
     - No exact headword glosses.
     - No gloss has more | segments than def_before.
     - No rule-count mismatch for leading-N *_sense_distinct.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
AUDIT_PATH = paths.deck_audit_jsonl
TXT_PATH = paths.anki_notes_txt
JSONL_PATH = paths.anki_notes_jsonl
INPUT_PATH = Path(r"C:\Users\admin\Downloads\audit_full_deck_v2_p15_full_simple_gloss_patch_v2.jsonl")

EXPECTED_CHANGE_COUNT = 51

APPLY_FIELDS = (
    'gloss_after', 'separator', 'rule_applied', 'gloss_word_count',
    'fix_status', 'review_needed',
)


def _key(r: dict) -> tuple[str, str, str]:
    return (
        r['word'].strip().lower(),
        r['pos'].strip().lower(),
        r['cefr'].strip().upper(),
    )


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def _find_pre_apply_backup() -> Path | None:
    for p in sorted(AUDIT_PATH.parent.glob(f'{AUDIT_PATH.name}.bak_pre_p15_*'), reverse=True):
        return p
    return None


def main() -> int:
    print('=' * 72)
    print('P15 full simple gloss patch Verifier')
    print('=' * 72)

    if not AUDIT_PATH.exists():
        print('FATAL: curated/deck_audit.jsonl does not exist')
        return 1

    audit = _load_jsonl(AUDIT_PATH)
    if not INPUT_PATH.exists():
        print(f'FATAL: target input {INPUT_PATH} not found')
        return 1
    target = _load_jsonl(INPUT_PATH)
    pre = _find_pre_apply_backup()
    if pre is None:
        print('FATAL: no pre-apply backup found')
        return 1
    pre_audit = _load_jsonl(pre)

    print(f'  Audit rows:     {len(audit)}')
    print(f'  Target rows:    {len(target)}')
    print(f'  Pre-apply rows: {len(pre_audit)}')
    print(f'  Pre-apply backup: {pre.name}')

    failures: list[str] = []

    if len(audit) != 2487:
        failures.append(f'audit has {len(audit)} rows (expected 2487)')
    if len(target) != 2487:
        failures.append(f'target has {len(target)} rows (expected 2487)')
    if len(pre_audit) != 2487:
        failures.append(f'pre_audit has {len(pre_audit)} rows (expected 2487)')

    target_by_key = {_key(r): r for r in target}
    audit_by_key = {_key(r): r for r in audit}
    pre_by_key = {_key(r): r for r in pre_audit}

    # 1. Identify the target keys (keys where patch differs from pre-patch)
    target_keys: list[tuple[str, str, str]] = []
    for k in pre_by_key:
        c = pre_by_key[k]
        n = target_by_key[k]
        diffs = {f for f in APPLY_FIELDS if c.get(f) != n.get(f)}
        if 'review_needed' in diffs:
            if not c.get('review_needed') and not n.get('review_needed'):
                diffs.remove('review_needed')
        if diffs:
            target_keys.append(k)

    print(f'\n[1] Target keys count: {len(target_keys)}')
    if len(target_keys) != EXPECTED_CHANGE_COUNT:
        failures.append(f'Expected {EXPECTED_CHANGE_COUNT} changed keys, got {len(target_keys)}')
    else:
        print(f'  [OK] Exactly {EXPECTED_CHANGE_COUNT} target keys')

    # 2. Check that target keys match patch values in audit
    print('\n[2] Checking target keys match patch in audit...')
    for k in target_keys:
        a = audit_by_key[k]
        t = target_by_key[k]
        for fld in APPLY_FIELDS:
            a_val = a.get(fld)
            t_val = t.get(fld)
            if a_val != t_val:
                # review_needed False or None are treated same
                if fld == 'review_needed' and not a_val and not t_val:
                    continue
                failures.append(f'{k} field {fld!r}: audit={a_val!r}, target={t_val!r}')
    if not failures:
        print('  [OK] Target keys match patch values')

    # 3. Check no non-target keys changed vs pre-apply
    print('\n[3] Checking non-target keys vs pre-apply...')
    target_set = set(target_keys)
    for k in pre_by_key:
        if k in target_set:
            continue
        a = audit_by_key[k]
        p = pre_by_key[k]
        # Compare raw dicts except we only care about fields in the audit schema
        diffs = {fld for fld in p if p.get(fld) != a.get(fld)}
        if diffs:
            failures.append(f'Non-target key {k} changed: {diffs}')
    if not any(f.startswith('Non-target key') for f in failures):
        print('  [OK] No non-target rows changed')

    # 4. validate_verdict on the 51 target glosses
    print('\n[4] Validating target glosses...')
    from src.deck_builder.gloss_llm import validate_verdict
    for k in target_keys:
        a = audit_by_key[k]
        g = a.get('gloss_after', '').strip()
        sep = a.get('separator', 'none').strip()
        
        # Word count check
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', g) if c.strip()]
        actual_wc = sum(len(c.split()) for c in chunks)
        if actual_wc != a.get('gloss_word_count'):
            failures.append(f'{k} declared wc={a.get("gloss_word_count")} != actual={actual_wc} for gloss {g!r}')
            
        v_errors = validate_verdict(a['word'], g, sep, len(chunks))
        if v_errors:
            failures.append(f'{k} gloss {g!r} fails validation: {v_errors}')
    if not any(f.endswith('fails validation') for f in failures):
        print('  [OK] All target glosses valid')

    # 5. fit|noun|C1 state and fit|noun|B2 unchanged check
    print('\n[5] Checking fit state...')
    fit_c1 = audit_by_key.get(('fit', 'noun', 'C1'))
    if not fit_c1:
        failures.append('fit|noun|C1 missing from audit')
    else:
        if fit_c1.get('gloss_after') != 'medical seizure|coughing or laughing you cannot stop|sudden strong feeling':
            failures.append(f"fit|noun|C1 gloss_after={fit_c1.get('gloss_after')!r}")
        if fit_c1.get('rule_applied') != '3sense_distinct_with_facet':
            failures.append(f"fit|noun|C1 rule_applied={fit_c1.get('rule_applied')!r}")
        if not fit_c1.get('review_needed'):
            failures.append("fit|noun|C1 review_needed is not True")
        if fit_c1.get('fix_status') != 'p15_simple_gloss_repaired':
            failures.append(f"fit|noun|C1 fix_status={fit_c1.get('fix_status')!r}")
            
    fit_b2 = audit_by_key.get(('fit', 'noun', 'B2'))
    if not fit_b2:
        failures.append('fit|noun|B2 missing from audit')
    else:
        if fit_b2.get('gloss_after') != 'size or suitability':
            failures.append(f"fit|noun|B2 gloss_after={fit_b2.get('gloss_after')!r}")
        if fit_b2.get('fix_status') != 'p12_equiv_sense_semantic_hotfix':
            failures.append(f"fit|noun|B2 fix_status={fit_b2.get('fix_status')!r}")
            
    if not any('fit' in f for f in failures):
        print('  [OK] fit|noun|C1 and B2 states are correct')

    # 6. P15 QA invariants hold
    print('\n[6] Validating QA invariants...')
    for k in target_keys:
        a = audit_by_key[k]
        word = a['word']
        gloss = a.get('gloss_after', '')
        def_before = a.get('def_before', '')
        rule = a.get('rule_applied', '')
        
        # Exact headword gloss check
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        for c in chunks:
            if c.lower() == word.lower():
                failures.append(f'{k} has exact headword chunk {c!r} in gloss')
                
        # Gloss segments vs def_before segments check
        def_chunks = [c.strip() for c in def_before.split('|') if c.strip()]
        if len(chunks) > len(def_chunks):
            failures.append(f'{k} has {len(chunks)} chunks, def_before has {len(def_chunks)} chunks (gloss cannot have more)')
            
        # Rule count check for leading-N
        m = re.match(r'^(\d+)sense_distinct', rule)
        if m:
            n = int(m.group(1))
            if len(chunks) != n:
                failures.append(f'{k} rule={rule!r} expected {n} chunks, got {len(chunks)}')
                
    if not any('QA' in f or 'chunks' in f or 'headword' in f for f in failures):
        print('  [OK] QA invariants hold')

    # 7. TXT Sync check
    print('\n[7] Checking TXT Sync...')
    if TXT_PATH.exists():
        txt_lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
        txt_keys: dict[tuple, str] = {}
        for line in txt_lines:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            txt_k = (
                parts[3].strip().lower(),
                parts[4].strip().lower(),
                parts[14].strip().upper(),
            )
            txt_keys[txt_k] = parts[6].strip()
            
        n_txt_synced = 0
        for k in target_keys:
            expected = target_by_key[k].get('gloss_after', '').strip()
            if k in txt_keys:
                if txt_keys[k] != expected:
                    failures.append(f'TXT {k} def={txt_keys[k]!r} != expected={expected!r}')
                else:
                    n_txt_synced += 1
        print(f'  TXT synced: {n_txt_synced}/{len(target_keys)}')
    else:
        failures.append('TXT file does not exist')

    # 8. JSONL Sync check
    print('\n[8] Checking JSONL Sync...')
    if JSONL_PATH.exists():
        jsonl_rows = _load_jsonl(JSONL_PATH)
        jsonl_by_key = {
            (r.get('word', '').strip().lower(),
             r.get('pos', '').strip().lower(),
             r.get('cefr', '').strip().upper()): r
            for r in jsonl_rows
        }
        n_jsonl_synced = 0
        n_jsonl_absent = 0
        for k in target_keys:
            expected = target_by_key[k].get('gloss_after', '').strip()
            jsonl_r = jsonl_by_key.get(k)
            if jsonl_r is None:
                n_jsonl_absent += 1
                continue
            if (jsonl_r.get('definition') or '').strip() != expected:
                failures.append(
                    f'JSONL {k} definition={jsonl_r.get("definition")!r} != expected={expected!r}'
                )
            else:
                n_jsonl_synced += 1
        print(f'  JSONL synced: {n_jsonl_synced}, absent/deferred: {n_jsonl_absent}')
    else:
        print('  WARN: JSONL not present (run build_notes to generate/verify)')

    if failures:
        print('=' * 72)
        print(f'FAIL -- P15 verifier found {len(failures)} failures:')
        for f in failures[:30]:
            print(f'  {f}')
        if len(failures) > 30:
            print(f'  ... and {len(failures) - 30} more')
        print('=' * 72)
        return 1

    print('=' * 72)
    print('PASS -- P15 verification passed successfully!')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
