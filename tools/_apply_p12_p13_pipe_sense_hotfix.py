"""P12 + P13: Equivalent-sense + pipe/sense hotfix -- guarded apply.

Reads:
  - `C:\\Users\\admin\\Downloads\\audit_full_deck_v2_p13_pipe_sense_hotfix.jsonl`
    (target values; expected 33 rows differ vs current audit)
  - `data/audit_full_deck_v2.jsonl` (current state, 2487 rows)

Writes (with --apply; otherwise dry-run):
  - `data/audit_full_deck_v2.jsonl` (2487 rows; exactly 33 updated)
  - `English Academic Vocabulary.txt` (cells updated for matching rows)
  - `data/anki_notes.jsonl` (rebuilt via `tools/build_notes` after apply)

Scope (per P12+P13 plan):
  - The patch is a SCOPED 33-key update, not a wholesale file replacement.
  - For each of the 33 target keys, apply ALL changed fields from the
    patch row (gloss_after, separator, rule_applied, gloss_word_count,
    fix_status, gate_status). def_before is preserved (already matches).
  - Lock expected count to 33 keys.
  - Preserve row order and row count (2487).

Run:
  python -m tools._apply_p12_p13_pipe_sense_hotfix            # dry-run
  python -m tools._apply_p12_p13_pipe_sense_hotfix --apply    # write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
JSONL_PATH = PROJECT_ROOT / 'data' / 'anki_notes.jsonl'
INPUT_PATH = Path(r"C:\Users\admin\Downloads\audit_full_deck_v2_p13_pipe_sense_hotfix.jsonl")

EXPECTED_CHANGE_COUNT = 33

# Fields we apply from the patch row when they differ.
APPLY_FIELDS = (
    'def_before', 'gloss_after', 'separator', 'rule_applied',
    'gloss_word_count', 'fix_status', 'gate_status',
)


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _key(r: dict) -> tuple[str, str, str]:
    return (
        r['word'].strip().lower(),
        r['pos'].strip().lower(),
        r['cefr'].strip().upper(),
    )


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P12+P13 pipe/sense hotfix (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    cur = _load_jsonl(AUDIT_PATH)
    new = _load_jsonl(INPUT_PATH)
    print(f'\n  Current audit: {len(cur)} rows')
    print(f'  P13 input:     {len(new)} rows')

    if len(cur) != 2487:
        print(f'FATAL: current audit has {len(cur)} rows (expected 2487)')
        return 1
    if len(new) != 2487:
        print(f'FATAL: P13 input has {len(new)} rows (expected 2487)')
        return 1

    cur_by_key = {_key(r): r for r in cur}
    new_by_key = {_key(r): r for r in new}
    if set(cur_by_key) != set(new_by_key):
        only_cur = set(cur_by_key) - set(new_by_key)
        only_new = set(new_by_key) - set(cur_by_key)
        if only_cur:
            print(f'FATAL: {len(only_cur)} keys only in current audit')
        if only_new:
            print(f'FATAL: {len(only_new)} keys only in P13 input')
        return 1

    # Find the 33 target keys.
    target_keys: list[tuple[str, str, str]] = []
    unmatched: list[tuple[str, str, str]] = []
    for k in cur_by_key:
        c = cur_by_key[k]
        n = new_by_key[k]
        diffs = {f for f in APPLY_FIELDS if (c.get(f) or '') != (n.get(f) or '')}
        if diffs:
            target_keys.append(k)
    print(f'\n[1] Target keys (differ from current): {len(target_keys)}')
    if len(target_keys) != EXPECTED_CHANGE_COUNT:
        print(f'FATAL: target count is {len(target_keys)} '
              f'(expected {EXPECTED_CHANGE_COUNT})')
        return 1
    print(f'  [OK] exactly {EXPECTED_CHANGE_COUNT} target keys')

    # Validate each target: def_before must already match.
    print('\n[2] Validating def_before preservation...')
    for k in target_keys:
        c = cur_by_key[k]
        n = new_by_key[k]
        if (c.get('def_before') or '') != (n.get('def_before') or ''):
            print(f'FATAL: {k} def_before differs (P12/P13 must preserve)')
            return 1
    print(f'  [OK] all 33 def_before values already match')

    # Validate every changed gloss passes validate_verdict (post-P5D).
    print('\n[3] Validating changed glosses...')
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402
    failures: list[str] = []
    for k in target_keys:
        n = new_by_key[k]
        gloss = (n.get('gloss_after') or '').strip()
        sep = (n.get('separator') or 'none').strip()
        wc = n.get('gloss_word_count', 0) or 0
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        actual_wc = sum(len(c.split()) for c in chunks)
        if actual_wc != wc:
            failures.append(
                f'{k} gloss_word_count={wc} != actual {actual_wc} (gloss={gloss!r})'
            )
        v = validate_verdict(n['word'], gloss, sep, len(chunks))
        if v:
            failures.append(f'{k} gloss={gloss!r} fails validator: {v}')
    if failures:
        for f in failures[:20]:
            print(f'  {f}')
        print(f'FATAL: {len(failures)} gloss validation failures')
        return 1
    print(f'  [OK] all 33 changed glosses validated')

    # Build new audit.
    print('\n[4] Building new audit...')
    target_set = set(target_keys)
    new_audit: list[dict] = []
    replaced = 0
    for r in cur:
        k = _key(r)
        if k not in target_set:
            new_audit.append(r)
            continue
        new_r = dict(r)
        patch = new_by_key[k]
        for fld in APPLY_FIELDS:
            if fld in patch:
                new_r[fld] = patch[fld]
        new_audit.append(new_r)
        replaced += 1
    if replaced != EXPECTED_CHANGE_COUNT:
        print(f'FATAL: replaced {replaced} (expected {EXPECTED_CHANGE_COUNT})')
        return 1
    print(f'  Replaced {replaced} rows')

    # Update TXT (parts[6] = gloss def).
    print('\n[5] Updating TXT...')
    target_glosses: dict[tuple, str] = {
        k: (new_by_key[k].get('gloss_after') or '') for k in target_keys
    }
    lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
    new_lines: list[str] = []
    n_txt_replaced = 0
    seen_keys: set[tuple] = set()
    deferred: list[tuple] = []
    for line in lines:
        if line.startswith('#') or not line.strip():
            new_lines.append(line)
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            new_lines.append(line)
            continue
        k = (
            parts[3].strip().lower(),
            parts[4].strip().lower(),
            parts[14].strip().upper(),
        )
        seen_keys.add(k)
        if k in target_glosses:
            parts[6] = target_glosses[k]
            n_txt_replaced += 1
            new_lines.append('\t'.join(parts))
        else:
            new_lines.append(line)
    for k in target_glosses:
        if k not in seen_keys:
            deferred.append(k)
    print(f'  TXT cells replaced: {n_txt_replaced}')
    print(f'  Deferred: {len(deferred)}')
    for k in deferred:
        print(f'    {k}')

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # === Apply ===
    print('\n[6] Writing changes...')
    audit_bak = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f'.bak_pre_p12_p13_{_ts()}')
    txt_bak = TXT_PATH.with_suffix(TXT_PATH.suffix + f'.bak_pre_p12_p13_{_ts()}')
    audit_bak.write_bytes(AUDIT_PATH.read_bytes())
    txt_bak.write_bytes(TXT_PATH.read_bytes())
    print(f'  Audit backup: {audit_bak.name}')
    print(f'  TXT backup:   {txt_bak.name}')

    AUDIT_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_audit) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote audit:  {AUDIT_PATH.name} ({len(new_audit)} rows)')

    TXT_PATH.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    print(f'  Wrote TXT:    {TXT_PATH.name}')

    print('\nDone. Run `python -m tools.build_notes` to regenerate JSONL.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
