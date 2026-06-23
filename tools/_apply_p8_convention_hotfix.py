"""P8 Convention Taxonomy + Miserable Hotfix -- guarded apply.

Reads:
  - `data/convention_p8_decisions.jsonl` (457 P8 decisions built from input diff)

Writes (with --apply; otherwise dry-run):
  - `data/audit_full_deck_v2.jsonl` (2487 rows; exactly 457 updated)
  - `English Academic Vocabulary.txt` (cells updated for matching rows)

Guardrails (per P8 plan):
  - Match audit rows by 5-element guard
    `(word, pos, cefr, current def_before, current gloss_after)`.
  - Exactly 457 audit rows changed.
  - All 457 decisions' `gloss_after` passes `validate_verdict`.
  - All 457 decisions' `gloss_word_count` matches actual count.
  - rule_after in NEW convention taxonomy (no deprecated `precision_phrase` /
    `multi_sense_distinct` in changed rows).
  - `_with_facet` rows carry `review_needed: true`.
  - `miserable.def_before` exactly contains `|` (Oxford source correction).
  - Audit row count preserved at 2487.

Run:
  python -m tools._apply_p8_convention_hotfix            # dry-run (default)
  python -m tools._apply_p8_convention_hotfix --apply    # write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DECISIONS_PATH = PROJECT_ROOT / 'data' / 'convention_p8_decisions.jsonl'
AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'


# Allowed new taxonomy rules (post-P8 migration).
NEW_TAXONOMY = {
    'word_gloss', 'phrase_gloss', 'facet_phrase',
    '2sense_distinct', '3sense_distinct',
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
    '4sense_distinct', '5sense_distinct',
    'common_core_trimmed', 'trimmed_multisense',
    'rule_b_pick1', 'rule_b_pick2', 'rule_b_pick2_addendum',
    'multi_pos_pick1', 'multi_pos_pick2',
    'concrete_1sense', 'safety_net',
    '2sense_samedomain', 'pos_aware_gloss',
    'POS_DEF_MISMATCH_fixed', 'B', 'concise_def_skip',
    '',  # no rule
}

DEPRECATED_IN_CHANGED_ROWS = {'precision_phrase', 'multi_sense_distinct'}

WITH_FACET_RULES = {
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
}


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _cur_guard(r: dict) -> tuple:
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
    print(f'P8 Convention + Hotfix Apply (apply={args.apply})')
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
    print(f'  Audit:     {len(audit_rows)}')

    if len(decisions) != 457:
        print(f'FATAL: decisions has {len(decisions)} rows (expected 457)')
        return 1
    if len(audit_rows) != 2487:
        print(f'FATAL: audit has {len(audit_rows)} rows (expected 2487)')
        return 1

    # Build decision index by 5-element guard.
    dec_by_guard: dict[tuple, dict] = {}
    for d in decisions:
        g = (
            d['guard_word'],
            d['guard_pos'],
            d['guard_cefr'],
            d['guard_def_before'],
            d['guard_gloss_after'],
        )
        dec_by_guard[g] = d

    # Cross-check: every decision must match exactly 1 audit row.
    print('\n[2] Cross-checking decisions vs audit...')
    audit_by_full_guard: dict[tuple, list[dict]] = {}
    for r in audit_rows:
        g = _cur_guard(r)
        audit_by_full_guard.setdefault(g, []).append(r)
    unmatched: list[dict] = []
    ambiguous: list[tuple] = []
    matched_audit: list[dict] = []
    for d in decisions:
        g = (
            d['guard_word'], d['guard_pos'], d['guard_cefr'],
            d['guard_def_before'], d['guard_gloss_after'],
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
            print(f'  ({d["word"]}, {d["pos"]}, {d["cefr"]})')
        return 1
    if ambiguous:
        print(f'FATAL: {len(ambiguous)} decisions are ambiguous (multiple audit matches)')
        for g in ambiguous[:5]:
            print(f'  {g}')
        return 1
    print(f'  Matched {len(matched_audit)} audit rows.')

    # Validate each decision.
    print('\n[3] Validating decisions...')
    import re as _re
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402
    failures: list[str] = []
    for d in decisions:
        gloss = (d.get('gloss_after') or '').strip()
        sep = (d.get('separator') or 'none').strip()
        wc = d.get('gloss_word_count', 0) or 0
        chunks = [c.strip() for c in _re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        actual_wc = sum(len(c.split()) for c in chunks)
        if actual_wc != wc:
            failures.append(
                f'  ({d["word"]}, {d["pos"]}, {d["cefr"]}) gloss_word_count={wc} '
                f'!= actual {actual_wc} (gloss={gloss!r})'
            )
        v = validate_verdict(d['word'], gloss, sep, len(chunks))
        if v:
            failures.append(
                f'  ({d["word"]}, {d["pos"]}, {d["cefr"]}) gloss={gloss!r} '
                f'fails validator: {v}'
            )
        rule_after = d.get('rule_after')
        if rule_after not in NEW_TAXONOMY:
            failures.append(
                f'  ({d["word"]}, {d["pos"]}, {d["cefr"]}) rule_after={rule_after!r} '
                f'not in P8 taxonomy'
            )
        # _with_facet rows must carry review_needed: true
        if rule_after in WITH_FACET_RULES and not d.get('review_needed'):
            failures.append(
                f'  ({d["word"]}, {d["pos"]}, {d["cefr"]}) rule={rule_after!r} '
                f'requires review_needed: true (got {d.get("review_needed")!r})'
            )
    # Miserable-specific check
    mis = next((d for d in decisions if d['word'] == 'miserable'
                and d['pos'] == 'adjective' and d['cefr'] == 'B2'), None)
    if mis:
        if '|' not in mis.get('def_before_new', ''):
            failures.append(
                f'  miserable.def_before_new must contain | '
                f'(got {mis["def_before_new"]!r})'
            )
        if ';' in mis.get('def_before_new', ''):
            failures.append(
                f'  miserable.def_before_new must NOT contain ; '
                f'(got {mis["def_before_new"]!r})'
            )
    else:
        failures.append('  miserable|adjective|B2 decision missing')
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
        g = _cur_guard(r)
        d = dec_by_guard.get(g)
        if d is None:
            new_audit.append(r)
            continue
        new_r = dict(r)
        # Apply new field values from decision.
        new_r['def_before'] = d['def_before_new']
        new_r['gloss_after'] = d['gloss_after']
        new_r['rule_applied'] = d['rule_after']
        new_r['separator'] = d['separator']
        new_r['gloss_word_count'] = d['gloss_word_count']
        new_r['gate_status'] = d.get('gate_status') or 'pass'
        new_r['fix_status'] = d['fix_status']
        # Carry review_needed for _with_facet rows.
        if d.get('rule_after') in WITH_FACET_RULES:
            new_r['review_needed'] = True
            new_r['review_reason'] = d.get('review_reason') or 'p8_convention_with_facet'
        new_audit.append(new_r)
        replaced += 1
    if replaced != 457:
        print(f'FATAL: replaced {replaced} audit rows (expected 457)')
        return 1
    print(f'  Replaced {replaced} audit rows.')

    # Update TXT.
    print('\n[5] Updating TXT...')
    txt_keys: dict[tuple, str] = {}
    for d in decisions:
        k = (
            (d['word'] or '').strip().lower(),
            (d['pos'] or '').strip().lower(),
            (d['cefr'] or '').strip().upper(),
        )
        txt_keys[k] = d['gloss_after']
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
            # parts[6] = Definition cell (gloss).
            # parts[7] = Example sentence (NOT def_before — that's audit-only).
            parts[6] = txt_keys[k]
            n_txt_replaced += 1
        new_lines.append('\t'.join(parts))
    deferred_keys: set[tuple] = {k for k in txt_keys if k not in seen_keys}
    print(f'  TXT cells replaced (gloss): {n_txt_replaced}')
    print(f'  Deferred (no TXT row): {len(deferred_keys)}')
    for k in sorted(deferred_keys):
        print(f'    {k}')

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # === Apply ===
    print('\n[6] Writing changes...')
    audit_bak = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f'.bak_pre_p8_convention_{_ts()}')
    txt_bak = TXT_PATH.with_suffix(TXT_PATH.suffix + f'.bak_pre_p8_convention_{_ts()}')
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
