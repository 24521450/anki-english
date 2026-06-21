"""P4B Rule-Shape Consistency Fix — apply tool.

Targets the 24 `rule_applied` rows whose shape is contradicted by the
gloss: rule says "pick 2" (or equivalent: distinct / addendum) but the
gloss has only 1 chunk. These are the rule-shape contradictions — NOT
all "multi-def one-gloss" rows (those need Rule A/B/C review, see
`tools/_audit_gloss_policy_coverage.py`).

Each target is identified by a guarded key
`(word, pos, cefr, old_gloss_after, rule_applied)` — the rule_applied
is part of the guard because multiple rule codes can map to the same
(word, pos, cefr) and we must target the right one.

Run:
  python -m tools._apply_p4b_rule_shape_fix              # dry-run (default)
  python -m tools._apply_p4b_rule_shape_fix --apply      # write
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

# Tuple shape: (word, pos, cefr, old_gloss, rule_applied, new_gloss)
# rule_applied is part of the guard so identical (word, pos, cefr)
# under different rule codes (e.g. worship|noun,verb|C1 was
# multi_pos_pick2; worship|verb|C1 is POS_DEF_MISMATCH_fixed) are
# matched exactly.
P4B_FIXES: list[tuple[str, str, str, str, str, str]] = [
    ('acceptance',     'noun',      'C1', 'willingness',                 'rule_b_pick2',          'receiving|agreeing'),
    ('acute',          'adjective', 'C1', 'very serious',               'rule_b_pick2',          'severe|sensitive'),
    ('appreciation',   'noun',      'C1', 'gratitude',                  'rule_b_pick2',          'gratitude|recognition'),
    ('bare',           'adjective', 'C1', 'uncovered',                  'rule_b_pick2',          'naked|empty'),
    ('breakdown',      'noun',      'C1', 'failure',                    'rule_b_pick2',          'failure|analysis'),
    ('breed',          'noun, verb', 'C1', 'animal type',                'multi_pos_pick2',       'animal type|reproduce'),
    ('circulation',    'noun',      'C1', 'flow',                       'rule_b_pick2',          'spread|sales'),
    ('civilization',   'noun',      'B2', 'society',                    'rule_b_pick2',          'developed society|all humanity'),
    ('defensive',      'adjective', 'C1', 'protective',                 'rule_b_pick2',          'protective|sensitive'),
    ('dramatic',       'adjective', 'B2', 'sudden',                     'rule_b_pick2',          'sudden|exciting'),
    ('exploitation',   'noun',      'C1', 'unfair use',                 'rule_b_pick2',          'unfair use|taking advantage'),
    ('irony',          'noun',      'C1', 'opposite result',            '2sense_distinct',       'unexpected contrast|opposite words'),
    ('lobby',          'noun, verb', 'C1', 'entrance hall',              'multi_pos_pick2',       'entrance hall|pressure group'),
    ('proposition',    'noun',      'C1', 'suggestion or proposed plan', 'rule_b_pick2',         'proposal|task'),
    ('radical',        'adjective', 'C1', 'extreme',                    'rule_b_pick2',          'thorough|extreme'),
    ('reflection',     'noun',      'C1', 'image',                      'rule_b_pick2',          'image|thought'),
    ('spell',          'noun',      'C1', 'period',                     'rule_b_pick2',          'period|magic'),
    ('strip',          'noun, verb', 'C2', 'remove',                     'multi_pos_pick2',       'sports uniform|remove clothes'),
    ('temporal',       'adjective', 'UNCLASSIFIED', 'time-related',     'rule_b_pick2',          'worldly|time-related'),
    ('tender',         'adjective', 'C1', 'gentle',                     'rule_b_pick2_addendum', 'gentle|soft'),
    ('tide',           'noun',      'C1', 'sea level',                  'rule_b_pick2',          'sea level|trend'),
    ('warrant',        'noun, verb', 'C1', 'justify',                    'multi_pos_pick2',       'legal document|justify'),
    ('welfare',        'noun',      'B2', 'well-being',                 'rule_b_pick2',          'well-being|aid'),
    ('worship',        'noun, verb', 'C1', 'revere',                     'multi_pos_pick2',       'reverence|adore'),
]


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _validate_all_new_glosses() -> list[str]:
    """Pre-flight: every new gloss must pass `validate_verdict`."""
    from src.deck_builder.gloss_llm import validate_verdict

    errors: list[str] = []
    for word, pos, cefr, _old, _rule, new in P4B_FIXES:
        sep = '|' if '|' in new else ';' if ';' in new else 'none'
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', new) if c.strip()]
        v = validate_verdict(word, new, sep, len(chunks))
        if v:
            errors.append(f'  ({word}, {pos}, {cefr}) new_gloss={new!r} → {v}')
    return errors


def _load_audit_rows() -> list[dict]:
    return [
        json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]


def _check_audit_guards(audit_rows: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Verify each P4B_FIXES tuple matches exactly one audit row.

    Guard = (word, pos, cefr, old_gloss_after, rule_applied).

    Returns (matched_rows, unmatched_fixes, error_lines).
    """
    by_guard: dict[tuple, list[dict]] = {}
    for r in audit_rows:
        g = (
            r['word'].strip().lower(),
            r['pos'].strip().lower(),
            r['cefr'].strip().upper(),
            (r.get('gloss_after') or '').strip(),
            (r.get('rule_applied') or '').strip(),
        )
        by_guard.setdefault(g, []).append(r)

    matched: list[dict] = []
    unmatched: list[dict] = []
    errors: list[str] = []
    for word, pos, cefr, old, rule, _new in P4B_FIXES:
        g = (word, pos.lower(), cefr.upper(), old, rule)
        rows = by_guard.get(g, [])
        if len(rows) == 0:
            unmatched.append({'word': word, 'pos': pos, 'cefr': cefr, 'old': old, 'rule': rule})
            errors.append(
                f'  MISS: ({word}, {pos}, {cefr}, {rule!r}, old={old!r}) → no audit row'
            )
        elif len(rows) > 1:
            errors.append(
                f'  AMBIGUOUS: ({word}, {pos}, {cefr}, {rule!r}, old={old!r}) → '
                f'{len(rows)} audit rows (guard insufficient)'
            )
        else:
            matched.append(rows[0])
    return matched, unmatched, errors


