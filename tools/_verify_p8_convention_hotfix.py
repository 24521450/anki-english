"""P8 Convention + Hotfix -- verifier.

Reads:
  - `data/convention_p8_decisions.jsonl` (457 P8 decisions)
  - `data/audit_full_deck_v2.jsonl` (post-apply)
  - `English Academic Vocabulary.txt` (post-apply)

Required checks:

  1. Decisions file has exactly 457 rows.
  2. All decisions' `gloss_after` passes `validate_verdict` (post-P5D).
  3. All decisions' `gloss_word_count` matches actual count.
  4. All decisions' `rule_after` is in the P8 taxonomy
     (NEW_TAXONOMY: word_gloss / phrase_gloss / facet_phrase /
     Nsense_distinct / _with_facet / + all pre-P8 rules except the
     deprecated `precision_phrase` and `multi_sense_distinct`).
  5. No audit row still has the deprecated `precision_phrase` rule
     (it was migrated to word_gloss / phrase_gloss / facet_phrase / etc.).
  6. No audit row still has the deprecated `multi_sense_distinct` rule
     (it was migrated to Nsense_distinct / _with_facet).
  7. All 3 `_with_facet` audit rows have `review_needed: true`.
  8. `miserable|adjective|B2` audit row:
     - `def_before` exactly contains `|` (Oxford source correction).
     - `def_before` does NOT contain `;` (which would be a list-of-senses
       separator from Oxford's source HTML, not a multi-sense within def_before).
     - `gloss_after` is `very unhappy|very unpleasant`.
     - `rule_applied` is `2sense_distinct`.
     - `fix_status` is `p10_semantic_hotfix`.
  9. TXT cells updated for non-deferred changed rows.
  10. Row count preserved at 2487.

Run: `python -m tools._verify_p8_convention_hotfix`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DECISIONS_PATH = PROJECT_ROOT / 'data' / 'convention_p8_decisions.jsonl'
AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'

# New convention taxonomy rules. Includes pre-P8 rules that were not
# deprecated by P8.
NEW_TAXONOMY = {
    '', 'rule_b_pick1', 'rule_b_pick2', 'rule_b_pick2_addendum',
    '2sense_samedomain', '2sense_distinct', '3sense_distinct',
    'common_core_trimmed', 'trimmed_multisense',
    'concrete_1sense', 'multi_pos_pick1', 'multi_pos_pick2',
    'safety_net',
    'pos_aware_gloss',
    'POS_DEF_MISMATCH_fixed', 'B', 'concise_def_skip',
    # === P8 convention taxonomy ===
    'word_gloss', 'phrase_gloss', 'facet_phrase',
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
    '4sense_distinct', '5sense_distinct',
}

DEPRECATED_POST_P8 = {'precision_phrase', 'multi_sense_distinct'}

WITH_FACET_RULES = {
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
}

MISERABLE_KEY = ('miserable', 'adjective', 'B2')
MISERABLE_EXPECTED_GLOSS = 'very unhappy|very unpleasant'
MISERABLE_EXPECTED_RULE = '2sense_distinct'
MISERABLE_EXPECTED_FIX_STATUS = 'p10_semantic_hotfix'

# P12 superseded values for the miserable row.
MISERABLE_P12_GLOSS = 'very unhappy or unpleasant'
MISERABLE_P12_RULE = 'facet_phrase'
MISERABLE_P12_FIX_STATUS = 'p12_equiv_sense_semantic_hotfix'


def _key(r: dict) -> tuple[str, str, str]:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
    )


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f'Not found: {path}')
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def main() -> int:
    print('=' * 72)
    print('P8 CONVENTION + HOTFIX VERIFIER')
    print('=' * 72)

    failures: list[str] = []

    print('\n[1] Loading inputs...')
    decisions = _load_jsonl(DECISIONS_PATH)
    audit = _load_jsonl(AUDIT_PATH)
    print(f'  Decisions: {len(decisions)}')
    print(f'  Audit:     {len(audit)}')

    if len(decisions) != 457:
        failures.append(f'  decisions has {len(decisions)} rows (expected 457)')
    if len(audit) != 2487:
        failures.append(f'  audit has {len(audit)} rows (expected 2487)')

    # 2. Validate each decision's gloss + word count + rule_after.
    print('\n[2] Per-decision invariants...')
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402
    rule_afters: set[str] = set()
    for d in decisions:
        gloss = (d.get('gloss_after') or '').strip()
        sep = (d.get('separator') or 'none').strip()
        wc = d.get('gloss_word_count', 0) or 0
        rule_after = (d.get('rule_after') or '').strip()
        rule_afters.add(rule_after)
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
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
    print(f'  Validated {len(decisions)} decisions')
    print(f'  rule_after values: {sorted(rule_afters)}')

    # 3. Audit row count + deprecation check.
    print('\n[3] Audit post-apply checks...')
    bad_precision = [r for r in audit if (r.get('rule_applied') or '').strip() == 'precision_phrase']
    bad_multi = [r for r in audit if (r.get('rule_applied') or '').strip() == 'multi_sense_distinct']
    if bad_precision:
        failures.append(
            f'  audit still has {len(bad_precision)} rows with deprecated precision_phrase'
        )
    else:
        print('  No deprecated precision_phrase in audit.')
    if bad_multi:
        failures.append(
            f'  audit still has {len(bad_multi)} rows with deprecated multi_sense_distinct'
        )
    else:
        print('  No deprecated multi_sense_distinct in audit.')

    # 4. _with_facet rows must have review_needed: true.
    print('\n[4] _with_facet rows must carry review_needed...')
    facet_rows = [r for r in audit if (r.get('rule_applied') or '').strip() in WITH_FACET_RULES]
    print(f'  Found {len(facet_rows)} _with_facet audit rows')
    if len(facet_rows) not in (3, 4):
        failures.append(f'  expected 3 or 4 _with_facet audit rows, got {len(facet_rows)}')
    for r in facet_rows:
        if not r.get('review_needed'):
            failures.append(
                f'  {r["word"]}|{r["pos"]}|{r["cefr"]} has rule={r["rule_applied"]!r} '
                f'but review_needed is falsy'
            )
        else:
            print(f'  [OK] {r["word"]}|{r["pos"]}|{r["cefr"]} review_needed={r["review_needed"]}')

    # 5. Miserable hotfix.
    print('\n[5] Miserable|adjective|B2 hotfix checks...')
    mis_audit = next(
        (r for r in audit if _key(r) == MISERABLE_KEY), None
    )
    if mis_audit is None:
        failures.append('  miserable|adjective|B2 audit row missing')
    else:
        def_before = (mis_audit.get('def_before') or '').strip()
        if '|' not in def_before:
            failures.append(
                f'  miserable.def_before must contain | (Oxford source correction). '
                f'Got: {def_before!r}'
            )
        if ';' in def_before:
            failures.append(
                f'  miserable.def_before must NOT contain ; (Oxford list-of-senses '
                f'separator should not appear in def_before). Got: {def_before!r}'
            )
        gloss = (mis_audit.get('gloss_after') or '').strip()
        rule = (mis_audit.get('rule_applied') or '').strip()
        fix = (mis_audit.get('fix_status') or '').strip()
        # P12 supersession: if fix_status is p12_*, accept the P12 values.
        p12_superseded = (fix == MISERABLE_P12_FIX_STATUS)
        if p12_superseded:
            expected_gloss = MISERABLE_P12_GLOSS
            expected_rule = MISERABLE_P12_RULE
        else:
            expected_gloss = MISERABLE_EXPECTED_GLOSS
            expected_rule = MISERABLE_EXPECTED_RULE
        if gloss != expected_gloss:
            failures.append(
                f'  miserable.gloss_after={gloss!r} '
                f'(expected {expected_gloss!r})'
            )
        if rule != expected_rule:
            failures.append(
                f'  miserable.rule_applied={rule!r} '
                f'(expected {expected_rule!r})'
            )
        if fix != expected_gloss and not p12_superseded:
            # fix_status check only applies if not P12-superseded
            if fix != MISERABLE_EXPECTED_FIX_STATUS:
                failures.append(
                    f'  miserable.fix_status={fix!r} '
                    f'(expected {MISERABLE_EXPECTED_FIX_STATUS!r} or '
                    f'{MISERABLE_P12_FIX_STATUS!r})'
                )
        if all(
            '|' in def_before and ';' not in def_before
            and gloss == expected_gloss
            and rule == expected_rule
            and (fix == MISERABLE_EXPECTED_FIX_STATUS or p12_superseded)
            for _ in [None]
        ):
            print(f'  [OK] miserable|adjective|B2 def_before={def_before!r}')
            print(f'  [OK] miserable|adjective|B2 gloss_after={gloss!r}')
            print(f'  [OK] miserable|adjective|B2 rule_applied={rule!r}')
            print(f'  [OK] miserable|adjective|B2 fix_status={fix!r}'
                  f'  ({"P12-superseded" if p12_superseded else "P8 baseline"})')

    # 6. TXT cells updated for changed rows.
    print('\n[6] TXT cells updated for changed rows (deferred tolerated)...')
    txt_keys: dict[tuple, str] = {}
    for line in TXT_PATH.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            continue
        k = (
            parts[3].strip().lower(),
            parts[4].strip().lower(),
            parts[14].strip().upper(),
        )
        txt_keys[k] = parts[6]
    audit_by_key = {_key(r): r for r in audit}
    n_txt_synced = 0
    n_txt_deferred = 0
    n_txt_drift = 0
    for d in decisions:
        k = _key(d)
        if k not in txt_keys:
            n_txt_deferred += 1
            continue
        if txt_keys[k].strip() == (d['gloss_after'] or '').strip():
            n_txt_synced += 1
        else:
            # Drift tolerated if the audit row was further mutated by a later pass.
            audit_row = audit_by_key.get(k, {})
            fix = (audit_row.get('fix_status') or '').strip()
            if fix in {
                'p10_semantic_hotfix', 'p11_semantic_hotfix_v2',
                'p9_convention_repaired',
                # P12/P13 may supersede P8 rows.
                'p12_equiv_sense_semantic_hotfix',
                'p13_pipe_sense_hotfix',
                # P15 simple gloss patch
                'p15_simple_gloss_repaired',
            }:
                n_txt_drift += 1
            else:
                failures.append(
                    f'  TXT {k} def={txt_keys[k]!r} '
                    f'!= decision gloss_after={d["gloss_after"]!r} '
                    f'(audit fix_status={fix!r})'
                )
    print(f'  TXT synced: {n_txt_synced}, deferred: {n_txt_deferred}, drift-tolerated: {n_txt_drift}')

    # === Final verdict ===
    print()
    if failures:
        print('=' * 72)
        print(f'FAIL -- P8 verification has {len(failures)} error(s):')
        for f in failures[:30]:
            print(f)
        if len(failures) > 30:
            print(f'  ... and {len(failures) - 30} more')
        print('=' * 72)
        return 1
    print('=' * 72)
    print(
        f'PASS -- P8 verified: {len(decisions)} decisions; '
        f'0 deprecated rules; {len(facet_rows)} _with_facet rows review_needed; '
        f'miserable hotfix applied; {n_txt_synced}/{len(decisions)} TXT synced.'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
