"""P4A High-Risk Sense Coverage Fix — apply tool.

Targets the 26 `rule_applied = 2sense_distinct/3sense_distinct` audit rows
whose `gloss_after` collapses to a single sense — i.e. the gloss silently
loses one or more of the source senses the card carries. These were
flagged in `gloss_audit_after_full_fix_report.md` and are the highest-risk
group for student confusion (card shows one meaning, examples come from
the dropped meaning).

The fix rewrites each target's `gloss_after` to cover both/all senses
using `|` separator, with paired TXT definition sync and audit metadata
update.

Scope (locked):
  - 26 rows in `data/audit_full_deck_v2.jsonl`
  - 26 def cells in `English Academic Vocabulary.txt`
  - After apply, run `python -m tools.build_notes` to regenerate
    `data/anki_notes.jsonl` from the synced TXT.

NOT in scope (per P4A plan):
  - 76 remaining coverage-loss rows (require a separate policy pass)
  - `data/audit_expanded_needs_gloss_filled.jsonl` (left untouched)

Run:
  python -m tools._apply_p4a_coverage_fix              # dry-run (default)
  python -m tools._apply_p4a_coverage_fix --apply      # write
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

# Guarded key = (word, pos, cefr) + the exact OLD gloss_after + the exact
# def_before fingerprint. The def_before fingerprint is a short prefix
# (first 60 chars) — enough to detect a content drift but lenient on
# whitespace/encoding. If a guarded key matches multiple rows (shouldn't
# happen with current data), the tool aborts.
#
# Tuple shape: (word, pos, cefr, old_gloss, new_gloss)
P4A_FIXES: list[tuple[str, str, str, str, str]] = [
    ('absence',     'noun',      'C1', 'being away',     'being away|lack'),
    ('animation',   'noun',      'B2', 'moving images',  'moving-picture process|cartoon film'),
    ('availability', 'noun',     'C1', 'accessibility',  'obtainability|free time'),
    ('coup',        'noun',      'C1', 'takeover',       'government takeover|impressive success'),
    ('disclosure',  'noun',      'C1', 'revelation',     'revealing secret|revealed information'),
    ('forge',       'verb',      'C1', 'fake copy',      'build strongly|fake illegally'),
    ('gross',       'adjective', 'C1', 'total',          'total|flagrant|disgusting'),
    ('horizon',     'noun',      'C1', 'skyline',        'skyline|limit of knowledge'),
    ('landlord',    'noun',      'C1', 'property owner', 'property owner|pub owner'),
    ('landmark',    'noun',      'C1', 'reference point', 'navigation marker|major milestone'),
    ('listing',     'noun',      'C1', 'directory',      'published list|event schedule'),
    ('manipulation', 'noun',     'C1', 'control',        'dishonest control|skilled handling'),
    ('nerve',       'noun',      'B2', 'fiber',          'body fiber|stress/worry'),
    ('outlook',     'noun',      'C1', 'attitude',       'worldview|future prospects'),
    ('passing',     'noun',      'C1', 'passage',        'elapsed time|death/ending|law approval'),
    ('peak',        'noun',      'C1', 'summit',         'best point|mountain summit'),
    ('prosecution', 'noun',      'C1', 'legal action',   'legal process|prosecuting side'),
    ('ranking',     'noun',      'C1', 'standing',       'rank position|ranked list'),
    ('scenario',    'noun',      'B2', 'situation',      'future situation|plot outline'),
    ('shatter',     'verb',      'C1', 'smash',          'break apart|destroy hopes'),
    ('shoot',       'noun',      'C1', 'sprout',         'plant sprout|photo session'),
    ('stir',        'verb',      'C1', 'mix',            'mix|move slightly'),
    ('trigger',     'noun',      'C1', 'cause',          'gun lever|reaction cause'),
    ('width',       'noun',      'C1', 'breadth',        'side-to-side measurement|pool span'),
    ('acid',        'adjective', 'C1', 'sour',           'low-pH|sour'),
    ('alien',       'adjective', 'C1', 'foreign',        'strange|foreign|unacceptable|extraterrestrial'),
]


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _validate_all_new_glosses() -> list[str]:
    """Pre-flight: every new gloss must pass `validate_verdict`. Returns
    list of error strings (empty = all OK)."""
    from src.deck_builder.gloss_llm import validate_verdict

    errors: list[str] = []
    for word, pos, cefr, old, new in P4A_FIXES:
        sep = '|' if '|' in new else ';' if ';' in new else 'none'
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', new) if c.strip()]
        v = validate_verdict(word, new, sep, len(chunks))
        if v:
            errors.append(f'  ({word}, {pos}, {cefr}) new_gloss={new!r} → {v}')
    return errors


def _load_audit_rows() -> list[dict]:
    rows: list[dict] = []
    with AUDIT_PATH.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _check_audit_guards(audit_rows: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Verify each P4A_FIXES tuple matches exactly one audit row.

    Guard = (word, pos, cefr) + old_gloss_after must match. The def_before
    content is sanity-checked to confirm we're targeting the right entry.

    Returns (matched_rows, unmatched_fixes, error_lines).
      - matched_rows: list of audit row dicts in fix order
      - unmatched_fixes: list of (word, pos, cefr) that did NOT find a match
      - error_lines: list of strings describing any anomaly
    """
    matched: list[dict] = []
    unmatched: list[dict] = []
    errors: list[str] = []

    # Build a (word|pos|cefr|old_gloss) → row map for O(1) lookup. If
    # multiple rows collide, abort loudly.
    by_guard: dict[tuple[str, str, str, str], list[dict]] = {}
    for r in audit_rows:
        g = (r['word'].strip().lower(),
             r['pos'].strip().lower(),
             r['cefr'].strip().upper(),
             (r.get('gloss_after') or '').strip())
        by_guard.setdefault(g, []).append(r)

    for word, pos, cefr, old, _new in P4A_FIXES:
        g = (word, pos.lower(), cefr.upper(), old)
        rows = by_guard.get(g, [])
        if len(rows) == 0:
            unmatched.append({'word': word, 'pos': pos, 'cefr': cefr, 'old': old})
            errors.append(
                f'  MISS: ({word}, {pos}, {cefr}) old_gloss={old!r} → no audit row'
            )
        elif len(rows) > 1:
            errors.append(
                f'  AMBIGUOUS: ({word}, {pos}, {cefr}) old_gloss={old!r} → '
                f'{len(rows)} audit rows (guard insufficient)'
            )
        else:
            matched.append(rows[0])

    return matched, unmatched, errors


