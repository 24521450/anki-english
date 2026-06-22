"""P5b Manual Review Apply -- apply 335 manual repairs + finalize P5 ledger.

Reads:
  - `data/gloss_precision_phrase_p5.jsonl` (990 rows: 2 seed repair + 988 review)
  - `data/manual_gloss_review_p5_decisions.jsonl` (988 rows: 335 repair + 653 keep)

Writes (with --apply; otherwise dry-run):
  - `data/gloss_precision_phrase_p5.jsonl` (990 rows: 337 repair + 653 keep)
    - 2 seed repair rows preserved (mediate, solo)
    - 988 review_candidate rows replaced by 335 repair_gloss + 653 keep_current
  - `data/audit_full_deck_v2.jsonl` (2487 rows; 335 rows updated)
  - `English Academic Vocabulary.txt` (TXT def cells updated for repair keys)

Decision source: `data/manual_gloss_review_p5_decisions.jsonl`.
- repair_gloss: new_gloss replaces audit gloss_after + TXT def cell + ledger
- keep_current: ledger decision flips from review_candidate to keep_current;
                audit and TXT are NOT touched (already unchanged from review_candidate).

Guardrails:
- All 988 decisions must match a (word, pos, cefr, def_before, old_gloss)
  row in the P5 ledger (review_candidate set).
- All 335 repair glosses must pass validate_verdict.
- No new duplicate (word, pos, cefr, def_before, old_gloss) keys.
- Audit row count must remain 2487 (no add/delete).
- TXT def cell replacements only for keys with matching TXT row; missing
  keys are recorded as deferred (audit-only).

Run:
  python -m tools._apply_p5b_manual_review             # dry-run (default)
  python -m tools._apply_p5b_manual_review --apply     # write
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
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5_decisions.jsonl'
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
    rows: list[dict] = []
    with path.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _validate_decisions(decisions: list[dict]) -> list[str]:
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    errors: list[str] = []
    seen: dict[tuple, int] = {}

    for d in decisions:
        word = (d.get('word') or '').strip()
        pos = (d.get('pos') or '').strip().lower()
        cefr = (d.get('cefr') or '').strip().upper()
        decision = d.get('decision')

        g = (
            word.lower(), pos, cefr,
            (d.get('def_before') or '').strip(),
            (d.get('old_gloss') or '').strip(),
        )
        seen[g] = seen.get(g, 0) + 1

        if decision == 'keep_current':
            if d.get('new_gloss'):
                errors.append(f'  ({word}, {pos}, {cefr}) keep_current but new_gloss set')
            if d.get('rule_after'):
                errors.append(f'  ({word}, {pos}, {cefr}) keep_current but rule_after set')
        elif decision == 'repair_gloss':
            gloss = (d.get('new_gloss') or '').strip()
            if not gloss:
                errors.append(f'  ({word}, {pos}, {cefr}) repair_gloss but new_gloss empty')
                continue
            old = (d.get('old_gloss') or '').strip()
            if gloss == old:
                errors.append(f'  ({word}, {pos}, {cefr}) new_gloss == old_gloss ({gloss!r})')
            rule_after = (d.get('rule_after') or '').strip()
            if rule_after != 'precision_phrase':
                errors.append(
                    f'  ({word}, {pos}, {cefr}) manual_rule_after={rule_after!r} '
                    f'(expected precision_phrase)'
                )
            sep = d.get('separator', '')
            chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
            v = validate_verdict(word, gloss, sep, len(chunks))
            if v:
                errors.append(
                    f'  ({word}, {pos}, {cefr}) new_gloss={gloss!r} fails validator: {v}'
                )
        else:
            errors.append(f'  ({word}, {pos}, {cefr}) invalid decision={decision!r}')

    for g, n in seen.items():
        if n > 1:
            errors.append(f'  DUPLICATE decision guard: {g} appears {n} times')

    return errors


def _update_p5_ledger(
    ledger: list[dict],
    decisions: list[dict],
) -> tuple[list[dict], list[str]]:
    """Replace each ledger review_candidate row with the user's decision.

    Returns (new_ledger, errors). The new ledger preserves the 2 seed
    repair rows at their original positions, then for every
    review_candidate row, replaces the decision and adds manual
    provenance fields.

    Guard: every decision must match exactly one review_candidate ledger row.
    """
    errors: list[str] = []
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

    out: list[dict] = []
    n_review_seen = 0
    n_review_matched = 0
    for row in ledger:
        if row.get('decision') != 'review_candidate':
            out.append(row)
            continue
        n_review_seen += 1
        g = (
            (row.get('word') or '').strip().lower(),
            (row.get('pos') or '').strip().lower(),
            (row.get('cefr') or '').strip().upper(),
            (row.get('def_before') or '').strip(),
            (row.get('old_gloss') or '').strip(),
        )
        dec = dec_by_guard.get(g)
        if dec is None:
            errors.append(f'  NO DECISION for review_candidate ({g[0]}, {g[1]}, {g[2]})')
            out.append(row)
            continue
        new_row = dict(row)
        new_row['decision'] = dec['decision']
        new_row['new_gloss'] = dec['new_gloss']
        if dec['decision'] == 'repair_gloss':
            new_row['rule_after'] = dec['rule_after']
            new_row['separator'] = dec['separator']
            new_row['gloss_word_count'] = dec['gloss_word_count']
        else:
            # keep_current: clear new_gloss, rule_after; preserve old_gloss in record
            new_row['new_gloss'] = None
            new_row['rule_after'] = None
            new_row['separator'] = 'none'
            new_row['gloss_word_count'] = 0
        # Manual provenance
        new_row['manual_decision'] = dec['decision']
        new_row['manual_notes'] = dec.get('notes', '')
        new_row['qa_normalized'] = dec.get('qa_normalized', False)
        if dec.get('qa_normalized'):
            new_row['qa_original'] = dec.get('qa_original', '')
        new_row['p5b_version'] = '2026-06-22'
        out.append(new_row)
        n_review_matched += 1

    if n_review_matched != len(decisions):
        errors.append(
            f'  matched {n_review_matched} ledger review rows but have {len(decisions)} decisions'
        )
    if n_review_seen != 988:
        errors.append(f'  ledger has {n_review_seen} review_candidate rows (expected 988)')

    return out, errors


def _check_audit_coverage(
    audit_rows: list[dict],
    repair_decisions: list[dict],
) -> tuple[list[dict], list[dict], list[str]]:
    """Match each repair decision to its audit row by full guard.

    Returns (matched_audit_rows, repair_decisions_with_match, errors).
    """
    by_guard: dict[tuple, list[dict]] = {}
    for r in audit_rows:
        g = _full_audit_guard(r)
        by_guard.setdefault(g, []).append(r)

    matched_audit: list[dict] = []
    matched_decisions: list[dict] = []
    errors: list[str] = []
    for d in repair_decisions:
        word = (d['word'] or '').strip().lower()
        pos = (d['pos'] or '').strip().lower()
        cefr = (d['cefr'] or '').strip().upper()
        rule = (d.get('rule_applied') or '').strip()
        def_before = (d.get('def_before') or '').strip()
        old = (d.get('old_gloss') or '').strip()
        g = (word, pos, cefr, rule, def_before, old)
        rows = by_guard.get(g, [])
        if len(rows) == 0:
            errors.append(
                f'  NO AUDIT MATCH for ({word}, {pos}, {cefr}, old={old!r})'
            )
        elif len(rows) > 1:
            errors.append(
                f'  AMBIGUOUS: ({word}, {pos}, {cefr}) matches {len(rows)} audit rows'
            )
        else:
            matched_audit.append(rows[0])
            matched_decisions.append(d)
    return matched_audit, matched_decisions, errors


def _build_updated_audit(
    matched_audit: list[dict],
    repair_decisions: list[dict],
) -> list[dict]:
    """Build the updated audit row dicts (replacements) for each matched repair."""
    out: list[dict] = []
    for r, d in zip(matched_audit, repair_decisions):
        new = dict(r)
        new['gloss_after'] = d['new_gloss']
        new['rule_applied'] = d.get('rule_after') or new.get('rule_applied', '')
        new['separator'] = d.get('separator', 'none')
        new['gloss_word_count'] = d.get('gloss_word_count', 0)
        new['gate_status'] = 'pass'
        new['fix_status'] = 'p5b_manual_review_repaired'
        out.append(new)
    return out


def _apply_audit(
    audit_rows: list[dict],
    matched_originals: list[dict],
    replacements: list[dict],
) -> tuple[list[dict], list[str]]:
    """Replace matched originals in audit_rows with replacements."""
    key_to_new = {
        _full_audit_guard(r): repl
        for r, repl in zip(matched_originals, replacements)
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
    errors: list[str] = []
    if replaced != len(matched_originals):
        errors.append(
            f'audit replace mismatch: replaced={replaced} expected={len(matched_originals)}'
        )
    return out, errors


def _apply_txt(
    new_gloss_by_key: dict[tuple[str, str, str], str],
) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Update TXT def cells for repair keys.

    Returns (new_lines, skipped_keys). Keys with no matching TXT row
    are recorded as deferred (audit-only, JSONL reconciliation pending).
    """
    lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
    new_lines: list[str] = []
    replaced = 0
    skipped: list[tuple[str, str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for line in lines:
        if line.startswith('#') or not line.strip():
            new_lines.append(line)
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            new_lines.append(line)
            continue
        word = parts[3].strip().lower()
        pos = parts[4].strip().lower()
        cefr = parts[14].strip().upper()
        key = (word, pos, cefr)
        seen_keys.add(key)
        if key in new_gloss_by_key:
            parts[6] = new_gloss_by_key[key]
            new_lines.append('\t'.join(parts))
            replaced += 1
        else:
            new_lines.append(line)
    for key in new_gloss_by_key:
        if key not in seen_keys:
            skipped.append(key)
    return new_lines, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P5B Manual Review Apply (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load all inputs.
    print('\n[1] Loading inputs...')
    try:
        ledger = _load_jsonl(P5_LEDGER_PATH)
        decisions = _load_jsonl(DECISIONS_PATH)
        audit_rows = _load_jsonl(AUDIT_PATH)
    except FileNotFoundError as e:
        print(f'FATAL: {e}')
        return 1
    print(f'  P5 ledger: {len(ledger)} rows')
    print(f'  Decisions: {len(decisions)} rows')
    print(f'  Audit:     {len(audit_rows)} rows')

    # Decisions structural validation.
    print('\n[2] Validating decisions...')
    errs = _validate_decisions(decisions)
    if errs:
        print('FATAL: decisions validation failed:')
        for e in errs:
            print(e)
        return 1
    n_repair = sum(1 for d in decisions if d['decision'] == 'repair_gloss')
    n_keep = sum(1 for d in decisions if d['decision'] == 'keep_current')
    print(f'  All {len(decisions)} decisions valid ({n_repair} repair + {n_keep} keep)')

    # Update P5 ledger.
    print('\n[3] Updating P5 ledger...')
    new_ledger, ledger_errs = _update_p5_ledger(ledger, decisions)
    if ledger_errs:
        print('FATAL: ledger update errors:')
        for e in ledger_errs:
            print(e)
        return 1
    n_new_repair = sum(1 for r in new_ledger if r['decision'] == 'repair_gloss')
    n_new_keep = sum(1 for r in new_ledger if r['decision'] == 'keep_current')
    n_new_review = sum(1 for r in new_ledger if r['decision'] == 'review_candidate')
    print(
        f'  Updated ledger: {len(new_ledger)} rows '
        f'({n_new_repair} repair + {n_new_keep} keep + {n_new_review} review)'
    )
    if len(new_ledger) != 990:
        print(f'FATAL: updated ledger has {len(new_ledger)} rows (expected 990)')
        return 1
    if n_new_repair != 337:
        print(f'FATAL: updated ledger has {n_new_repair} repair (expected 337)')
        return 1
    if n_new_keep != 653:
        print(f'FATAL: updated ledger has {n_new_keep} keep (expected 653)')
        return 1
    if n_new_review != 0:
        print(f'FATAL: updated ledger has {n_new_review} review (expected 0)')
        return 1

    # Match audit + apply updates.
    print('\n[4] Matching repair decisions to audit rows...')
    repair_decisions = [d for d in decisions if d['decision'] == 'repair_gloss']
    matched_audit, matched_decisions, audit_cov_errs = _check_audit_coverage(
        audit_rows, repair_decisions
    )
    if audit_cov_errs:
        print('FATAL: audit coverage errors:')
        for e in audit_cov_errs:
            print(e)
        return 1
    print(f'  Matched {len(matched_audit)} audit rows.')

    # Apply audit updates.
    print('\n[5] Building new audit...')
    replacements = _build_updated_audit(matched_audit, matched_decisions)
    new_audit, apply_errs = _apply_audit(audit_rows, matched_audit, replacements)
    if apply_errs:
        print('FATAL: audit apply errors:')
        for e in apply_errs:
            print(e)
        return 1
    if len(new_audit) != len(audit_rows):
        print(
            f'FATAL: audit row count changed: {len(audit_rows)} -> {len(new_audit)}'
        )
        return 1
    print(f'  Audit row count preserved: {len(new_audit)} rows')

    # Build new-gloss map for TXT.
    new_gloss_by_key = {
        (
            (d['word'] or '').strip().lower(),
            (d['pos'] or '').strip().lower(),
            (d['cefr'] or '').strip().upper(),
        ): d['new_gloss']
        for d in matched_decisions
    }

    # Apply TXT updates.
    print('\n[6] Building new TXT...')
    new_txt_lines, skipped_txt_keys = _apply_txt(new_gloss_by_key)
    print(
        f'  TXT cells replaced: {len(new_gloss_by_key) - len(skipped_txt_keys)}; '
        f'deferred: {len(skipped_txt_keys)}'
    )
    if skipped_txt_keys:
        for k in skipped_txt_keys:
            print(
                f'  DEFERRED: {k[0]}|{k[1]}|{k[2]} -- no matching TXT row, '
                f'JSONL reconciliation pending a future fix'
            )

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # === Apply ===
    print('\n[7] Writing changes...')
    audit_bak = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f'.bak_pre_p5b_manual_review_{_ts()}')
    txt_bak = TXT_PATH.with_suffix(TXT_PATH.suffix + f'.bak_pre_p5b_manual_review_{_ts()}')
    ledger_bak = P5_LEDGER_PATH.with_suffix(P5_LEDGER_PATH.suffix + f'.bak_pre_p5b_{_ts()}')

    audit_bak.write_text(AUDIT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    txt_bak.write_text(TXT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    ledger_bak.write_text(P5_LEDGER_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'  Audit backup:  {audit_bak.name}')
    print(f'  TXT backup:    {txt_bak.name}')
    print(f'  Ledger backup: {ledger_bak.name}')

    # Write audit.
    audit_text = '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_audit) + '\n'
    AUDIT_PATH.write_text(audit_text, encoding='utf-8')
    print(f'  Wrote audit:   {AUDIT_PATH.name} ({len(new_audit)} rows)')

    # Write TXT.
    txt_text = '\n'.join(new_txt_lines) + '\n'
    TXT_PATH.write_text(txt_text, encoding='utf-8')
    print(f'  Wrote TXT:     {TXT_PATH.name}')

    # Write ledger.
    ledger_text = '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_ledger) + '\n'
    P5_LEDGER_PATH.write_text(ledger_text, encoding='utf-8')
    print(f'  Wrote ledger:  {P5_LEDGER_PATH.name} ({len(new_ledger)} rows)')

    print(
        '\nDone. Run `python -m tools.build_notes` to regenerate JSONL.'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
