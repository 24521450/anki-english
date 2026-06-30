"""P5 Precision Phrase Ledger — apply tool.

Reads the ledger (`data/gloss_precision_phrase_p5.jsonl`) and applies
the `repair_gloss` decisions to:
  - audit row: update `gloss_after`, `rule_applied` (→ `precision_phrase`),
    `separator`, `gloss_word_count`, `gate_status`, `fix_status`
  - TXT def cell (col 6) for the (word, pos, cefr) key

`review_candidate` and `keep_current` rows are recorded in the ledger
but cause NO change to audit + TXT.

Guard key for matching ledger to audit: `(word, pos, cefr, def_before, old_gloss)`.
This 5-element guard prevents accidental wrong-row updates if the
audit drifts between the scan and the apply.

NOTE: This is a historical apply tool. It is stale-sensitive. Running this tool
against the current `data/curated/deck_audit.jsonl` may fail and exit `1` because
target guard rows have already been modified/superseded by subsequent runs
(e.g., P12, P13, P15). This strict failure is the correct and expected safety
behavior to prevent accidental wrong-row corruption.

Run:
  python -m tools._apply_p5_precision_phrase              # dry-run (default)
  python -m tools._apply_p5_precision_phrase --apply      # write
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

from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
AUDIT_PATH = paths.deck_audit_jsonl
TXT_PATH = paths.anki_notes_txt
LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'


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


def _load_ledger() -> list[dict]:
    from src.deck_builder.audit_patch import load_jsonl
    if not LEDGER_PATH.exists():
        raise FileNotFoundError(
            f'Ledger not found: {LEDGER_PATH}. Run `python -m tools._build_p5_ledger` first.'
        )
    return load_jsonl(LEDGER_PATH)


def _full_audit_guard(r: dict) -> tuple:
    """Identity guard for matching ledger rows to audit rows. Includes
    `def_before` + `old_gloss` so audit drift aborts."""
    gloss = r.get('old_gloss') if 'old_gloss' in r else r.get('gloss_after')
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
        (r.get('rule_applied') or '').strip(),
        (r.get('def_before') or '').strip(),
        (gloss or '').strip(),
    )


def _validate_ledger_structure(ledger: list[dict]) -> list[str]:
    """Static structural validation (no audit access here)."""
    from src.deck_builder.gloss_llm import validate_verdict

    errors: list[str] = []
    seen_guards: dict[tuple, int] = {}

    for rec in ledger:
        for f in ('word', 'pos', 'cefr', 'rule_applied', 'def_before',
                  'old_gloss', 'decision', 'reason', 'p5_version',
                  'risk_type', 'candidate_gloss'):
            if f not in rec:
                errors.append(f'  missing field {f!r} in {rec.get("word", "?")}')

        word = (rec.get('word') or '').strip()
        pos = (rec.get('pos') or '').strip().lower()
        cefr = (rec.get('cefr') or '').strip().upper()
        rule = (rec.get('rule_applied') or '').strip()
        old = (rec.get('old_gloss') or '').strip()
        decision = rec.get('decision')

        g = (word.lower(), pos, cefr, rule, rec.get('def_before', ''), old)
        seen_guards[g] = seen_guards.get(g, 0) + 1

        if decision == 'keep_current':
            if rec.get('new_gloss') is not None:
                errors.append(
                    f'  ({word}, {pos}, {cefr}) decision=keep_current but new_gloss set'
                )
        elif decision == 'repair_gloss':
            new = (rec.get('new_gloss') or '').strip()
            if not new:
                errors.append(
                    f'  ({word}, {pos}, {cefr}) decision=repair_gloss but new_gloss empty'
                )
            elif new == old:
                errors.append(
                    f'  ({word}, {pos}, {cefr}) new_gloss == old_gloss ({new!r}) — no-op fix'
                )
            else:
                sep = '|' if '|' in new else ';' if ';' in new else 'none'
                chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', new) if c.strip()]
                v = validate_verdict(word, new, sep, len(chunks))
                if v:
                    errors.append(
                        f'  ({word}, {pos}, {cefr}) new_gloss={new!r} fails validator: {v}'
                    )
        elif decision == 'review_candidate':
            if rec.get('new_gloss') is not None:
                errors.append(
                    f'  ({word}, {pos}, {cefr}) decision=review_candidate but new_gloss set'
                )
        else:
            errors.append(
                f'  ({word}, {pos}, {cefr}) unknown decision={decision!r}'
            )

        rule_after = (rec.get('rule_after') or '').strip()
        if decision == 'repair_gloss' and not rule_after:
            errors.append(
                f'  ({word}, {pos}, {cefr}) repair_gloss but rule_after empty'
            )
        elif decision in ('keep_current', 'review_candidate') and rule_after:
            errors.append(
                f'  ({word}, {pos}, {cefr}) decision={decision!r} but rule_after={rule_after!r} set'
            )

    for g, n in seen_guards.items():
        if n > 1:
            errors.append(f'  DUPLICATE ledger guard: {g} appears {n} times')

    return errors


def _check_audit_coverage(
    audit_rows: list[dict],
    ledger: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """Cross-check ledger against audit.

    Returns (matched, repair_records, keep_records, errors). Each
    matched audit row is paired with its ledger decision.
    """
    from src.deck_builder.audit_patch import match_by_guard
    repair_records = [r for r in ledger if r.get('decision') == 'repair_gloss']
    keep_records = [r for r in ledger if r.get('decision') != 'repair_gloss']
    try:
        matched = match_by_guard(audit_rows, repair_records, _full_audit_guard)
        return list(matched.values()), repair_records, keep_records, []
    except ValueError as e:
        return [], [], [], [str(e)]


def _update_audit_rows(
    matched_repair: list[dict],
    ledger: list[dict],
) -> list[dict]:
    """Build updated audit row dicts for repair_gloss entries only."""
    rec_by_guard = {
        (
            r['word'].strip().lower(),
            r['pos'].strip().lower(),
            r['cefr'].strip().upper(),
            (r.get('rule_applied') or '').strip(),
            r.get('def_before', ''),
            (r.get('old_gloss') or '').strip(),
        ): r
        for r in ledger
    }
    new_rows: list[dict] = []
    for r in matched_repair:
        new = dict(r)
        g = _full_audit_guard(r)
        rec = rec_by_guard[g]
        new_gloss = rec['new_gloss']
        rule_after = (rec.get('rule_after') or '').strip()
        sep, wc = _compute_separator_count(new_gloss)
        new['gloss_after'] = new_gloss
        new['rule_applied'] = rule_after or new.get('rule_applied', '')
        new['separator'] = sep
        new['gloss_word_count'] = wc
        new['gate_status'] = 'pass'
        new['fix_status'] = 'p5_precision_phrase_repaired'
        new_rows.append(new)
    return new_rows


def _apply_audit(
    audit_rows: list[dict],
    matched_repair_originals: list[dict],
    updated_replacements: list[dict],
) -> list[dict]:
    """Replace matched_repair ORIGINAL rows in audit_rows with their
    UPDATED counterparts.
    """
    key_to_new = {
        _full_audit_guard(r): repl
        for r, repl in zip(matched_repair_originals, updated_replacements)
    }
    out: list[dict] = []
    replaced = 0
    for r in audit_rows:
        g = _full_audit_guard(r)
        if g in key_to_new:
            out.append(key_to_new[g])
            replaced += 1
        else:
            out.append(r)
    assert replaced == len(matched_repair_originals), (
        f'audit replace mismatch: replaced={replaced} '
        f'expected={len(matched_repair_originals)}'
    )
    return out


def _apply_txt(new_gloss_by_key: dict[tuple[str, str, str], str]) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Update TXT def cells (col 6) for the repair keys."""
    from src.deck_builder.audit_patch import replace_txt_definition_cells
    txt_text = TXT_PATH.read_text(encoding='utf-8')
    updated_txt, replaced, deferred = replace_txt_definition_cells(txt_text, new_gloss_by_key)
    return updated_txt.splitlines(), list(deferred)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P5 Precision Phrase Ledger Apply (apply={args.apply})')
    print(f'Timestamp: {datetime.now().strftime("%Y%m%d_%H%M%S")}')
    print('=' * 72)

    # Load ledger using helper
    print('\n[1] Loading ledger...')
    try:
        ledger = _load_ledger()
    except FileNotFoundError as e:
        print(f'FATAL: {e}')
        return 1
    n_repair = sum(1 for r in ledger if r.get('decision') == 'repair_gloss')
    n_review = sum(1 for r in ledger if r.get('decision') == 'review_candidate')
    n_keep = sum(1 for r in ledger if r.get('decision') == 'keep_current')
    print(f'  Ledger: {len(ledger)} rows ({n_repair} repair + {n_review} review + {n_keep} keep_current)')

    # Structural validation
    print('\n[2] Validating ledger structure...')
    errs = _validate_ledger_structure(ledger)
    if errs:
        print('FATAL: ledger validation failed:')
        for e in errs:
            print(e)
        return 1
    print(f'  All {len(ledger)} ledger rows structurally valid.')

    # Cross-check against audit
    print('\n[3] Loading audit and checking coverage...')
    from src.deck_builder.audit_patch import AuditPatchPaths, AuditPatchResult, load_jsonl, replace_txt_definition_cells, write_jsonl_text, backup_and_write
    try:
        audit_rows = load_jsonl(AUDIT_PATH)
    except FileNotFoundError as e:
        print(f'FATAL: {e}')
        return 1

    print(f'  Loaded {len(audit_rows)} audit rows.')
    matched, repair_records, keep_records, cov_errs = _check_audit_coverage(audit_rows, ledger)
    if cov_errs:
        print('FATAL: ledger coverage issues:')
        for e in cov_errs:
            print(e)
        return 1
    print(f'  All {len(matched)} repair rows match exactly one audit row.')
    if len(matched) != n_repair:
        print(
            f'FATAL: expected {n_repair} repair records but matched {len(matched)}.'
        )
        return 1
    print(f'  {len(keep_records)} non-repair rows (review_candidate + keep_current) recorded only.')

    # Build new-gloss map (repair only)
    new_gloss_by_key = {
        (r['word'].strip().lower(),
         r['pos'].strip().lower(),
         r['cefr'].strip().upper()): r['new_gloss']
        for r in repair_records
    }

    # Build new files
    print('\n[4] Building new audit + TXT...')
    updated_repair = _update_audit_rows(matched, ledger)
    new_audit = _apply_audit(audit_rows, matched, updated_repair)
    
    updated_audit_text = write_jsonl_text(new_audit)
    
    txt_text = TXT_PATH.read_text(encoding='utf-8')
    updated_txt_text, replaced_count, deferred_keys = replace_txt_definition_cells(txt_text, new_gloss_by_key)

    print(f'  Repair: {len(matched)} audit rows + {replaced_count} TXT cells')
    if deferred_keys:
        for k in sorted(deferred_keys):
            print(
                f'  SKIPPED TXT (no matching row): {k[0]}|{k[1]}|{k[2]} — '
                f'audit updated, TXT/JSONL reconciliation deferred to a future fix'
            )
    print(f'  Review-candidate / keep_current: {len(keep_records)} (no audit change)')

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # Apply backups and write changes
    print('\n[5] Writing changes...')
    paths = AuditPatchPaths(audit_jsonl_path=AUDIT_PATH, txt_path=TXT_PATH, ledger_path=LEDGER_PATH)
    result = AuditPatchResult(
        updated_audit_text=updated_audit_text,
        updated_txt_text=updated_txt_text,
        matched_count=len(matched),
        replaced_count=replaced_count,
        deferred_count=len(deferred_keys),
        validation_errors=[]
    )
    backup_and_write(paths, result, 'p5_precision_phrase')

    print('\nDone. Run `python -m tools.build_notes` to regenerate JSONL.')
    return 0


if __name__ == '__main__':
    sys.exit(main())