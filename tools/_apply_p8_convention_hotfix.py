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


def _cur_guard(r: dict) -> tuple:
    if 'guard_word' in r:
        return (
            (r.get('guard_word') or '').strip().lower(),
            (r.get('guard_pos') or '').strip().lower(),
            (r.get('guard_cefr') or '').strip().upper(),
            (r.get('guard_def_before') or '').strip(),
            (r.get('guard_gloss_after') or '').strip(),
        )
    else:
        return (
            (r.get('word') or '').strip().lower(),
            (r.get('pos') or '').strip().lower(),
            (r.get('cefr') or '').strip().upper(),
            (r.get('def_before') or '').strip(),
            (r.get('gloss_after') or '').strip(),
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P8 Convention + Hotfix Apply (apply={args.apply})')
    print(f'Timestamp: {datetime.now().strftime("%Y%m%d_%H%M%S")}')
    print('=' * 72)

    # Load inputs.
    print('\n[1] Loading inputs...')
    from src.deck_builder.audit_patch import (
        AuditPatchPaths,
        AuditPatchResult,
        load_jsonl,
        replace_txt_definition_cells,
        write_jsonl_text,
        match_by_guard,
        backup_and_write,
    )

    try:
        decisions = load_jsonl(DECISIONS_PATH)
        audit_rows = load_jsonl(AUDIT_PATH)
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

    # Cross-check: every decision must match exactly 1 audit row.
    print('\n[2] Cross-checking decisions vs audit...')
    try:
        matched = match_by_guard(audit_rows, decisions, _cur_guard)
    except ValueError as e:
        print(f'FATAL: ledger coverage issues:\n{e}')
        return 1
    print(f'  Matched {len(matched)} audit rows.')

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
        if g in matched:
            d = matched[g]
            new_r = dict(r)
            new_r['def_before'] = d['def_before_new']
            new_r['gloss_after'] = d['gloss_after']
            new_r['rule_applied'] = d['rule_after']
            new_r['separator'] = d['separator']
            new_r['gloss_word_count'] = d['gloss_word_count']
            new_r['gate_status'] = d.get('gate_status') or 'pass'
            new_r['fix_status'] = d['fix_status']
            if d.get('rule_after') in WITH_FACET_RULES:
                new_r['review_needed'] = True
                new_r['review_reason'] = d.get('review_reason') or 'p8_convention_with_facet'
            new_audit.append(new_r)
            replaced += 1
        else:
            new_audit.append(r)

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
        
    txt_text = TXT_PATH.read_text(encoding='utf-8')
    updated_txt_text, replaced_count, deferred_keys = replace_txt_definition_cells(txt_text, txt_keys)

    print(f'  TXT cells replaced (gloss): {replaced_count}')
    print(f'  Deferred (no TXT row): {len(deferred_keys)}')
    for k in sorted(deferred_keys):
        print(f'    {k}')

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # === Apply ===
    print('\n[6] Writing changes...')
    updated_audit_text = write_jsonl_text(new_audit)
    paths = AuditPatchPaths(audit_jsonl_path=AUDIT_PATH, txt_path=TXT_PATH, ledger_path=DECISIONS_PATH)
    result = AuditPatchResult(
        updated_audit_text=updated_audit_text,
        updated_txt_text=updated_txt_text,
        matched_count=replaced,
        replaced_count=replaced_count,
        deferred_count=len(deferred_keys),
        validation_errors=[]
    )
    backup_and_write(paths, result, 'p8_convention')

    print('\nDone. Run `python -m tools.build_notes` to regenerate JSONL.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
