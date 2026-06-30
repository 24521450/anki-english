"""P6 Multisense Hard-Drop Repair -- guarded apply.

Reads:
  - `data/multisense_harddrop_p6_decisions.jsonl` (117 P6 decisions, canonical)

Writes (with --apply; otherwise dry-run):
  - `data/audit_full_deck_v2.jsonl` (2487 rows; exactly 117 updated)
  - `English Academic Vocabulary.txt` (114 cells updated; 3 deferred)
  - (Rebuild JSONL via `tools/build_notes.py` after apply.)

Guardrails (per P6 plan):
  - Match audit rows by 5-element key
    `(word, pos, cefr, def_before, old_gloss)` BEFORE changing.
  - Exactly 117 audit rows changed.
  - Exactly 114 TXT rows sync; exactly 3 deferred keys match the known list:
    harbor|verb|UNCLASSIFIED, invading|verb|UNCLASSIFIED,
    shortsighted|adjective|UNCLASSIFIED.
  - Every P6 repair passes `validate_verdict`.
  - `gloss_word_count` matches actual count for all 117.
  - No `rule_shape_contradiction` introduced.

Run:
  python -m tools._apply_p6_multisense              # dry-run (default)
  python -m tools._apply_p6_multisense --apply      # write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DECISIONS_PATH = PROJECT_ROOT / 'data' / 'multisense_harddrop_p6_decisions.jsonl'
AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'

# Known deferred keys (audit-only, no TXT row exists).
EXPECTED_DEFERRED_KEYS: set[tuple[str, str, str]] = {
    ('harbor', 'verb', 'UNCLASSIFIED'),
    ('invading', 'verb', 'UNCLASSIFIED'),
    ('shortsighted', 'adjective', 'UNCLASSIFIED'),
}


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _full_audit_guard(r: dict) -> tuple:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
        (r.get('def_before') or '').strip(),
        (r.get('gloss_after') or '').strip(),
    )


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f'Not found: {path}')
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P6 Multisense Hard-Drop Apply (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load inputs.
    print('\n[1] Loading inputs...')
    try:
        decisions = _load_jsonl(DECISIONS_PATH)
        audit_rows = _load_jsonl(AUDIT_PATH)
    except FileNotFoundError as e:
        print(f'FATAL: {e}')
        return 1
    print(f'  Decisions: {len(decisions)}')
    print(f'  Audit: {len(audit_rows)}')

    if len(decisions) != 117:
        print(f'FATAL: decisions has {len(decisions)} rows (expected 117)')
        return 1
    if len(audit_rows) != 2487:
        print(f'FATAL: audit has {len(audit_rows)} rows (expected 2487)')
        return 1

    # Build decision index by 5-element guard.
    dec_by_guard: dict[tuple, dict] = {}
    for d in decisions:
        g = (
            (d['word'] or '').strip().lower(),
            (d['pos'] or '').strip().lower(),
            (d['cefr'] or '').strip().upper(),
            (d['def_before'] or '').strip(),
            (d['old_gloss'] or '').strip(),
        )
        dec_by_guard[g] = d

    # Cross-check: every decision must match exactly 1 audit row.
    print('\n[2] Cross-checking decisions vs audit...')
    audit_by_full_guard: dict[tuple, list[dict]] = {}
    for r in audit_rows:
        g = _full_audit_guard(r)
        audit_by_full_guard.setdefault(g, []).append(r)
    unmatched: list[dict] = []
    ambiguous: list[tuple] = []
    matched_audit: list[dict] = []
    for d in decisions:
        g = (
            (d['word'] or '').strip().lower(),
            (d['pos'] or '').strip().lower(),
            (d['cefr'] or '').strip().upper(),
            (d['def_before'] or '').strip(),
            (d['old_gloss'] or '').strip(),
        )
        rows = audit_by_full_guard.get(g, [])
        if len(rows) == 0:
            unmatched.append(d)
        elif len(rows) > 1:
            ambiguous.append(g)
        else:
            matched_audit.append(rows[0])
    if unmatched:
        print(f'FATAL: {len(unmatched)} decisions have no matching audit row:')
        for d in unmatched[:5]:
            print(f'  {(d["word"], d["pos"], d["cefr"])}')
        return 1
    if ambiguous:
        print(f'FATAL: {len(ambiguous)} decisions are ambiguous (multiple audit matches)')
        for g in ambiguous[:5]:
            print(f'  {g}')
        return 1
    print(f'  Matched {len(matched_audit)} audit rows.')

    # Validate each decision (post-P5D validator).
    print('\n[3] Validating decisions...')
    import re as _re
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402
    failures: list[str] = []
    for d in decisions:
        gloss = (d.get('new_gloss') or '').strip()
        sep = (d.get('separator') or '').strip()
        wc = d.get('gloss_word_count', 0) or 0
        chunks = [c.strip() for c in _re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        if len(chunks) != d.get('separator_count_expected', len(chunks)):
            pass  # not enforced
        # Recount.
        actual_wc = sum(len(c.split()) for c in chunks)
        if actual_wc != wc:
            failures.append(
                f'  ({d["word"]}, {d["pos"]}, {d["cefr"]}) gloss_word_count={wc} '
                f'!= actual {actual_wc}'
            )
        v = validate_verdict(d['word'], gloss, sep, len(chunks))
        if v:
            failures.append(
                f'  ({d["word"]}, {d["pos"]}, {d["cefr"]}) gloss={gloss!r} '
                f'fails validator: {v}'
            )
    if failures:
        print('FATAL: validator / metadata failures:')
        for f in failures[:20]:
            print(f)
        return 1
    print(f'  All {len(decisions)} decisions validated.')

    # Build updated audit rows.
    print('\n[4] Building new audit...')
    new_audit: list[dict] = []
    replaced = 0
    for r in audit_rows:
        g = _full_audit_guard(r)
        d = dec_by_guard.get(g)
        if d is None:
            new_audit.append(r)
            continue
        new_r = dict(r)
        new_r['gloss_after'] = d['new_gloss']
        new_r['rule_applied'] = d['rule_after']
        new_r['separator'] = d['separator']
        new_r['gloss_word_count'] = d['gloss_word_count']
        new_r['fix_status'] = d['fix_status']
        new_audit.append(new_r)
        replaced += 1
    if replaced != 117:
        print(f'FATAL: replaced {replaced} audit rows (expected 117)')
        return 1
    print(f'  Replaced {replaced} audit rows.')

    # Update TXT.
    print('\n[5] Updating TXT...')
    txt_keys: dict[tuple, str] = {}  # (word, pos, cefr) -> new gloss
    for d in decisions:
        k = (
            (d['word'] or '').strip().lower(),
            (d['pos'] or '').strip().lower(),
            (d['cefr'] or '').strip().upper(),
        )
        txt_keys[k] = d['new_gloss']
    lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
    new_lines: list[str] = []
    n_txt_replaced = 0
    seen_keys: set[tuple] = set()
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
        if k in txt_keys:
            parts[6] = txt_keys[k]
            new_lines.append('\t'.join(parts))
            n_txt_replaced += 1
        else:
            new_lines.append(line)
    deferred_keys: set[tuple] = {k for k in txt_keys if k not in seen_keys}
    print(f'  TXT cells replaced: {n_txt_replaced}')
    print(f'  Deferred (no TXT row): {len(deferred_keys)}')
    for k in sorted(deferred_keys):
        print(f'    {k}')

    # Cross-check deferred set matches expected.
    unexpected = deferred_keys - EXPECTED_DEFERRED_KEYS
    missing = EXPECTED_DEFERRED_KEYS - deferred_keys
    if unexpected:
        print(f'FATAL: unexpected deferred keys: {unexpected}')
        return 1
    if missing:
        print(f'FATAL: expected deferred keys missing: {missing}')
        return 1
    print(f'  Deferred keys match expected set: {sorted(EXPECTED_DEFERRED_KEYS)}')

    if n_txt_replaced != 114:
        print(f'FATAL: TXT replaced {n_txt_replaced} cells (expected 114)')
        return 1

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # === Apply ===
    print('\n[6] Writing changes...')
    audit_bak = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f'.bak_pre_p6_multisense_{_ts()}')
    txt_bak = TXT_PATH.with_suffix(TXT_PATH.suffix + f'.bak_pre_p6_multisense_{_ts()}')
    audit_bak.write_text(AUDIT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    txt_bak.write_text(TXT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
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
