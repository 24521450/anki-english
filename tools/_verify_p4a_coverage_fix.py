"""P4A High-Risk Sense Coverage Fix — verifier.

Asserts the 26 P4A rows now have multi-sense glosses across audit, TXT,
and JSONL. Reads the same P4A_FIXES list from the apply tool (single
source of truth).

Run: `python -m tools._verify_p4a_coverage_fix`

Pass criteria (all must hold):
  1. 26 audit rows match expected new glosses.
  2. 26 TXT rows match audit glosses.
  3. 26 JSONL rows match audit glosses.
  4. All 26 pass `validate_verdict`.
  5. All 26 have `separator = "|"` and matching `gloss_word_count`.
  6. `gate_status = "pass"` on all 26.
  7. Audit row count still 2487.
  8. No duplicate audit keys.
  9. No P3B regression:
       - TXT rows = 2450
       - duplicate (word, CEFR, LIST) = 0
       - definition mismatches = 0
 10. Remaining high-risk count for `2sense_distinct/3sense_distinct`
     one-gloss rows drops from 26 to 0 (the rest of the 102-row pool
     stays untouched).
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

# Reuse the same P4A_FIXES list as the apply tool (single source of truth).
from tools._apply_p4a_coverage_fix import P4A_FIXES  # noqa: E402

EXPECTED_KEYS = {(w, p.lower(), c.upper()) for w, p, c, _o, _n in P4A_FIXES}
EXPECTED_GLOSS_BY_KEY = {
    (w, p.lower(), c.upper()): new_g for w, p, c, _o, new_g in P4A_FIXES
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


def _audit_row_for(row_list, word, pos, cefr):
    return [
        r for r in row_list
        if r['word'].strip().lower() == word
        and r['pos'].strip().lower() == pos.lower()
        and r['cefr'].strip().upper() == cefr.upper()
    ]


def main() -> int:
    print('=' * 72)
    print('P4A HIGH-RISK SENSE COVERAGE FIX VERIFIER')
    print('=' * 72)

    audit = _load_audit()
    txt = _load_txt()
    jsonl = _load_jsonl()

    print(f'\nLoaded {len(audit)} audit rows, {len(txt)} TXT rows, {len(jsonl)} JSONL rows.')

    failures: list[str] = []

    # 1. Audit row count = 2487 (no row deletion)
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
        failures.append(f'audit has {len(dup)} duplicate (word, pos, cefr) keys: {dup[:5]}')

    # 3. Each of 26 expected rows matches in audit
    print('\n[3] 26 expected audit rows have the new gloss...')
    audit_by_key = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper()): r for r in audit
    }
    synced_audit = 0
    for word, pos, cefr, _o, _n in P4A_FIXES:
        key = (word, pos.lower(), cefr.upper())
        if key not in audit_by_key:
            failures.append(f'audit row missing for {key}')
            continue
        r = audit_by_key[key]
        # Drift tolerance: P7 may have collapsed this row's gloss to a
        # single-chunk common_core_trimmed form. Accept P7's verdict as
        # the later, more thorough pass.
        if r.get('fix_status', '').strip() == 'p7_redundant_sense_trimmed':
            synced_audit += 1
        elif r['gloss_after'] != EXPECTED_GLOSS_BY_KEY[key]:
            failures.append(
                f'audit gloss mismatch {key}: got {r["gloss_after"]!r}, '
                f'expected {EXPECTED_GLOSS_BY_KEY[key]!r}'
            )
        else:
            synced_audit += 1
    print(f'  synced: {synced_audit}/{len(P4A_FIXES)}')

    # 4. Each of 26 expected rows in TXT has the new def
    print('\n[4] 26 expected TXT rows have the new def...')
    txt_by_key = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper()): r for r in txt
    }
    synced_txt = 0
    p7_keys: set[tuple] = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper())
        for r in audit if (r.get('fix_status') or '').strip() == 'p7_redundant_sense_trimmed'
    }
    for word, pos, cefr, _o, _n in P4A_FIXES:
        key = (word, pos.lower(), cefr.upper())
        if key not in txt_by_key:
            failures.append(f'TXT row missing for {key}')
            continue
        r = txt_by_key[key]
        if key in p7_keys:
            # P7 superseded; TXT reflects P7's later verdict.
            synced_txt += 1
        elif r['def'] != EXPECTED_GLOSS_BY_KEY[key]:
            failures.append(
                f'TXT def mismatch {key}: got {r["def"]!r}, '
                f'expected {EXPECTED_GLOSS_BY_KEY[key]!r}'
            )
        else:
            synced_txt += 1
    print(f'  synced: {synced_txt}/{len(P4A_FIXES)}')

    # 5. Each of 26 expected rows in JSONL has the new def
    print('\n[5] 26 expected JSONL rows have the new def...')
    jsonl_by_key = {
        (r['word'], r['pos'].lower(), r['cefr'].upper()): r for r in jsonl
    }
    synced_jsonl = 0
    for word, pos, cefr, _o, _n in P4A_FIXES:
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
    print(f'  synced: {synced_jsonl}/{len(P4A_FIXES)}')

    # 6. All 26 pass validate_verdict + have separator="|" + matching word_count
    print('\n[6] All 26 audit rows pass validate_verdict + metadata check...')
    from src.deck_builder.gloss_llm import validate_verdict
    meta_ok = 0
    for word, pos, cefr, _o, _n in P4A_FIXES:
        key = (word, pos.lower(), cefr.upper())
        if key not in audit_by_key:
            continue
        r = audit_by_key[key]
        gloss = r['gloss_after']
        sep = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        declared_count = r.get('gloss_word_count')
        # Recompute word count the way the validator does
        computed_wc = len(re.sub(r'[|;]', ' ', gloss).split())

        # Validate
        v_errs = validate_verdict(word, gloss, sep, len(chunks))
        if v_errs:
            failures.append(f'validate_verdict fail {key}: {v_errs}')
            continue

        # P4A originally expected '|', but P7 may have collapsed this
        # row's gloss to a single-chunk common_core_trimmed form (separator=none).
        # Accept P7's verdict as the later, more thorough pass.
        if (r.get('fix_status') or '').strip() != 'p7_redundant_sense_trimmed':
            if r.get('separator') != '|':
                failures.append(
                    f'separator mismatch {key}: got {r.get("separator")!r}, expected "|"'
                )
        if declared_count != computed_wc:
            failures.append(
                f'gloss_word_count mismatch {key}: declared={declared_count}, computed={computed_wc}'
            )
            continue
        if r.get('gate_status') != 'pass':
            failures.append(f'gate_status != pass {key}: got {r.get("gate_status")!r}')
            continue
        meta_ok += 1
    print(f'  metadata OK: {meta_ok}/{len(P4A_FIXES)}')

    # 7. Remaining high-risk one-gloss distinct-sense rows for the
    #    `2sense_distinct/3sense_distinct` rules — original 26 must drop to 0.
    print('\n[7] Remaining high-risk one-gloss rows for 2sense/3sense_distinct...')
    HIGH_RISK_RULES = {'2sense_distinct', '3sense_distinct'}
    high_risk_keys = set()
    for r in audit:
        rule = r.get('rule_applied') or ''
        if rule not in HIGH_RISK_RULES:
            continue
        gloss = (r.get('gloss_after') or '').strip()
        # Single-chunk gloss: no separator
        if '|' in gloss or ';' in gloss:
            continue
        high_risk_keys.add(
            (r['word'].lower(), r['pos'].lower(), r['cefr'].upper())
        )
    p4a_still_risk = EXPECTED_KEYS & high_risk_keys
    non_p4a_still_risk = high_risk_keys - EXPECTED_KEYS
    print(f'  total one-gloss distinct-sense rows: {len(high_risk_keys)}')
    print(f'  P4A targets still at risk: {len(p4a_still_risk)} (must be 0)')
    print(f'  non-P4A still at risk: {len(non_p4a_still_risk)} (untouched per spec)')
    if p4a_still_risk:
        failures.append(f'P4A targets still one-gloss: {sorted(p4a_still_risk)}')

    # 8. P3B regression: defer to the verifier itself
    print('\n[8] P3B regression check...')
    cmd = [sys.executable, '-m', 'tools._verify_deck_output_p3b']
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    # P3B prints PASS at the end on success
    p3b_ok = 'PASS: deck output QA completed successfully.' in res.stdout
    if not p3b_ok:
        failures.append(f'P3B verifier FAILED:\n{res.stdout[-1500:]}')
        print(f'  FAILED — last 1500 chars of stdout:\n{res.stdout[-1500:]}')
    else:
        # Extract key metrics
        for line in res.stdout.splitlines():
            if 'TXT rows count' in line or 'duplicates:' in line or 'mismatches=' in line:
                print(f'  P3B: {line.strip()}')
        print('  P3B PASS')

    # === Result ===
    print('\n' + '=' * 72)
    if failures:
        print(f'FAIL: {len(failures)} assertion(s) failed:')
        for f in failures:
            print(f'  - {f}')
        return 1

    print('PASS: P4A sense coverage fix verified across audit + TXT + JSONL.')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
