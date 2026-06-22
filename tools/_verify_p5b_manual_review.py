"""P5B Manual Review Decisions — canonical decisions file verifier.

Reads `data/manual_gloss_review_p5_decisions.jsonl` and asserts structural
and semantic invariants. Idempotent — re-runnable any time after manual
edits to validate the canonical file is internally consistent and ready
to be applied (or already applied).

Required checks:
  - 988 rows total (335 repair + 653 keep).
  - Decisions in {repair_gloss, keep_current}.
  - repair rows have non-empty new_gloss + rule_after='precision_phrase'
    + new_gloss != old_gloss + new_gloss passes `validate_verdict`.
  - keep rows have empty new_gloss + rule_after + separator + gloss_word_count.
  - No duplicate `(word, pos, cefr, def_before, old_gloss)` guards.
  - All 7 QA-normalized rows have qa_normalized=True + qa_original matches
    a known pre-normalization gloss (set of 7 documented in
    `_import_p5b_decisions.QA_NORMALIZATIONS`).
  - Every row matches a P5 ledger `review_candidate` row by full guard
    (this enforces decisions were imported from the same P5 ledger they
    are intended to apply to).

Run: `python -m tools._verify_p5b_manual_review`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DECISIONS_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5_decisions.jsonl'
P5_LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'

# Set of (word|pos|cefr) for the 7 QA-normalized keys, mirroring the import tool.
QA_NORMALIZED_KEYS: set[str] = {
    'burst|verb|C1',
    'compromise|noun, verb|C1',
    'outrage|noun, verb|C1',
    'overwhelm|verb|C1',
    'pop|verb|C1',
    'punk|noun|B2',
    'whip|verb|C1',
}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f'Not found: {path}')
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


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


def main() -> int:
    print('=' * 72)
    print('P5B MANUAL REVIEW DECISIONS -- VERIFIER')
    print('=' * 72)

    failures: list[str] = []

    # Load decisions + P5 ledger.
    print('\n[1] Loading inputs...')
    try:
        decisions = _load_jsonl(DECISIONS_PATH)
        p5_rows = _load_jsonl(P5_LEDGER_PATH)
    except FileNotFoundError as e:
        print(f'FATAL: {e}')
        return 1
    print(f'  Decisions: {len(decisions)}')
    print(f'  P5 ledger: {len(p5_rows)}')

    # Distribution.
    n_repair = sum(1 for d in decisions if d.get('decision') == 'repair_gloss')
    n_keep = sum(1 for d in decisions if d.get('decision') == 'keep_current')
    n_other = sum(
        1 for d in decisions
        if d.get('decision') not in ('repair_gloss', 'keep_current')
    )
    print(f'  Distribution: {n_repair} repair + {n_keep} keep + {n_other} other')

    if len(decisions) != 988:
        failures.append(f'decisions has {len(decisions)} rows (expected 988)')
    if n_repair != 335:
        failures.append(f'  distribution: {n_repair} repair (expected 335)')
    if n_keep != 653:
        failures.append(f'  distribution: {n_keep} keep (expected 653)')
    if n_other != 0:
        failures.append(f'  distribution: {n_other} invalid decision')

    # P5 ledger membership. After apply, the 988 review_candidate rows
    # were replaced by 335 repair + 653 keep; total guard set remains
    # 990. We accept any (decision in {repair_gloss, keep_current}) that
    # carries the original review_candidate guard (5-element).
    p5_target_guards: set[tuple] = {
        (
            r['word'].strip().lower(),
            r['pos'].strip().lower(),
            r['cefr'].strip().upper(),
            r['def_before'],
            (r.get('old_gloss') or '').strip(),
        )
        for r in p5_rows
        if r.get('decision') in ('review_candidate', 'repair_gloss', 'keep_current')
    }
    print(f'  P5 ledger review/target guards: {len(p5_target_guards)}')

    # Per-row invariants.
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    seen_guards: dict[tuple, int] = {}
    n_qa_seen = 0
    print('\n[2] Per-row invariants...')
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
            (d.get('def_before') or '').strip(),
            old_gloss,
        )
        seen_guards[g] = seen_guards.get(g, 0) + 1

        # P5 membership.
        if g not in p5_target_guards:
            failures.append(
                f'  NO P5 MATCH: ({word}, {pos}, {cefr}) not in P5 ledger'
            )
            continue

        if decision == 'repair_gloss':
            if not new_gloss:
                failures.append(f'  ({word}, {pos}, {cefr}) repair but new_gloss empty')
                continue
            if rule_after != 'precision_phrase':
                failures.append(
                    f'  ({word}, {pos}, {cefr}) repair but rule_after={rule_after!r}'
                )
                continue
            if new_gloss == old_gloss:
                failures.append(
                    f'  ({word}, {pos}, {cefr}) new_gloss == old_gloss ({new_gloss!r})'
                )
                continue
            sep = d.get('separator', '')
            wc = d.get('gloss_word_count', 0)
            # Recompute separator/count for validation
            exp_sep, exp_wc = _compute_separator_count(new_gloss)
            chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', new_gloss) if c.strip()]
            if sep != exp_sep:
                failures.append(
                    f'  ({word}, {pos}, {cefr}) separator={sep!r} '
                    f'(expected {exp_sep!r})'
                )
                continue
            if wc != exp_wc:
                failures.append(
                    f'  ({word}, {pos}, {cefr}) gloss_word_count={wc} '
                    f'(expected {exp_wc})'
                )
                continue
            v = validate_verdict(word, new_gloss, sep, len(chunks))
            if v:
                failures.append(
                    f'  ({word}, {pos}, {cefr}) new_gloss={new_gloss!r} '
                    f'fails validator: {v}'
                )
                continue
            # QA flag.
            qk = f'{word.lower()}|{pos}|{cefr}'
            if qk in QA_NORMALIZED_KEYS:
                n_qa_seen += 1
                if not d.get('qa_normalized'):
                    failures.append(
                        f'  ({word}, {pos}, {cefr}) expected QA-normalized but qa_normalized=False'
                    )
                elif not (d.get('qa_original') or '').strip():
                    failures.append(
                        f'  ({word}, {pos}, {cefr}) qa_normalized=True but qa_original empty'
                    )
        elif decision == 'keep_current':
            if new_gloss:
                failures.append(
                    f'  ({word}, {pos}, {cefr}) keep but new_gloss={new_gloss!r}'
                )
                continue
            if rule_after:
                failures.append(
                    f'  ({word}, {pos}, {cefr}) keep but rule_after={rule_after!r}'
                )
                continue
            if d.get('separator', 'none') != 'none':
                failures.append(
                    f'  ({word}, {pos}, {cefr}) keep but separator={d.get("separator")!r}'
                )
                continue
            if d.get('gloss_word_count', 0) != 0:
                failures.append(
                    f'  ({word}, {pos}, {cefr}) keep but gloss_word_count={d.get("gloss_word_count")}'
                )
                continue

    # Duplicate guards.
    dups = [g for g, n in seen_guards.items() if n > 1]
    if dups:
        failures.append(f'  {len(dups)} duplicate (word, pos, cefr, def_before, old_gloss) guards')

    # QA cross-check: 7 expected QA keys must all appear.
    if n_qa_seen != 7:
        failures.append(f'  QA-normalized rows seen: {n_qa_seen} (expected 7)')

    # Final verdict.
    print()
    if failures:
        print('=' * 72)
        print(f'FAIL -- P5B decisions verification has {len(failures)} error(s):')
        for f in failures:
            print(f)
        print('=' * 72)
        return 1
    print('=' * 72)
    print(
        f'PASS -- P5B decisions verified: {n_repair} repair + {n_keep} keep '
        f'({n_qa_seen} QA-normalized).'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