def _check_txt_targets() -> tuple[dict[tuple[str, str, str], list[int]], list[str]]:
    """Verify each P4B_FIXES tuple has exactly one TXT counterpart.

    Guard for TXT lookup is (word, pos, cefr) only — TXT has no rule_applied.
    """
    errors: list[str] = []
    txt_index: dict[tuple[str, str, str], list[int]] = {}
    lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
    for idx, line in enumerate(lines):
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            continue
        word = parts[3].strip().lower()
        pos = parts[4].strip().lower()
        cefr = parts[14].strip().upper()
        txt_index.setdefault((word, pos, cefr), []).append(idx)

    for word, pos, cefr, _old, _rule, _new in P4B_FIXES:
        key = (word, pos.lower(), cefr.upper())
        hits = txt_index.get(key, [])
        if len(hits) == 0:
            errors.append(f'  MISS: TXT row for ({word}, {pos}, {cefr}) not found')
        elif len(hits) > 1:
            errors.append(
                f'  AMBIGUOUS: TXT has {len(hits)} rows for ({word}, {pos}, {cefr})'
            )
    return txt_index, errors


def _update_audit_rows(
    matched: list[dict],
    new_gloss_by_key: dict[tuple[str, str, str], str],
) -> list[dict]:
    """Build new audit row dicts from the matched originals.

    Preserves all unrelated fields (def_before, word, pos, cefr, source,
    rule_applied, ...). Updates gloss_after, separator, gloss_word_count,
    gate_status, fix_status.
    """
    new_rows: list[dict] = []
    for r in matched:
        new = dict(r)
        key = (
            r['word'].strip().lower(),
            r['pos'].strip().lower(),
            r['cefr'].strip().upper(),
        )
        gloss = new_gloss_by_key[key]
        if '|' in gloss:
            sep = '|'
        elif ';' in gloss:
            sep = ';'
        else:
            sep = 'none'
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        wc = sum(len(c.split()) for c in chunks)
        new['gloss_after'] = gloss
        new['separator'] = sep
        new['gloss_word_count'] = wc
        new['gate_status'] = 'pass'
        new['fix_status'] = 'p4b_rule_shape_repaired'
        new_rows.append(new)
    return new_rows


