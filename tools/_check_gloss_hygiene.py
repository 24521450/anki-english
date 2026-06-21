"""Non-mutating P0 gloss hygiene checker.

Per user plan (2026-06-21, "P0 Gloss Hygiene Cleanup"):

  FAILS (exit code 1):
    1. Literal ``\\|`` in any gloss/def cell
    2. ``separator`` field mismatches actual content (after un-escape + compact)
    3. ``gloss_word_count`` mismatches actual count
    4. Exact duplicate audit rows (canonical tuple match)

  REPORTS (does NOT fail): validator debt — glosses that pass hygiene but still
  violate the gloss_llm validator (long gloss, headword leak, POS-label candidates).
  These are deferred to a future P1 pass; we surface them so the user knows the
  scope of remaining work.

Touches (read-only):
  - ``data/audit_full_deck_v2.jsonl``
  - ``data/audit_expanded_needs_gloss_filled.jsonl``
  - ``English Academic Vocabulary.txt`` (Definition column)

Usage:
  python -m tools._check_gloss_hygiene           # fail on hard issues
  python -m tools._check_gloss_hygiene --report  # also print full debt report
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.gloss_hygiene import normalize_gloss  # noqa: E402
from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

MASTER_AUDIT = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
EXPANDED_FILLED = PROJECT_ROOT / 'data' / 'audit_expanded_needs_gloss_filled.jsonl'
DECK_TXT = PROJECT_ROOT / 'English Academic Vocabulary.txt'

CANONICAL_FIELDS = (
    'word', 'pos', 'cefr', 'def_before', 'gloss_after', 'separator',
    'rule_applied', 'gloss_word_count', 'gate_status', 'source', 'fix_status',
)

POS_LABEL_RE = re.compile(
    r'(^|[|;]\s*)'
    r'(?:'
    r'noun|verb|adjective|adverb|adj|adv|'
    r'preposition|prep|pronoun|determiner|conjunction|'
    r'exclamation|modal|auxiliary|phrasal verb|'
    r'(?:noun|verb|adjective|adverb|adj|adv)\s*/\s*'
    r'(?:noun|verb|adjective|adverb|adj|adv)'
    r')\s*:',
    re.IGNORECASE,
)


def chunk_count(gloss: str) -> int:
    return len([c for c in re.split(r'\s*[|;]\s*', gloss.strip()) if c.strip()])


def debt_category(violation: str) -> str:
    category = violation.split(':', 1)[0].split('[', 1)[0]
    if category == 'word_count_out_of_range':
        return 'gloss_too_long'
    return category


def check_audit(path: Path) -> dict:
    """Return {hard_failures: [...], debt: [...], counts: {...}}."""
    hard = defaultdict(list)  # category -> list of (line_no, sample)
    debt = defaultdict(list)
    counts = Counter(total=0, with_gloss=0)

    seen: dict[tuple, int] = {}  # canonical tuple → first line_no
    exact_dups: list[tuple[int, int]] = []  # (first_line, dup_line)

    with path.open(encoding='utf-8') as fp:
        for line_no, line in enumerate(fp, start=1):
            if not line.strip():
                continue
            r = json.loads(line)
            counts['total'] += 1

            # Exact duplicate detection
            canon = tuple(r.get(k) for k in CANONICAL_FIELDS)
            if canon in seen:
                exact_dups.append((seen[canon], line_no))
            else:
                seen[canon] = line_no

            g = r.get('gloss_after')
            if not (isinstance(g, str) and g.strip()):
                continue
            counts['with_gloss'] += 1

            res = normalize_gloss(g)

            # Hard failures
            if res.unescaped_pipe:
                hard['escaped_pipe'].append((line_no, g[:120]))
            old_sep = r.get('separator')
            if res.separator != old_sep:
                hard['separator_mismatch'].append((line_no, {
                    'gloss_after': g[:120],
                    'declared_sep': old_sep,
                    'actual_sep': res.separator,
                }))
            old_wc = r.get('gloss_word_count')
            if old_wc is not None and old_wc != res.gloss_word_count:
                hard['wc_mismatch'].append((line_no, {
                    'gloss_after': g[:120],
                    'declared_wc': old_wc,
                    'actual_wc': res.gloss_word_count,
                }))

            # Debt (does not fail): validator/style issues after normalization.
            violations = validate_verdict(
                r.get('word') or '',
                res.gloss,
                res.separator,
                chunk_count(res.gloss),
            )
            for violation in violations:
                debt[debt_category(violation)].append((line_no, {
                    'gloss_after': res.gloss[:120],
                    'violation': violation,
                    'word': r.get('word'),
                    'pos': r.get('pos'),
                    'cefr': r.get('cefr'),
                }))
            if POS_LABEL_RE.search(res.gloss):
                debt['pos_label_candidate'].append((line_no, {
                    'gloss_after': res.gloss[:120],
                    'word': r.get('word'),
                    'pos': r.get('pos'),
                    'cefr': r.get('cefr'),
                }))

    if exact_dups:
        hard['exact_duplicate_rows'].extend(exact_dups)

    return {'hard': dict(hard), 'debt': dict(debt), 'counts': dict(counts)}


def check_txt(path: Path) -> dict:
    """Check TXT def cells for escaped pipe (and pipe spacing for completeness)."""
    hard = defaultdict(list)
    debt = defaultdict(list)
    counts = Counter(total=0, with_def=0)

    with path.open(encoding='utf-8') as fp:
        for line_no, line in enumerate(fp, start=1):
            if line.startswith('#') or not line.strip():
                continue
            counts['total'] += 1
            fields = line.split('\t')
            if len(fields) <= 6:
                continue
            def_col = fields[6]
            counts['with_def'] += 1
            if '\\|' in def_col:
                hard['escaped_pipe'].append((line_no, {
                    'word': fields[3] if len(fields) > 3 else '?',
                    'def': def_col[:120],
                }))

    return {'hard': dict(hard), 'debt': dict(debt), 'counts': dict(counts)}


def main() -> int:
    ap = argparse.ArgumentParser(description='P0 gloss hygiene checker (non-mutating).')
    ap.add_argument('--report', action='store_true',
                    help='Print full debt report even when hard passes.')
    ap.add_argument('--quiet', action='store_true',
                    help='Suppress per-category detail, print only counts.')
    args = ap.parse_args()

    overall_hard: dict[str, int] = Counter()
    overall_debt: dict[str, int] = Counter()

    print('=' * 72)
    print('P0 Gloss Hygiene Checker (read-only)')
    print('=' * 72)

    # --- Audit: master ---
    print(f'\n[1/3] {MASTER_AUDIT.name}')
    r = check_audit(MASTER_AUDIT)
    print(f'  rows: total={r["counts"]["total"]} with_gloss={r["counts"]["with_gloss"]}')
    for k, v in sorted(r['hard'].items()):
        overall_hard[k] += len(v)
        print(f'  HARD  {k}: {len(v)}')
        if not args.quiet:
            for line_no, sample in v[:5]:
                print(f'    L{line_no}: {sample!r}')
            if len(v) > 5:
                print(f'    ... +{len(v) - 5} more')
    for k, v in sorted(r['debt'].items()):
        overall_debt[k] += len(v)
        if args.report:
            print(f'  DEBT  {k}: {len(v)}')
            for line_no, sample in v[:5]:
                print(f'    L{line_no}: {sample!r}')
            if len(v) > 5:
                print(f'    ... +{len(v) - 5} more')
        else:
            print(f'  DEBT  {k}: {len(v)} (use --report for details)')

    # --- Audit: filled ---
    print(f'\n[2/3] {EXPANDED_FILLED.name}')
    r = check_audit(EXPANDED_FILLED)
    print(f'  rows: total={r["counts"]["total"]} with_gloss={r["counts"]["with_gloss"]}')
    for k, v in sorted(r['hard'].items()):
        overall_hard[k] += len(v)
        print(f'  HARD  {k}: {len(v)}')
        if not args.quiet:
            for line_no, sample in v[:5]:
                print(f'    L{line_no}: {sample!r}')
            if len(v) > 5:
                print(f'    ... +{len(v) - 5} more')
    for k, v in sorted(r['debt'].items()):
        overall_debt[k] += len(v)
        if args.report:
            print(f'  DEBT  {k}: {len(v)}')
        else:
            print(f'  DEBT  {k}: {len(v)} (use --report for details)')

    # --- TXT ---
    print(f'\n[3/3] {DECK_TXT.name}')
    r = check_txt(DECK_TXT)
    print(f'  rows: total={r["counts"]["total"]} with_def={r["counts"]["with_def"]}')
    for k, v in sorted(r['hard'].items()):
        overall_hard[k] += len(v)
        print(f'  HARD  {k}: {len(v)}')
        if not args.quiet:
            for line_no, sample in v[:5]:
                print(f'    L{line_no}: {sample!r}')
            if len(v) > 5:
                print(f'    ... +{len(v) - 5} more')

    # --- Summary ---
    print('\n' + '=' * 72)
    print('Summary')
    print('=' * 72)
    print(f'  Hard failures (will exit 1 if any): {sum(overall_hard.values())}')
    for k, c in sorted(overall_hard.items(), key=lambda x: -x[1]):
        print(f'    {k}: {c}')
    print(f'  Debt (reported only): {sum(overall_debt.values())}')
    for k, c in sorted(overall_debt.items(), key=lambda x: -x[1]):
        print(f'    {k}: {c}')

    if overall_hard:
        print('\nFAIL — hygiene issues remain.')
        return 1
    print('\nOK — no hard hygiene issues.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
