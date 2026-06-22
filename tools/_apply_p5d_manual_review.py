"""P5D Manual Review Apply -- v2 manual pass (post word-count-limit removal).

Reads:
  - `data/gloss_precision_phrase_p5.jsonl` (P5 ledger, 990 rows)
  - `data/manual_gloss_review_p5d_decisions.jsonl` (988 v2 decisions)

Writes (with --apply; otherwise dry-run):
  - `data/gloss_precision_phrase_p5.jsonl` (990 rows; 9 new repairs added)
  - `data/audit_full_deck_v2.jsonl` (2487 rows; 36 cells updated: 9 new +
    27 changed)
  - `English Academic Vocabulary.txt` (matching cells updated)
  - JSONL regenerated via `tools/build_notes.py` after apply

Decision source: `data/manual_gloss_review_p5d_decisions.jsonl`.

Delta logic:
  - For each (word, pos, cefr) key:
    - If v2 says `repair_gloss` AND key is currently `keep_current` in
      ledger: NEW REPAIR. Mutate audit + TXT + ledger.
    - If v2 says `repair_gloss` AND key is currently `repair_gloss` in
      ledger: GLOSS CHANGED. Compare v2 gloss to ledger `new_gloss`.
      If different, mutate audit + TXT + ledger.
    - If v2 says `keep_current` AND key is currently `repair_gloss` in
      ledger: REVERT (no v1→v2 flips expected, but code handles it).
      Revert audit + TXT + ledger to old_gloss.
    - If both keep_current: no change.

Guardrails:
  - All 988 v2 decisions must match a P5 ledger row by full guard
    (word, pos, cefr, def_before, old_gloss).
  - All 344 v2 repair glosses pass `validate_verdict` (verified at import).
  - Audit row count remains 2487 (no add/delete).
  - Deck row count remains 2450 after build_notes.
  - 8 deferred audit-only keys (`solo` seed + 7 P5B manual) remain explicit.

Run:
  python -m tools._apply_p5d_manual_review            # dry-run (default)
  python -m tools._apply_p5d_manual_review --apply    # write
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

P5_LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5d_decisions.jsonl'
AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _compute_separator_count(gloss: str) -> tuple[str, int]:
    if '|' in gloss:
        sep = '|'
    elif ';' in gloss:
        sep = ';'
    else:
        sep = 'none'
    chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
    wc = sum(len(c.split()) for c in chunks)
    return sep, wc


def _full_audit_guard(r: dict) -> tuple:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
        (r.get('rule_applied') or '').strip(),
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
    print(f'P5D Manual Review Apply (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load inputs.
    print('\n[1] Loading inputs...')
    try:
        ledger = _load_jsonl(P5_LEDGER_PATH)
        decisions = _load_jsonl(DECISIONS_PATH)
        audit_rows = _load_jsonl(AUDIT_PATH)
    except FileNotFoundError as e:
        print(f'FATAL: {e}')
        return 1
    print(f'  P5 ledger: {len(ledger)} rows')
    print(f'  P5D decisions: {len(decisions)} rows')
    print(f'  Audit: {len(audit_rows)} rows')

    # Decisions structural validation.
    print('\n[2] Validating decisions...')
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402
    errs: list[str] = []
    seen: dict[tuple, int] = {}
    for d in decisions:
        word = (d.get('word') or '').strip()
        pos = (d.get('pos') or '').strip().lower()
        cefr = (d.get('cefr') or '').strip().upper()
        decision = d.get('decision')
        new_gloss = (d.get('new_gloss') or '').strip()
        old_gloss = (d.get('old_gloss') or '').strip()
        rule_after = (d.get('rule_after') or '').strip()
        g = (
            word.lower(), pos, cefr,
            (d.get('def_before') or '').strip(), old_gloss,
        )
        seen[g] = seen.get(g, 0) + 1
        if decision == 'keep_current':
            if new_gloss:
                errs.append(f'  ({word}, {pos}, {cefr}) keep but new_gloss={new_gloss!r}')
            if rule_after:
                errs.append(f'  ({word}, {pos}, {cefr}) keep but rule_after={rule_after!r}')
        elif decision == 'repair_gloss':
            if not new_gloss:
                errs.append(f'  ({word}, {pos}, {cefr}) repair but new_gloss empty')
                continue
            if rule_after != 'precision_phrase':
                errs.append(f'  ({word}, {pos}, {cefr}) repair but rule_after={rule_after!r}')
            sep = d.get('separator', '')
            chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', new_gloss) if c.strip()]
            v = validate_verdict(word, new_gloss, sep, len(chunks))
            if v:
                errs.append(f'  ({word}, {pos}, {cefr}) new_gloss={new_gloss!r} fails validator: {v}')
    dups = [g for g, n in seen.items() if n > 1]
    if dups:
        errs.append(f'  {len(dups)} duplicate decision guards')
    if errs:
        print('FATAL: decisions validation failed:')
        for e in errs[:20]:
            print(e)
        return 1
    n_repair = sum(1 for d in decisions if d['decision'] == 'repair_gloss')
    n_keep = sum(1 for d in decisions if d['decision'] == 'keep_current')
    print(f'  All {len(decisions)} decisions valid ({n_repair} repair + {n_keep} keep)')

    # Build index: decisions by guard.
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

    # Index P5 ledger by guard.
    ledger_by_guard: dict[tuple, dict] = {}
    for row in ledger:
        if row.get('decision') in ('repair_gloss', 'keep_current'):
            g = (
                (row.get('word') or '').strip().lower(),
                (row.get('pos') or '').strip().lower(),
                (row.get('cefr') or '').strip().upper(),
                (row.get('def_before') or '').strip(),
                (row.get('old_gloss') or '').strip(),
            )
            ledger_by_guard[g] = row

    # Compute deltas.
    print('\n[3] Computing deltas (v2 decisions vs current P5 ledger state)...')
    new_repairs: list[tuple[str, str, str]] = []  # v1=keep, v2=repair
    changed_repairs: list[tuple[str, str, str]] = []  # both repair, gloss differs
    unchanged_repairs: list[tuple[str, str, str]] = []
    reverted_to_keep: list[tuple[str, str, str]] = []
    unchanged_keeps: list[tuple[str, str, str]] = []

    for g, d in dec_by_guard.items():
        word, pos, cefr, _, _ = g
        k = (word, pos, cefr)
        cur = ledger_by_guard.get(g)
        if cur is None:
            print(f'FATAL: no ledger row for decision guard {k}')
            return 1
        cur_decision = cur.get('decision')
        cur_new_gloss = (cur.get('new_gloss') or '').strip()

        if d['decision'] == 'repair_gloss':
            v2_gloss = d['new_gloss']
            if cur_decision == 'keep_current':
                new_repairs.append(k)
            elif cur_decision == 'repair_gloss':
                if v2_gloss != cur_new_gloss:
                    changed_repairs.append(k)
                else:
                    unchanged_repairs.append(k)
        elif d['decision'] == 'keep_current':
            if cur_decision == 'repair_gloss':
                reverted_to_keep.append(k)
            else:
                unchanged_keeps.append(k)

    print(f'  new_repairs: {len(new_repairs)}')
    print(f'  changed_repairs (gloss differs): {len(changed_repairs)}')
    print(f'  unchanged_repairs: {len(unchanged_repairs)}')
    print(f'  reverted_to_keep: {len(reverted_to_keep)}')
    print(f'  unchanged_keeps: {len(unchanged_keeps)}')

    audit_changes_total = len(new_repairs) + len(changed_repairs) + len(reverted_to_keep)
    print(f'  TOTAL audit/TXT mutations: {audit_changes_total}')

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # Build new ledger.
    print('\n[4] Building new ledger...')
    new_ledger: list[dict] = []
    n_ledger_updated = 0
    for row in ledger:
        if row.get('decision') not in ('repair_gloss', 'keep_current'):
            new_ledger.append(row)
            continue
        g = (
            (row.get('word') or '').strip().lower(),
            (row.get('pos') or '').strip().lower(),
            (row.get('cefr') or '').strip().upper(),
            (row.get('def_before') or '').strip(),
            (row.get('old_gloss') or '').strip(),
        )
        d = dec_by_guard.get(g)
        if d is None:
            new_ledger.append(row)
            continue
        new_row = dict(row)
        new_row['decision'] = d['decision']
        new_row['manual_decision'] = d['decision']
        if d['decision'] == 'repair_gloss':
            new_row['new_gloss'] = d['new_gloss']
            new_row['rule_after'] = d['rule_after']
            new_row['separator'] = d['separator']
            new_row['gloss_word_count'] = d['gloss_word_count']
            new_row['manual_notes'] = d.get('notes', '')
            new_row['p5d_version'] = '2026-06-22'
        else:
            new_row['new_gloss'] = None
            new_row['rule_after'] = None
            new_row['separator'] = 'none'
            new_row['gloss_word_count'] = 0
            new_row['manual_notes'] = d.get('notes', '')
            new_row['p5d_version'] = '2026-06-22'
        new_ledger.append(new_row)
        n_ledger_updated += 1
    n_ledger_repair = sum(1 for r in new_ledger if r['decision'] == 'repair_gloss')
    n_ledger_keep = sum(1 for r in new_ledger if r['decision'] == 'keep_current')
    print(f'  Updated {n_ledger_updated} ledger rows')
    print(f'  New distribution: {n_ledger_repair} repair + {n_ledger_keep} keep + 0 review = {len(new_ledger)} total')

    # Build new audit + TXT.
    print('\n[5] Building new audit + TXT...')

    # Build a quick key -> ledger-row index (for guard lookup).
    ledger_by_key: dict[tuple, dict] = {}
    for row in ledger:
        if row.get('decision') in ('repair_gloss', 'keep_current'):
            k = (
                (row.get('word') or '').strip().lower(),
                (row.get('pos') or '').strip().lower(),
                (row.get('cefr') or '').strip().upper(),
            )
            ledger_by_key.setdefault(k, row)

    # Compute audit updates.
    audit_updates: dict[tuple, dict] = {}  # (word,pos,cefr) -> new audit row fields
    for k in new_repairs + changed_repairs:
        # Find the decision row for this key (any def_before/old_gloss match).
        d = None
        for g, dec in dec_by_guard.items():
            if (g[0], g[1], g[2]) == k:
                d = dec
                break
        if d is None:
            print(f'FATAL: no decision for key {k}')
            return 1
        audit_updates[k] = {
            'gloss_after': d['new_gloss'],
            'rule_applied': d['rule_after'],
            'separator': d['separator'],
            'gloss_word_count': d['gloss_word_count'],
            'gate_status': 'pass',
            'fix_status': 'p5d_manual_review_repaired',
            'loop_type': d.get('loop_type', ''),
        }
    # Reverts (v2=keep but current state is repair): restore old_gloss.
    for k in reverted_to_keep:
        cur = ledger_by_key.get(k)
        if cur is None:
            print(f'FATAL: no ledger row for revert key {k}')
            return 1
        old_gloss = (cur.get('old_gloss') or '').strip()
        rule_applied = (cur.get('rule_applied') or '').strip()
        sep, wc = _compute_separator_count(old_gloss)
        audit_updates[k] = {
            'gloss_after': old_gloss,
            'rule_applied': rule_applied,
            'separator': sep,
            'gloss_word_count': wc,
            'gate_status': 'pass',
            'fix_status': 'p5d_reverted_to_keep',
            'loop_type': '',
        }

    # Apply audit updates.
    n_audit_changed = 0
    new_audit = []
    for r in audit_rows:
        k = (
            (r.get('word') or '').strip().lower(),
            (r.get('pos') or '').strip().lower(),
            (r.get('cefr') or '').strip().upper(),
        )
        if k in audit_updates:
            new_r = dict(r)
            for f, v in audit_updates[k].items():
                new_r[f] = v
            new_audit.append(new_r)
            n_audit_changed += 1
        else:
            new_audit.append(r)
    if len(new_audit) != len(audit_rows):
        print(f'FATAL: audit row count drift {len(audit_rows)} -> {len(new_audit)}')
        return 1
    print(f'  Audit rows updated: {n_audit_changed}')

    # Apply TXT updates.
    txt_keys_to_update: dict[tuple, str] = {}
    for k in new_repairs + changed_repairs + reverted_to_keep:
        if k in audit_updates:
            txt_keys_to_update[k] = audit_updates[k]['gloss_after']
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
        if k in txt_keys_to_update:
            parts[6] = txt_keys_to_update[k]
            new_lines.append('\t'.join(parts))
            n_txt_replaced += 1
        else:
            new_lines.append(line)
    n_txt_skipped = sum(1 for k in txt_keys_to_update if k not in seen_keys)
    print(f'  TXT cells replaced: {n_txt_replaced}; deferred (no TXT row): {n_txt_skipped}')

    # Write files.
    print('\n[6] Writing changes...')
    audit_bak = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f'.bak_pre_p5d_manual_review_{_ts()}')
    txt_bak = TXT_PATH.with_suffix(TXT_PATH.suffix + f'.bak_pre_p5d_manual_review_{_ts()}')
    ledger_bak = P5_LEDGER_PATH.with_suffix(P5_LEDGER_PATH.suffix + f'.bak_pre_p5d_{_ts()}')
    audit_bak.write_text(AUDIT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    txt_bak.write_text(TXT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    ledger_bak.write_text(P5_LEDGER_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'  Audit backup:  {audit_bak.name}')
    print(f'  TXT backup:    {txt_bak.name}')
    print(f'  Ledger backup: {ledger_bak.name}')

    AUDIT_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_audit) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote audit:   {AUDIT_PATH.name} ({len(new_audit)} rows)')

    TXT_PATH.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    print(f'  Wrote TXT:     {TXT_PATH.name}')

    P5_LEDGER_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_ledger) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote ledger:  {P5_LEDGER_PATH.name} ({len(new_ledger)} rows)')

    print('\nDone. Run `python -m tools.build_notes` to regenerate JSONL.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