def _apply_audit(
    audit_rows: list[dict],
    matched_originals: list[dict],
    updated_replacements: list[dict],
) -> list[dict]:
    """Replace matched ORIGINAL rows in audit_rows with their UPDATED
    counterparts. Identity is determined by the original row's
    (word, pos, cefr, old_gloss_after, rule_applied) tuple.
    """
    key_to_new = {
        (
            r['word'],
            r['pos'],
            r['cefr'],
            (r.get('gloss_after') or '').strip(),
            (r.get('rule_applied') or '').strip(),
        ): repl
        for r, repl in zip(matched_originals, updated_replacements)
    }
    out: list[dict] = []
    replaced = 0
    for r in audit_rows:
        g = (
            r['word'],
            r['pos'],
            r['cefr'],
            (r.get('gloss_after') or '').strip(),
            (r.get('rule_applied') or '').strip(),
        )
        if g in key_to_new:
            out.append(key_to_new[g])
            replaced += 1
        else:
            out.append(r)
    assert replaced == len(matched_originals), (
        f'audit replace mismatch: replaced={replaced} expected={len(matched_originals)}'
    )
    return out


def _apply_txt(new_gloss_by_key: dict[tuple[str, str, str], str]) -> list[str]:
    """Update TXT def cells (col 6) for the 24 target keys. Returns new lines."""
    lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
    new_lines: list[str] = []
    replaced = 0
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
        if key in new_gloss_by_key:
            parts[6] = new_gloss_by_key[key]
            new_lines.append('\t'.join(parts))
            replaced += 1
        else:
            new_lines.append(line)
    assert replaced == len(new_gloss_by_key), (
        f'TXT replace mismatch: replaced={replaced} expected={len(new_gloss_by_key)}'
    )
    return new_lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P4B Rule-Shape Consistency Fix (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Pre-flight 1: validate_verdict on every new gloss
    print('\n[1] Validating new glosses against gate rules...')
    errs = _validate_all_new_glosses()
    if errs:
        print('FATAL: new glosses fail validation:')
        for e in errs:
            print(e)
        return 1
    print(f'  All {len(P4B_FIXES)} new glosses pass validate_verdict.')

    # Pre-flight 2: verify guarded audit keys match
    print('\n[2] Loading audit rows and checking guarded keys...')
    audit_rows = _load_audit_rows()
    print(f'  Loaded {len(audit_rows)} audit rows.')
    matched, unmatched, audit_errs = _check_audit_guards(audit_rows)
    if audit_errs:
        print('FATAL: guarded key mismatches:')
        for e in audit_errs:
            print(e)
        if unmatched:
            print('\nUnmatched fixes:')
            for u in unmatched:
                print(f'  {u}')
        return 1
    print(f'  All {len(matched)} guarded audit rows match exactly.')

    # Pre-flight 3: verify TXT targets exist (1 each)
    print('\n[3] Loading TXT and checking targets...')
    _txt_index, txt_errs = _check_txt_targets()
    if txt_errs:
        print('FATAL: TXT counterpart mismatches:')
        for e in txt_errs:
            print(e)
        return 1
    print(f'  All {len(P4B_FIXES)} TXT targets found (1 row each).')

    # Build update map (audit key without rule)
    new_gloss_by_key = {
        (w.lower(), p.lower(), c.upper()): new_g
        for w, p, c, _o, _r, new_g in P4B_FIXES
    }

    # === Build new files ===
    print('\n[4] Building new audit + TXT...')
    updated_matched = _update_audit_rows(matched, new_gloss_by_key)
    # matched carries OLD gloss_after (used as identity guard);
    # updated_matched carries NEW gloss_after (used as replacement).
    new_audit = _apply_audit(audit_rows, matched, updated_matched)
    new_txt_lines = _apply_txt(new_gloss_by_key)

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        print(f'  Would update {len(matched)} audit rows.')
        print(f'  Would update {len(new_gloss_by_key)} TXT def cells.')
        return 0

    # === Apply ===
    print('\n[5] Writing changes...')
    audit_bak = AUDIT_PATH.with_suffix(
        AUDIT_PATH.suffix + f'.bak_pre_p4b_rule_shape_{_ts()}'
    )
    txt_bak = TXT_PATH.with_suffix(
        TXT_PATH.suffix + f'.bak_pre_p4b_rule_shape_{_ts()}'
    )
    audit_bak.write_text(AUDIT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    txt_bak.write_text(TXT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'  Audit backup: {audit_bak.name}')
    print(f'  TXT backup:   {txt_bak.name}')

    audit_text = '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_audit) + '\n'
    AUDIT_PATH.write_text(audit_text, encoding='utf-8')
    print(f'  Wrote audit:  {AUDIT_PATH.name} ({len(new_audit)} rows)')

    txt_text = '\n'.join(new_txt_lines) + '\n'
    TXT_PATH.write_text(txt_text, encoding='utf-8')
    print(f'  Wrote TXT:    {TXT_PATH.name}')

    print('\nDone. Run `python -m tools.build_notes` to regenerate JSONL.')
    return 0


if __name__ == '__main__':
    sys.exit(main())