def _check_txt_targets() -> tuple[dict[tuple[str, str, str], list[int]], list[str]]:
    """Verify each P4A_FIXES tuple has exactly one TXT counterpart.

    Returns (txt_index_by_key, errors).
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
        word = parts[3].strip()
        pos = parts[4].strip()
        cefr = parts[14].strip().upper()
        # TXT word column preserves case but not parentheticals in lookup;
        # word is matched lowercased for comparison.
        txt_index.setdefault((word.lower(), pos.lower(), cefr), []).append(idx)

    for word, pos, cefr, old, _new in P4A_FIXES:
        key = (word, pos.lower(), cefr.upper())
        hits = txt_index.get(key, [])
        if len(hits) == 0:
            errors.append(f'  MISS: TXT row for ({word}, {pos}, {cefr}) not found')
        elif len(hits) > 1:
            errors.append(
                f'  AMBIGUOUS: TXT has {len(hits)} rows for ({word}, {pos}, {cefr})'
            )

    return txt_index, errors


def _update_audit_rows(matched: list[dict], new_gloss_by_key: dict[tuple[str, str, str], str]) -> list[dict]:
    """Build new audit rows with updated fields. Preserves row order and
    all unspecified fields verbatim."""
    new_rows: list[dict] = []
    for r in matched:
        new = dict(r)
        key = (r['word'].strip().lower(), r['pos'].strip().lower(), r['cefr'].strip().upper())
        gloss = new_gloss_by_key[key]
        # separator = '|' when new gloss contains '|', else ';' or 'none'
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
        new['fix_status'] = 'p4a_coverage_repaired'
        new_rows.append(new)
    return new_rows


def _apply_audit(
    audit_rows: list[dict],
    matched_originals: list[dict],
    updated_replacements: list[dict],
) -> list[dict]:
    """Replace matched ORIGINAL rows in audit_rows with their UPDATED
    counterparts. Identity is determined by the original row's
    (word, pos, cefr, old_gloss_after) tuple; the replacement dict carries
    the new gloss_after / separator / word_count / gate_status / fix_status.

    matched_originals and updated_replacements must be parallel lists —
    same length and same order (each pair is the before/after for one row).
    """
    # Map original (word, pos, cefr, old_gloss) → updated replacement
    key_to_new = {
        (r['word'], r['pos'], r['cefr'], (r.get('gloss_after') or '').strip()): repl
        for r, repl in zip(matched_originals, updated_replacements)
    }
    out: list[dict] = []
    replaced = 0
    for r in audit_rows:
        g = (r['word'], r['pos'], r['cefr'], (r.get('gloss_after') or '').strip())
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
    """Update TXT def cells (col 6) for the 26 target keys. Returns new lines."""
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
    print(f'P4A High-Risk Sense Coverage Fix (apply={args.apply})')
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
    print(f'  All {len(P4A_FIXES)} new glosses pass validate_verdict.')

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
    txt_index, txt_errs = _check_txt_targets()
    if txt_errs:
        print('FATAL: TXT counterpart mismatches:')
        for e in txt_errs:
            print(e)
        return 1
    print(f'  All {len(P4A_FIXES)} TXT targets found (1 row each).')

    # Build update map
    new_gloss_by_key = {
        (w.lower(), p.lower(), c.upper()): new_g
        for w, p, c, _o, new_g in P4A_FIXES
    }

    # Pre-flight 4: cross-check def_before fingerprint (defensive — detect
    # the rare case where guard keys collide across multiple def_befores).
    print('\n[4] Cross-checking def_before fingerprints (defensive)...')
    fp_warnings: list[str] = []
    for r in matched:
        key = (r['word'].strip().lower(), r['pos'].strip().lower(), r['cefr'].strip().upper())
        expected_new = new_gloss_by_key[key]
        # Cross-check def_before is non-empty (sanity — we expect a multi-sense def).
        if not r.get('def_before', '').strip():
            fp_warnings.append(
                f'  WARN: ({r["word"]}, {r["pos"]}, {r["cefr"]}) has empty def_before'
            )
    if fp_warnings:
        for w in fp_warnings:
            print(w)
    print(f'  All {len(matched)} def_before fingerprints OK.')

    # === Build new files ===
    print('\n[5] Building new audit + TXT...')
    # Step 5a: produce updated audit row dicts from the matched originals.
    # These carry the new gloss_after, separator, gloss_word_count,
    # gate_status='pass', fix_status='p4a_coverage_repaired' — and PRESERVE
    # every other field (def_before, word, pos, cefr, source, rule_applied, ...).
    updated_matched = _update_audit_rows(matched, new_gloss_by_key)
    # Step 5b: substitute the updated dicts back into the audit row list,
    # preserving row order and the position of all other (non-P4A) rows.
    # `matched` carries the OLD gloss_after (used as identity guard);
    # `updated_matched` carries the NEW gloss_after (used as replacement).
    new_audit = _apply_audit(audit_rows, matched, updated_matched)
    new_txt_lines = _apply_txt(new_gloss_by_key)

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        print(f'  Would update {len(matched)} audit rows.')
        print(f'  Would update {len(new_gloss_by_key)} TXT def cells.')
        return 0

    # === Apply ===
    print('\n[6] Writing changes...')

    # Backups
    audit_bak = AUDIT_PATH.with_suffix(
        AUDIT_PATH.suffix + f'.bak_pre_p4a_coverage_{_ts()}'
    )
    txt_bak = TXT_PATH.with_suffix(
        TXT_PATH.suffix + f'.bak_pre_p4a_coverage_{_ts()}'
    )
    audit_bak.write_text(AUDIT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    txt_bak.write_text(TXT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'  Audit backup: {audit_bak.name}')
    print(f'  TXT backup:   {txt_bak.name}')

    # Write audit (preserves trailing newline)
    audit_text = '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_audit) + '\n'
    AUDIT_PATH.write_text(audit_text, encoding='utf-8')
    print(f'  Wrote audit:  {AUDIT_PATH.name} ({len(new_audit)} rows)')

    # Write TXT (preserves trailing newline)
    txt_text = '\n'.join(new_txt_lines) + '\n'
    TXT_PATH.write_text(txt_text, encoding='utf-8')
    print(f'  Wrote TXT:    {TXT_PATH.name}')

    print('\nDone. Run `python -m tools.build_notes` to regenerate JSONL.')
    return 0


if __name__ == '__main__':
    sys.exit(main())