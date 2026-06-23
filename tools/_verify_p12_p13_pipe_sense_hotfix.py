"""P12+P13: Equivalent-sense + pipe/sense hotfix -- verifier.

Reads:
  - `C:\\Users\\admin\\Downloads\\audit_full_deck_v2_p13_pipe_sense_hotfix.jsonl`
    (target values for the 33 keys)
  - `data/audit_full_deck_v2.jsonl` (post-apply)
  - `English Academic Vocabulary.txt` (post-apply)
  - `data/anki_notes.jsonl` (post-rebuild)

Required checks:

  1. Audit row count remains 2487.
  2. Exactly 33 audit keys match the P13 target values.
  3. No non-target audit rows differ from the pre-apply backup
     (data/audit_full_deck_v2.jsonl.bak_pre_p12_p13_<ts>).
  4. Each target row's `gloss_after` matches the P13 target.
  5. Each target row's `rule_applied` matches the P13 target.
  6. `miserable|adjective|B2` final state:
     - `def_before = very unhappy or uncomfortable|making you feel very unhappy or uncomfortable`
     - `gloss_after = very unhappy or unpleasant`
     - `separator = none`
     - `rule_applied = facet_phrase`
  7. P13 metadata fixes:
     - `gross` rule = `3sense_distinct`
     - `passing` rule = `3sense_distinct`
     - `alien` rule = `4sense_distinct`
  8. `provincial` has 2 gloss chunks (matches 2 def_before chunks).
  9. TXT cells updated for changed glosses (deferred for missing-row keys).
 10. JSONL definitions sync for changed glosses that have deck counterparts.

Run: `python -m tools._verify_p12_p13_pipe_sense_hotfix`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
JSONL_PATH = PROJECT_ROOT / 'data' / 'anki_notes.jsonl'
INPUT_PATH = Path(r"C:\Users\admin\Downloads\audit_full_deck_v2_p13_pipe_sense_hotfix.jsonl")

EXPECTED_CHANGE_COUNT = 33

APPLY_FIELDS = (
    'def_before', 'gloss_after', 'separator', 'rule_applied',
    'gloss_word_count', 'fix_status', 'gate_status',
)

MISERABLE_KEY = ('miserable', 'adjective', 'B2')
MISERABLE_EXPECTED = {
    'def_before': 'very unhappy or uncomfortable|making you feel very unhappy or uncomfortable',
    'gloss_after': 'very unhappy or unpleasant',
    'separator': 'none',
    'rule_applied': 'facet_phrase',
}

# P13 metadata fixes: (word_lower, pos_lower, cefr_upper) -> expected rule_applied.
# Match the exact audit row keys.
P13_METADATA_CHECKS = {
    ('gross', 'adjective', 'C1'): '3sense_distinct',
    ('passing', 'noun', 'C1'): '3sense_distinct',
    ('alien', 'adjective', 'C1'): '4sense_distinct',
}

PROVINCIAL_KEY = ('provincial', 'adjective', 'C1')


def _key(r: dict) -> tuple[str, str, str]:
    return (
        r['word'].strip().lower(),
        r['pos'].strip().lower(),
        r['cefr'].strip().upper(),
    )


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def _find_pre_apply_backup() -> Path | None:
    for p in sorted(AUDIT_PATH.parent.glob(f'{AUDIT_PATH.name}.bak_pre_p12_p13_*'),
                    reverse=True):
        return p
    return None


def main() -> int:
    print('=' * 72)
    print('P12+P13 pipe/sense hotfix Verifier')
    print('=' * 72)

    audit = _load_jsonl(AUDIT_PATH)
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

    target_by_key = {_key(r): r for r in target}
    audit_by_key = {_key(r): r for r in audit}
    pre_by_key = {_key(r): r for r in pre_audit}

    print('\n[1] Target keys match the P13 input...')
    # After apply, audit should match target on the 33 changed keys.
    # Find which keys differ from target — should be 0.
    diffs_from_target: list[tuple] = []
    for k in target_by_key:
        diffs = {f for f in APPLY_FIELDS
                 if (audit_by_key[k].get(f) or '') != (target_by_key[k].get(f) or '')}
        if diffs:
            diffs_from_target.append((k, diffs))
    if diffs_from_target:
        for k, diffs in diffs_from_target[:5]:
            failures.append(f'{k} differs from target on: {diffs}')
        failures.append(f'{len(diffs_from_target)} keys differ from P13 target')
    else:
        print(f'  [OK] audit fully matches P13 target on all 2487 rows')

    # Compute the 33 target keys (rows that changed vs pre-apply).
    target_keys: list[tuple[str, str, str]] = []
    for k in pre_by_key:
        diffs = {f for f in APPLY_FIELDS
                 if (pre_by_key[k].get(f) or '') != (audit_by_key[k].get(f) or '')}
        if diffs:
            target_keys.append(k)
    if len(target_keys) != EXPECTED_CHANGE_COUNT:
        failures.append(
            f'changed count vs pre-apply is {len(target_keys)} '
            f'(expected {EXPECTED_CHANGE_COUNT})'
        )
    else:
        print(f'  [OK] exactly {EXPECTED_CHANGE_COUNT} rows changed vs pre-apply')

    print('\n[2] No non-target rows changed vs pre-apply...')
    drift_keys: list[tuple] = []
    for k in pre_by_key:
        if k in target_keys:
            continue
        a = audit_by_key.get(k)
        p = pre_by_key[k]
        for fld in APPLY_FIELDS:
            if (a.get(fld) or '') != (p.get(fld) or ''):
                drift_keys.append((k, fld))
                break
    if drift_keys:
        for k, fld in drift_keys[:5]:
            failures.append(f'non-target row {k} field {fld!r} changed')
        failures.append(f'{len(drift_keys)} non-target rows changed')
    else:
        print('  [OK] 0 non-target rows changed')

    print('\n[3] Miserable final state...')
    mis = audit_by_key.get(MISERABLE_KEY)
    if mis is None:
        failures.append('miserable|adjective|B2 audit row missing')
    else:
        for fld, expected in MISERABLE_EXPECTED.items():
            actual = (mis.get(fld) or '').strip()
            if actual != expected:
                failures.append(
                    f'miserable.{fld}={actual!r} (expected {expected!r})'
                )
            else:
                print(f'  [OK] miserable.{fld}={actual!r}')

    print('\n[4] P13 metadata fixes...')
    for k, expected_rule in P13_METADATA_CHECKS.items():
        r = audit_by_key.get(k)
        if r is None:
            failures.append(f'{k} audit row missing')
            continue
        actual_rule = (r.get('rule_applied') or '').strip()
        if actual_rule != expected_rule:
            failures.append(
                f'{k} rule_applied={actual_rule!r} (expected {expected_rule!r})'
            )
        else:
            print(f'  [OK] {k} rule_applied={actual_rule!r}')

    print('\n[5] Provincial has 2 gloss chunks for 2 def_before chunks...')
    prov = audit_by_key.get(PROVINCIAL_KEY)
    if prov is None:
        failures.append(f'{PROVINCIAL_KEY} audit row missing')
    else:
        gloss = (prov.get('gloss_after') or '').strip()
        sep = (prov.get('separator') or 'none').strip()
        db = (prov.get('def_before') or '').strip()
        if sep == '|':
            gloss_chunks = [c.strip() for c in gloss.split('|')]
        elif sep == ';':
            gloss_chunks = [c.strip() for c in gloss.split(';')]
        else:
            gloss_chunks = [gloss] if gloss else []
        db_chunks = [c.strip() for c in db.split('|')]
        if len(gloss_chunks) != 2 or len(db_chunks) != 2:
            failures.append(
                f'provincial gloss chunks={len(gloss_chunks)} (sep={sep!r}) '
                f'def_before chunks={len(db_chunks)} (expected 2 each)'
            )
        else:
            print(f'  [OK] gloss chunks=2, def_before chunks=2')

    print('\n[6] TXT cells updated for changed glosses...')
    if TXT_PATH.exists():
        txt_keys: dict[tuple, str] = {}
        for line in TXT_PATH.read_text(encoding='utf-8').splitlines():
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            k = (
                parts[3].strip().lower(),
                parts[4].strip().lower(),
                parts[14].strip().upper(),
            )
            txt_keys[k] = parts[6]
        n_synced = 0
        n_deferred = 0
        for k in target_keys:
            expected = (target_by_key[k].get('gloss_after') or '').strip()
            if k in txt_keys:
                if txt_keys[k].strip() != expected:
                    failures.append(
                        f'TXT {k} def={txt_keys[k]!r} != target {expected!r}'
                    )
                else:
                    n_synced += 1
            else:
                n_deferred += 1
        print(f'  TXT synced: {n_synced}, deferred: {n_deferred}')
    else:
        print('  WARN: TXT not present')

    print('\n[7] JSONL definitions sync for changed glosses...')
    if JSONL_PATH.exists():
        jsonl_rows = _load_jsonl(JSONL_PATH)
        jsonl_by_key = {
            (r.get('word', '').strip().lower(),
             r.get('pos', '').strip().lower(),
             r.get('cefr', '').strip().upper()): r
            for r in jsonl_rows
        }
        n_synced = 0
        n_absent = 0
        for k in target_keys:
            expected = (target_by_key[k].get('gloss_after') or '').strip()
            jsonl_r = jsonl_by_key.get(k)
            if jsonl_r is None:
                n_absent += 1
                continue
            if (jsonl_r.get('definition') or '').strip() != expected:
                failures.append(
                    f'JSONL {k} definition={jsonl_r.get("definition")!r} '
                    f'!= target {expected!r}'
                )
            else:
                n_synced += 1
        print(f'  JSONL synced: {n_synced}, absent: {n_absent}')
    else:
        print('  WARN: JSONL not present')

    print()
    if failures:
        print('=' * 72)
        print(f'FAIL -- P12+P13 verifier has {len(failures)} error(s):')
        for f in failures[:30]:
            print(f'  {f}')
        if len(failures) > 30:
            print(f'  ... and {len(failures) - 30} more')
        print('=' * 72)
        return 1

    print('=' * 72)
    print(
        f'PASS -- P12+P13 verified: {len(target_keys)} rows match P13 target; '
        f'miserable + P13 metadata checks pass; TXT/JSONL synced.'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
