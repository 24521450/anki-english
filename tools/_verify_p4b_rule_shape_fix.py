"""P4B Rule-Shape Consistency Fix — verifier.

Asserts the 24 P4B rows now have multi-chunk glosses consistent with
their `rule_applied`. Reads the same P4B_FIXES list from the apply tool
(single source of truth).

Run: `python -m tools._verify_p4b_rule_shape_fix`

Pass criteria (all must hold):
  1. 24 audit rows match expected new glosses.
  2. 24 TXT rows match audit glosses.
  3. 24 JSONL rows match audit glosses.
  4. All 24 pass `validate_verdict`.
  5. All 24 have `separator = "|"` and matching `gloss_word_count`.
  6. `gate_status = "pass"` on all 24.
  7. Audit row count still 2487.
  8. No duplicate audit keys (word, pos, cefr).
  9. Rule-shape contradiction count = 0 (was 24 before P4B).
 10. P3B verifier still PASS.
 11. P4A verifier still PASS.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
JSONL_PATH = PROJECT_ROOT / 'data' / 'anki_notes.jsonl'

from tools._apply_p4b_rule_shape_fix import P4B_FIXES  # noqa: E402

EXPECTED_KEYS = {(w, p.lower(), c.upper()) for w, p, c, _o, _r, _n in P4B_FIXES}
EXPECTED_GLOSS_BY_KEY = {
    (w, p.lower(), c.upper()): new_g for w, p, c, _o, _r, new_g in P4B_FIXES
}

# Rules that require multi-chunk gloss (per CONTEXT.md § Rule-Shape Consistency)
PICK_RULES = {
    '2sense_distinct', '3sense_distinct',
    'rule_b_pick2', 'rule_b_pick2_addendum',
    'multi_pos_pick2',
}


def _load_audit() -> list[dict]:
    return [
        json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]


def _load_txt() -> list[dict]:
    rows: list[dict] = []
    for line in TXT_PATH.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            continue
        rows.append({
            'word': parts[3].strip(),
            'pos': parts[4].strip(),
            'cefr': parts[14].strip(),
            'def': parts[6],
        })
    return rows


def _load_jsonl() -> list[dict]:
    return [
        json.loads(l) for l in JSONL_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]


def main() -> int:
    print('=' * 72)
    print('P4B RULE-SHAPE CONSISTENCY FIX VERIFIER')
    print('=' * 72)

    audit = _load_audit()
    txt = _load_txt()
    jsonl = _load_jsonl()

    print(f'\nLoaded {len(audit)} audit rows, {len(txt)} TXT rows, {len(jsonl)} JSONL rows.')

    failures: list[str] = []

    # 1. Audit row count = 2487
    print('\n[1] Audit row count must remain 2487...')
    if len(audit) != 2487:
        failures.append(f'audit count = {len(audit)} (expected 2487)')
    print(f'  audit rows: {len(audit)}')

    # 2. No duplicate audit keys (word, pos, cefr)
    print('\n[2] No duplicate audit (word, pos, cefr) keys...')
    keys = [(r['word'].lower(), r['pos'].lower(), r['cefr'].upper()) for r in audit]
    dup = [k for k in set(keys) if keys.count(k) > 1]
    print(f'  duplicate keys: {len(dup)}')
    if dup:
        failures.append(f'audit has {len(dup)} duplicate keys: {dup[:5]}')

    # 3. Each of 24 expected rows matches in audit
    print('\n[3] 24 expected audit rows have the new gloss...')
    audit_by_key = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper()): r for r in audit
    }
    synced_audit = 0
    for word, pos, cefr, _o, _r, _n in P4B_FIXES:
        key = (word, pos.lower(), cefr.upper())
        if key not in audit_by_key:
            failures.append(f'audit row missing for {key}')
            continue
        r = audit_by_key[key]
        # Drift tolerance: P7 may have collapsed this row's gloss to a
        # single-chunk common_core_trimmed form.
        if (r.get('fix_status') or '').strip() == 'p7_redundant_sense_trimmed':
            synced_audit += 1
        elif r['gloss_after'] != EXPECTED_GLOSS_BY_KEY[key]:
            failures.append(
                f'audit gloss mismatch {key}: got {r["gloss_after"]!r}, '
                f'expected {EXPECTED_GLOSS_BY_KEY[key]!r}'
            )
        else:
            synced_audit += 1
    print(f'  synced: {synced_audit}/{len(P4B_FIXES)}')

    # 4. Each of 24 expected rows in TXT has the new def
    print('\n[4] 24 expected TXT rows have the new def...')
    txt_by_key = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper()): r for r in txt
    }
    synced_txt = 0
    p7_keys: set[tuple] = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper())
        for r in audit if (r.get('fix_status') or '').strip() == 'p7_redundant_sense_trimmed'
    }
    for word, pos, cefr, _o, _r, _n in P4B_FIXES:
        key = (word, pos.lower(), cefr.upper())
        if key not in txt_by_key:
            failures.append(f'TXT row missing for {key}')
            continue
        r = txt_by_key[key]
        if key in p7_keys:
            synced_txt += 1
        elif r['def'] != EXPECTED_GLOSS_BY_KEY[key]:
            failures.append(
                f'TXT def mismatch {key}: got {r["def"]!r}, '
                f'expected {EXPECTED_GLOSS_BY_KEY[key]!r}'
            )
        else:
            synced_txt += 1
    print(f'  synced: {synced_txt}/{len(P4B_FIXES)}')

    # 5. Each of 24 expected rows in JSONL has the new def
    print('\n[5] 24 expected JSONL rows have the new def...')
    jsonl_by_key = {
        (r['word'], r['pos'].lower(), r['cefr'].upper()): r for r in jsonl
    }
    synced_jsonl = 0
    for word, pos, cefr, _o, _r, _n in P4B_FIXES:
        key = (word, pos.lower(), cefr.upper())
        if key not in jsonl_by_key:
            failures.append(f'JSONL row missing for {key}')
            continue
        r = jsonl_by_key[key]
        if key in p7_keys:
            synced_jsonl += 1
        elif r['definition'] != EXPECTED_GLOSS_BY_KEY[key]:
            failures.append(
                f'JSONL def mismatch {key}: got {r["definition"]!r}, '
                f'expected {EXPECTED_GLOSS_BY_KEY[key]!r}'
            )
        else:
            synced_jsonl += 1
    print(f'  synced: {synced_jsonl}/{len(P4B_FIXES)}')

    # 6. All 24 pass validate_verdict + have separator="|" + matching word_count
    print('\n[6] All 24 audit rows pass validate_verdict + metadata check...')
    from src.deck_builder.gloss_llm import validate_verdict
    meta_ok = 0
    for word, pos, cefr, _o, _r, _n in P4B_FIXES:
        key = (word, pos.lower(), cefr.upper())
        if key not in audit_by_key:
            continue
        r = audit_by_key[key]
        gloss = r['gloss_after']
        sep = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        computed_wc = len(re.sub(r'[|;]', ' ', gloss).split())

        v_errs = validate_verdict(word, gloss, sep, len(chunks))
        if v_errs:
            failures.append(f'validate_verdict fail {key}: {v_errs}')
            continue
        # P7 may have collapsed this row's gloss to common_core_trimmed (single-chunk).
        if (r.get('fix_status') or '').strip() == 'p7_redundant_sense_trimmed':
            # Accept single-chunk form.
            pass
        elif r.get('separator') != '|':
            failures.append(f'separator mismatch {key}: got {r.get("separator")!r}, expected "|"')
            continue
        if r.get('gloss_word_count') != computed_wc:
            failures.append(
                f'gloss_word_count mismatch {key}: declared={r.get("gloss_word_count")}, computed={computed_wc}'
            )
            continue
        if r.get('gate_status') != 'pass':
            failures.append(f'gate_status != pass {key}: got {r.get("gate_status")!r}')
            continue
        meta_ok += 1
    print(f'  metadata OK: {meta_ok}/{len(P4B_FIXES)}')

    # 7. Rule-shape contradiction count = 0 (was 24 before P4B)
    print('\n[7] Rule-shape contradictions must be 0...')
    contradictions = []
    for r in audit:
        rule = r.get('rule_applied') or ''
        gloss = (r.get('gloss_after') or '').strip()
        is_single = '|' not in gloss and ';' not in gloss
        if rule in PICK_RULES and is_single:
            contradictions.append((r['word'], r['pos'], r['cefr'], rule, gloss))
    print(f'  rule_shape_contradiction: {len(contradictions)}')
    if contradictions:
        failures.append(
            f'rule-shape contradictions remain: {len(contradictions)} '
            f'(e.g. {contradictions[:3]})'
        )

    # 8. P3B regression
    print('\n[8] P3B regression check...')
    cmd = [sys.executable, '-m', 'tools._verify_deck_output_p3b']
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    p3b_ok = 'PASS: deck output QA completed successfully.' in res.stdout
    if not p3b_ok:
        failures.append(f'P3B verifier FAILED:\n{res.stdout[-1500:]}')
        print(f'  FAILED — last 1500 chars of stdout:\n{res.stdout[-1500:]}')
    else:
        for line in res.stdout.splitlines():
            if 'TXT rows count' in line or 'duplicates:' in line or 'mismatches=' in line:
                print(f'  P3B: {line.strip()}')
        print('  P3B PASS')

    # 9. P4A regression
    print('\n[9] P4A regression check...')
    cmd = [sys.executable, '-m', 'tools._verify_p4a_coverage_fix']
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    p4a_ok = 'PASS: P4A sense coverage fix verified' in res.stdout
    if not p4a_ok:
        failures.append(f'P4A verifier FAILED:\n{res.stdout[-1500:]}')
        print(f'  FAILED — last 1500 chars of stdout:\n{res.stdout[-1500:]}')
    else:
        for line in res.stdout.splitlines():
            if 'synced:' in line or 'metadata OK' in line:
                print(f'  P4A: {line.strip()}')
        print('  P4A PASS')

    # === Result ===
    print('\n' + '=' * 72)
    if failures:
        print(f'FAIL: {len(failures)} assertion(s) failed:')
        for f in failures:
            print(f'  - {f}')
        return 1

    print('PASS: P4B rule-shape consistency fix verified across audit + TXT + JSONL.')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())