"""Build P8 convention/hotfix decisions from input vs current diff.

Reads:
  - `data/audit_full_deck_v2.jsonl` (current state)
  - `C:\\Users\\admin\\Downloads\\audit_full_deck_v2_convention_patched_semantic_hotfix_v2.jsonl` (P8 input)

Writes:
  - `data/convention_p8_decisions.jsonl` — one row per (word, pos, cefr) where
    any field differs.

Apply is guarded by 5-element key:
  (word, pos, cefr, current def_before, current gloss_after)

Special cases:
  - `miserable|adjective|B2`: Oxford source correction. def_before uses `;`
    between two B2 senses (which is a list-of-senses separator), but the
    project's def_before convention for multi-sense is `|`. Apply overrides
    def_before to use `|`.

Run:
  python -m tools._build_p8_decisions
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

INPUT_PATH = Path(r"C:\Users\admin\Downloads\audit_full_deck_v2_convention_patched_semantic_hotfix_v2.jsonl")
CURRENT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
OUTPUT_PATH = PROJECT_ROOT / 'data' / 'convention_p8_decisions.jsonl'

# Miscrable hotfix: Oxford has two B2 senses; def_before separator must be `|`.
MISERABLE_KEY = ('miserable', 'adjective', 'B2')
MISERABLE_NEW_DEF_BEFORE = (
    'very unhappy or uncomfortable|making you feel very unhappy or uncomfortable'
)


def _key(r: dict) -> tuple[str, str, str]:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
    )


def _cur_guard(r: dict) -> tuple:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
        (r.get('def_before') or '').strip(),
        (r.get('gloss_after') or '').strip(),
    )


def _differs(cur: dict, new: dict) -> bool:
    fields = ['def_before', 'gloss_after', 'separator', 'rule_applied',
              'gloss_word_count', 'fix_status', 'gate_status']
    return any((cur.get(f) or '') != (new.get(f) or '') for f in fields)


def main() -> int:
    print('=' * 72)
    print('P8 Convention + Hotfix Decisions Builder')
    print('=' * 72)

    if not INPUT_PATH.exists():
        print(f'FATAL: input not found: {INPUT_PATH}')
        return 1

    cur_rows = [json.loads(l) for l in CURRENT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
    new_rows = [json.loads(l) for l in INPUT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]

    cur_by_key = {_key(r): r for r in cur_rows}
    new_by_key = {_key(r): r for r in new_rows}

    if set(cur_by_key) != set(new_by_key):
        only_cur = set(cur_by_key) - set(new_by_key)
        only_new = set(new_by_key) - set(cur_by_key)
        if only_cur:
            print(f'FATAL: {len(only_cur)} keys only in current audit (sample): {list(only_cur)[:3]}')
            return 1
        if only_new:
            print(f'FATAL: {len(only_new)} keys only in input (sample): {list(only_new)[:3]}')
            return 1

    print(f'Current audit: {len(cur_rows)} rows')
    print(f'Input: {len(new_rows)} rows')

    decisions: list[dict] = []
    matched = 0
    p6_drift = 0
    p7_drift = 0
    mismatched = 0

    for k in sorted(cur_by_key.keys()):
        cur = cur_by_key[k]
        new = new_by_key[k]
        if not _differs(cur, new):
            continue
        # Guard: 5-element key
        guard = _cur_guard(cur)
        # Special case: miserable
        if k == MISERABLE_KEY:
            new_def_before = MISERABLE_NEW_DEF_BEFORE
        else:
            new_def_before = (new.get('def_before') or '').strip()
        d = {
            'word': cur['word'],
            'pos': cur['pos'],
            'cefr': cur['cefr'],
            'def_before_old': cur.get('def_before', ''),
            'def_before_new': new_def_before,
            'gloss_before': cur.get('gloss_after', ''),
            'gloss_after': new.get('gloss_after', ''),
            'rule_before': cur.get('rule_applied'),
            'rule_after': new.get('rule_applied'),
            'separator': new.get('separator', 'none'),
            'gloss_word_count': new.get('gloss_word_count', 0),
            'gate_status': new.get('gate_status', 'pass'),
            'fix_status': new.get('fix_status', 'p9_convention_repaired'),
            'fix_status_old': cur.get('fix_status', ''),
            'source': new.get('source', ''),
            'review_needed': new.get('review_needed'),
            'review_reason': new.get('review_reason'),
            'guard_word': guard[0],
            'guard_pos': guard[1],
            'guard_cefr': guard[2],
            'guard_def_before': guard[3],
            'guard_gloss_after': guard[4],
            'p8_version': '2026-06-23',
        }
        decisions.append(d)
        # Classify drift type for stats
        cur_fix = (cur.get('fix_status') or '').strip()
        if cur_fix == 'p6_multisense_harddrop_repaired':
            p6_drift += 1
        elif cur_fix == 'p7_redundant_sense_trimmed':
            p7_drift += 1
        matched += 1

    # Stats
    print(f'\nDiffering rows: {len(decisions)}')
    print(f'  P6-superseded (was p6_multisense_harddrop_repaired): {p6_drift}')
    print(f'  P7-superseded (was p7_redundant_sense_trimmed): {p7_drift}')

    rule_dest = {}
    for d in decisions:
        key = (d.get('rule_before') or 'NULL', d.get('rule_after') or 'NULL')
        rule_dest[key] = rule_dest.get(key, 0) + 1
    print('\nRule migrations:')
    for (old, new), n in sorted(rule_dest.items(), key=lambda x: -x[1]):
        print(f'  {old!r} -> {new!r}: {n}')

    fix_dest = {}
    for d in decisions:
        key = (d.get('fix_status_old') or 'NULL', d.get('fix_status') or 'NULL')
        fix_dest[key] = fix_dest.get(key, 0) + 1
    print('\nFix-status transitions:')
    for (old, new), n in sorted(fix_dest.items(), key=lambda x: -x[1]):
        print(f'  {old!r} -> {new!r}: {n}')

    OUTPUT_PATH.write_text(
        '\n'.join(json.dumps(d, ensure_ascii=False) for d in decisions) + '\n',
        encoding='utf-8',
    )
    print(f'\nWrote {len(decisions)} decisions to: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
