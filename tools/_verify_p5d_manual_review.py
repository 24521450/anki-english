"""P5D Manual Review Decisions — canonical decisions file verifier.

Reads `data/manual_gloss_review_p5d_decisions.jsonl` and asserts structural
and semantic invariants. Idempotent — re-runnable any time after manual
edits to validate the canonical file is internally consistent and ready
to be applied (or already applied).

This is the v2 pass: post word-count-limit removal. All 344 repair glosses
pass `validate_verdict` (no `word_count_out_of_range` allowed), and 644 keep
decisions have empty new_gloss.

Required checks:
  - 988 rows total (344 repair + 644 keep).
  - Decisions in {repair_gloss, keep_current}.
  - repair rows have non-empty new_gloss + rule_after='precision_phrase'
    + new_gloss != old_gloss + new_gloss passes `validate_verdict`.
  - keep rows have empty new_gloss + rule_after + separator + gloss_word_count.
  - No duplicate `(word, pos, cefr, def_before, old_gloss)` guards.
  - The 8 previously-failing long glosses (post word-count removal) all
    pass: `identification`, `rental`, `whip`, `pop`, `compromise`,
    `burst`, `outrage`, `overwhelm`.

Run: `python -m tools._verify_p5d_manual_review`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DECISIONS_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5d_decisions.jsonl'
P5_LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'

# The 8 glosses that pre-P5D failed `word_count_out_of_range`. Post-P5D
# (validator without the cap) they should all pass.
LONG_GLOSS_KEYS: set[tuple[str, str, str]] = {
    ('burst', 'verb', 'C1'),
    ('compromise', 'noun, verb', 'C1'),
    ('identification', 'noun', 'C1'),
    ('outrage', 'noun, verb', 'C1'),
    ('overwhelm', 'verb', 'C1'),
    ('pop', 'verb', 'C1'),
    ('rental', 'noun', 'C1'),
    ('whip', 'verb', 'C1'),
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
    print('P5D MANUAL REVIEW DECISIONS -- VERIFIER')
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
    if n_repair != 344:
        failures.append(f'  distribution: {n_repair} repair (expected 344)')
    if n_keep != 644:
        failures.append(f'  distribution: {n_keep} keep (expected 644)')
    if n_other != 0:
        failures.append(f'  distribution: {n_other} invalid decision')

    # P5 ledger membership. After apply, the 988 v2 decisions are reflected
    # in the ledger; total guard set should be 990 (988 + 2 seed repairs).
    p5_target_guards: set[tuple] = {
        (
            r['word'].strip().lower(),
            r['pos'].strip().lower(),
            r['cefr'].strip().upper(),
            r['def_before'],
            (r.get('old_gloss') or '').strip(),
        )
        for r in p5_rows
        if r.get('decision') in ('repair_gloss', 'keep_current', 'review_candidate')
    }
    print(f'  P5 ledger guards: {len(p5_target_guards)}')

    # Per-row invariants.
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    seen_guards: dict[tuple, int] = {}
    long_gloss_seen: set[tuple[str, str, str]] = set()
    word_count_violations: list[str] = []
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
                # Specifically watch for word_count_out_of_range -- P5D
                # removed this rule, so any occurrence is a regression.
                for violation in v:
                    if 'word_count_out_of_range' in violation:
                        word_count_violations.append(
                            f'  ({word}, {pos}, {cefr}) {violation}'
                        )
                failures.append(
                    f'  ({word}, {pos}, {cefr}) new_gloss={new_gloss!r} '
                    f'fails validator: {v}'
                )
                continue
            # Track long-gloss keys that passed.
            k = (word, pos, cefr)
            if k in LONG_GLOSS_KEYS:
                long_gloss_seen.add(k)
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

    # Long-gloss coverage check.
    missing_long = LONG_GLOSS_KEYS - long_gloss_seen
    if missing_long:
        failures.append(
            f'  long-gloss keys missing or not repaired: {sorted(missing_long)}'
        )

    # No word_count_out_of_range should appear anywhere post-P5D.
    if word_count_violations:
        failures.append(
            f'  word_count_out_of_range should be removed post-P5D; '
            f'{len(word_count_violations)} occurrence(s)'
        )

    # Final verdict.
    print()
    if failures:
        print('=' * 72)
        print(f'FAIL -- P5D decisions verification has {len(failures)} error(s):')
        for f in failures[:30]:
            print(f)
        if len(failures) > 30:
            print(f'  ... and {len(failures) - 30} more')
        print('=' * 72)
        return 1
    print('=' * 72)
    print(
        f'PASS -- P5D decisions verified: {n_repair} repair + {n_keep} keep '
        f'({len(LONG_GLOSS_KEYS)} long-gloss keys all repaired).'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
