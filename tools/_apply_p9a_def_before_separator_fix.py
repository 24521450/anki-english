"""P9A: Broader def_before separator normalization -- guarded apply.

Reads:
  - `data/curated/deck_audit.jsonl` (current state, 2487 rows)
  - `data/sources/oxford.jsonl` (Oxford source, for sense-text matching)

Writes (with --apply; otherwise dry-run):
  - `data/curated/deck_audit.jsonl` -- only `def_before` is changed on
    exactly 66 rows. All other fields (gloss_after, rule_applied,
    separator, gloss_word_count, fix_status, gate_status, source,
    review_needed, review_reason) are byte-identical to pre-apply.

Scope (per P9A plan):
  - Candidates: rows whose `def_before` has ` ; ` and no `|` AND whose
    `gloss_after` has `|` OR `rule_applied` is in the multi-sense rule set.
  - Each candidate's `def_before` chunks (split on ' ; ') must match
    the Oxford `pos_data.definitions[].text` for the same (word, pos)
    in order. No fuzzy matching: chunks are matched by exact text.
  - New `def_before` is built by joining the matched Oxford sense texts
    with `|`. Internal semicolons (pattern `\S;\S`) are preserved.
  - `fix_status`, `source`, and all rule metadata stay unchanged.
  - `miserable|adjective|B2` is already correct post-P8 and must not
    be re-touched.

Run:
  python -m tools._apply_p9a_def_before_separator_fix            # dry-run
  python -m tools._apply_p9a_def_before_separator_fix --apply    # write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
AUDIT_PATH = paths.deck_audit_jsonl
OXF_PATH = paths.oxford_jsonl

MULTI_SENSE_RULES = {
    '2sense_distinct', '3sense_distinct', '4sense_distinct', '5sense_distinct',
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
    'multi_sense_distinct',  # legacy P6
    'trimmed_multisense',  # P7 keeps multi-chunk
}

EXPECTED_CANDIDATE_COUNT = 66

# Miserable post-P8 must NOT be re-touched.
MISERABLE_KEY = ('miserable', 'adjective', 'B2')


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def _audit_key(r: dict) -> tuple[str, str, str]:
    return (
        r['word'].strip().lower(),
        r['pos'].strip().lower(),
        r['cefr'].strip().upper(),
    )


def _is_candidate(audit_row: dict) -> bool:
    db = audit_row.get('def_before') or ''
    ga = audit_row.get('gloss_after') or ''
    rule = (audit_row.get('rule_applied') or '').strip()
    if ' ; ' not in db:
        return False
    if '|' in db:
        return False
    if '|' in ga:
        return True
    if rule in MULTI_SENSE_RULES:
        return True
    return False


def _build_oxford_index(oxf_rows: list[dict]) -> dict[tuple, dict]:
    """Index Oxford by (word_lower, pos_lower) -> pos_data dict."""
    idx: dict[tuple, dict] = {}
    for r in oxf_rows:
        w = (r.get('word') or '').strip().lower()
        for pd in r.get('pos_data') or []:
            pos = (pd.get('pos') or '').strip().lower()
            idx[(w, pos)] = pd
    return idx


def _build_new_def_before(audit_row: dict, oxf_pd: dict) -> str | None:
    """Build new def_before by joining audit chunks with |.

    Each audit chunk must match an Oxford sense text verbatim (the
    audit stores Oxford text directly, possibly a CEFR-filtered subset
    of Oxford's full sense list). The new def_before preserves the
    audit's chosen subset and ordering, but uses `|` as the top-level
    separator instead of ` ; `. Returns None if any chunk fails Oxford
    verbatim match.
    """
    db = audit_row.get('def_before') or ''
    chunks = [c.strip() for c in db.split(' ; ')]
    oxf_texts = [(d.get('text') or '').strip() for d in oxf_pd.get('definitions') or []]
    oxf_text_set = set(oxf_texts)
    for c in chunks:
        if c not in oxf_text_set:
            return None
    return '|'.join(chunks)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P9A def_before Separator Normalization (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    audit = _load_jsonl(AUDIT_PATH)
    oxf_rows = _load_jsonl(OXF_PATH)
    oxf_idx = _build_oxford_index(oxf_rows)
    print(f'\n  Audit: {len(audit)} rows')
    print(f'  Oxford: {len(oxf_rows)} rows')

    if len(audit) != 2487:
        print(f'FATAL: audit has {len(audit)} rows (expected 2487)')
        return 1

    # 1. Find candidates.
    candidates = [r for r in audit if _is_candidate(r)]
    print(f'\n[1] Candidates: {len(candidates)}')
    if len(candidates) != EXPECTED_CANDIDATE_COUNT:
        print(f'FATAL: candidate count is {len(candidates)} '
              f'(expected {EXPECTED_CANDIDATE_COUNT})')
        return 1

    # 2. Validate Oxford match for each candidate.
    print('\n[2] Validating Oxford match per candidate...')
    decisions: list[dict] = []
    unmatched: list[dict] = []
    for r in candidates:
        word, pos, cefr = _audit_key(r)
        oxf_pd = oxf_idx.get((word, pos))
        if oxf_pd is None:
            unmatched.append(r)
            continue
        new_db = _build_new_def_before(r, oxf_pd)
        if new_db is None:
            unmatched.append(r)
            continue
        if new_db == r.get('def_before'):
            # no-op (already has |) — shouldn't happen given the filter
            continue
        decisions.append({
            'word': r['word'],
            'pos': r['pos'],
            'cefr': r['cefr'],
            'def_before_old': r.get('def_before', ''),
            'def_before_new': new_db,
            'rule_applied': r.get('rule_applied', ''),
        })
    if unmatched:
        print(f'FATAL: {len(unmatched)} candidates failed Oxford match:')
        for r in unmatched[:5]:
            word, pos, cefr = _audit_key(r)
            print(f'  ({word}, {pos}, {cefr})')
        return 1
    print(f'  All {len(decisions)} candidates Oxford-matched.')

    # 3. Build new audit.
    print('\n[3] Building new audit...')
    decisions_by_key: dict[tuple, dict] = {
        (d['word'].strip().lower(), d['pos'].strip().lower(), d['cefr'].strip().upper()): d
        for d in decisions
    }
    new_audit: list[dict] = []
    replaced = 0
    field_change_failures: list[str] = []
    for r in audit:
        k = _audit_key(r)
        d = decisions_by_key.get(k)
        if d is None:
            new_audit.append(r)
            continue
        # Field isolation: copy r, only change def_before.
        new_r = dict(r)
        new_r['def_before'] = d['def_before_new']
        # Verify ALL other fields are byte-identical to r.
        for fld, v in r.items():
            if fld == 'def_before':
                continue
            if new_r.get(fld) != v:
                field_change_failures.append(
                    f'{k} field {fld!r} changed: {v!r} -> {new_r.get(fld)!r}'
                )
        new_audit.append(new_r)
        replaced += 1
    if field_change_failures:
        print('FATAL: field isolation violations:')
        for fc in field_change_failures[:10]:
            print(f'  {fc}')
        return 1
    if replaced != EXPECTED_CANDIDATE_COUNT:
        print(f'FATAL: replaced {replaced} audit rows (expected {EXPECTED_CANDIDATE_COUNT})')
        return 1
    print(f'  Replaced {replaced} audit rows (only def_before changed).')

    # 4. Miserable must NOT be re-touched.
    print('\n[4] Miserable post-P8 sanity check...')
    mis = next(
        (r for r in new_audit if _audit_key(r) == MISERABLE_KEY), None
    )
    if mis is None:
        print('FATAL: miserable|adjective|B2 audit row missing')
        return 1
    mis_db = mis.get('def_before') or ''
    if ';' in mis_db:
        print(f'FATAL: miserable|adjective|B2 has ; in def_before: {mis_db!r}')
        return 1
    if '|' not in mis_db:
        print(f'FATAL: miserable|adjective|B2 missing | in def_before: {mis_db!r}')
        return 1
    print(f'  [OK] miserable|adjective|B2 def_before has |, no ;')

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # === Apply ===
    print('\n[5] Writing changes...')
    bak = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f'.bak_pre_p9a_def_before_{_ts()}')
    bak.write_bytes(AUDIT_PATH.read_bytes())
    print(f'  Backup: {bak.name}')

    AUDIT_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_audit) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote audit: {AUDIT_PATH.name} ({len(new_audit)} rows)')
    print('\nDone. No TXT/JSONL rebuild needed (def_before is audit-only).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
