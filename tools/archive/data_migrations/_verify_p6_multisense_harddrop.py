"""P6 Multisense Hard-Drop Repair -- verifier.

Reads:
  - `data/multisense_harddrop_p6_decisions.jsonl` (117 P6 decisions)
  - `data/curated/deck_audit.jsonl` (post-apply)
  - `data/build/anki_notes.txt` (post-apply)
  - `data/build/anki_notes.jsonl` (post-rebuild)

Asserts structural invariants. Idempotent — re-runnable any time after
P6 apply to validate the patch is fully reflected in the deck.

Required checks (all must hold):

  1. Decisions file has exactly 117 rows.
  2. All decisions use `rule_after = multi_sense_distinct`.
  3. All decisions' `new_gloss` passes `validate_verdict` (post-P5D).
  4. All decisions' `gloss_word_count` matches actual count.
  5. Audit row count remains 2487; no duplicate guards.
  6. Exactly 117 audit rows reflect P6 decisions
     (`fix_status = p6_multisense_harddrop_repaired` or P7/P8 successor,
     `gloss_after = decision.new_gloss` unless superseded by P7/P8).
  7. Exactly 114 TXT rows sync; exactly 3 deferred keys match the
     known set: harbor|verb|UNCLASSIFIED, invading|verb|UNCLASSIFIED,
     shortsighted|adjective|UNCLASSIFIED.
  8. No P6 audit row is mis-classified as `rule_shape_contradiction`
     by `_audit_gloss_policy_coverage`.

Post-P8 drift tolerance:
  - P8 split `multi_sense_distinct` into the new convention taxonomy
    (`2sense_distinct` / `3sense_distinct` / `4sense_distinct` /
    `5sense_distinct` / `2sense_distinct_with_facet` /
    `3sense_distinct_with_facet`). P6 audit rows are allowed to have any
    of these successor rules post-P8.
  - TXT gloss drift after P8 is tolerated for keys whose current audit
    row has a P8 successor rule.
  - The P6 decisions file itself is a historical artifact: its
    `rule_after` field stays `multi_sense_distinct` regardless of
    later taxonomy migrations.

Historical run path:
`python -m tools.archive.data_migrations._verify_p6_multisense_harddrop`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

DECISIONS_PATH = PROJECT_ROOT / 'data' / 'multisense_harddrop_p6_decisions.jsonl'
from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
AUDIT_PATH = paths.deck_audit_jsonl
TXT_PATH = paths.anki_notes_txt

EXPECTED_DEFERRED_KEYS: set[tuple[str, str, str]] = {
    ('harbor', 'verb', 'UNCLASSIFIED'),
    ('invading', 'verb', 'UNCLASSIFIED'),
    ('shortsighted', 'adjective', 'UNCLASSIFIED'),
}

# Post-P8 successors of P6's `multi_sense_distinct` rule. P6 audit rows
# may now use any of these after the convention taxonomy split.
P8_P6_SUCCESSOR_RULES = {
    'multi_sense_distinct',  # legacy rows not yet migrated by P8
    '2sense_distinct',
    '3sense_distinct',
    '4sense_distinct',
    '5sense_distinct',
    '2sense_distinct_with_facet',
    '3sense_distinct_with_facet',
}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f'Not found: {path}')
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def _key(r: dict) -> tuple[str, str, str]:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
    )


def _compute_word_count(gloss: str) -> int:
    if not gloss:
        return 0
    chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss.strip()) if c.strip()]
    return sum(len(c.split()) for c in chunks)


def main() -> int:
    print('=' * 72)
    print('P6 MULTISENSE HARD-DROP REPAIR -- VERIFIER')
    print('=' * 72)

    failures: list[str] = []

    # Load inputs.
    print('\n[1] Loading inputs...')
    try:
        decisions = _load_jsonl(DECISIONS_PATH)
        audit = _load_jsonl(AUDIT_PATH)
    except FileNotFoundError as e:
        print(f'FATAL: {e}')
        return 1
    print(f'  Decisions: {len(decisions)}')
    print(f'  Audit:     {len(audit)}')

    if len(decisions) != 117:
        failures.append(f'  decisions has {len(decisions)} rows (expected 117)')
    if len(audit) != 2487:
        failures.append(f'  audit has {len(audit)} rows (expected 2487)')

    # Distribution + invariant checks per decision.
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    n_qa = 0
    seen_guards: dict[tuple, int] = {}
    seen_rule_after: set[str] = set()
    print('\n[2] Per-decision invariants...')
    for d in decisions:
        word = (d.get('word') or '').strip()
        pos = (d.get('pos') or '').strip()
        cefr = (d.get('cefr') or '').strip()
        rule_after = (d.get('rule_after') or '').strip()
        gloss = (d.get('new_gloss') or '').strip()
        old_gloss = (d.get('old_gloss') or '').strip()
        sep = (d.get('separator') or '').strip()
        wc = d.get('gloss_word_count', 0) or 0
        fix_status = (d.get('fix_status') or '').strip()

        seen_rule_after.add(rule_after)
        g = _key(d)
        seen_guards[g] = seen_guards.get(g, 0) + 1
        if d.get('qa_normalized'):
            n_qa += 1

        if rule_after != 'multi_sense_distinct':
            failures.append(
                f'  ({word}, {pos}, {cefr}) rule_after={rule_after!r} '
                f'(expected multi_sense_distinct)'
            )
        if not gloss:
            failures.append(f'  ({word}, {pos}, {cefr}) new_gloss empty')
            continue
        if gloss == old_gloss:
            failures.append(
                f'  ({word}, {pos}, {cefr}) new_gloss == old_gloss ({gloss!r})'
            )
        actual_wc = _compute_word_count(gloss)
        if actual_wc != wc:
            failures.append(
                f'  ({word}, {pos}, {cefr}) gloss_word_count={wc} '
                f'!= actual {actual_wc}'
            )
        if fix_status != 'p6_multisense_harddrop_repaired':
            failures.append(
                f'  ({word}, {pos}, {cefr}) fix_status={fix_status!r} '
                f'(expected p6_multisense_harddrop_repaired)'
            )
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        v = validate_verdict(word, gloss, sep, len(chunks))
        if v:
            failures.append(
                f'  ({word}, {pos}, {cefr}) new_gloss={gloss!r} fails validator: {v}'
            )

    if seen_rule_after != {'multi_sense_distinct'}:
        failures.append(
            f'  rule_after values: {seen_rule_after} (expected {{multi_sense_distinct}})'
        )
    dups = [g for g, n in seen_guards.items() if n > 1]
    if dups:
        failures.append(f'  {len(dups)} duplicate (word, pos, cefr) guards')

    print(f'  Validated {len(decisions)} decisions ({n_qa} QA-normalized)')
    print(f'  rule_after values: {seen_rule_after}')

    # Audit reflection. After P6 apply, the audit row at (word,pos,cefr)
    # has been mutated. Match by key, then check the row reflects the
    # P6 decision (gloss_after == new_gloss, rule_applied ==
    # multi_sense_distinct, fix_status == p6_multisense_harddrop_repaired).
    print('\n[3] Audit reflection...')
    dec_by_key = {_key(d): d for d in decisions}
    audit_by_key: dict[tuple, list[dict]] = {}
    for r in audit:
        audit_by_key.setdefault(_key(r), []).append(r)
    n_synced = 0
    for d in decisions:
        k = _key(d)
        rows = audit_by_key.get(k, [])
        if not rows:
            failures.append(f'  audit missing for {k}')
            continue
        if len(rows) > 1:
            failures.append(
                f'  audit has {len(rows)} rows for {k} (expected 1)'
            )
            continue
        target = rows[0]
        # Drift tolerance: P7 may have superseded this P6 row with a
        # common_core_trimmed / trimmed_multisense rule (redundant subsenses
        # collapsed). P8 may have migrated multi_sense_distinct to the new
        # convention taxonomy. Accept P7/P8 verdicts as later, more thorough
        # passes.
        target_fix_status = target.get('fix_status', '').strip()
        target_rule_applied = target.get('rule_applied', '').strip()
        p7_superseded = target_fix_status == 'p7_redundant_sense_trimmed'
        p15_superseded = target_fix_status == 'p15_simple_gloss_repaired'
        # P8 may have changed the rule_applied + gloss but kept the original
        # fix_status (p6_multisense_harddrop_repaired) — that's a P8
        # convention migration, drift-tolerated.
        p8_migrated = (
            target_rule_applied in P8_P6_SUCCESSOR_RULES
            and target_rule_applied != 'multi_sense_distinct'
        )
        if target_fix_status not in (
            'p6_multisense_harddrop_repaired', 'p7_redundant_sense_trimmed',
            'p10_semantic_hotfix', 'p11_semantic_hotfix_v2', 'p15_simple_gloss_repaired',
        ):
            failures.append(
                f'  audit {k} fix_status={target.get("fix_status")!r} '
                f'(expected p6_multisense_harddrop_repaired or p7_redundant_sense_trimmed)'
            )
        if target.get('gloss_after', '').strip() != (d.get('new_gloss') or '').strip():
            if not (p7_superseded or p8_migrated or p15_superseded):
                failures.append(
                    f'  audit {k} gloss_after={target.get("gloss_after")!r} '
                    f'!= decision new_gloss={(d.get("new_gloss") or "")!r}'
                )
        if target_rule_applied not in P8_P6_SUCCESSOR_RULES:
            if not (p7_superseded or p15_superseded):
                failures.append(
                    f'  audit {k} rule_applied={target_rule_applied!r} '
                    f'(expected one of {sorted(P8_P6_SUCCESSOR_RULES)})'
                )
        n_synced += 1
    print(f'  Audit rows synced: {n_synced}/117')

    # TXT reflection.
    print('\n[4] TXT reflection...')
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
    n_txt_synced = 0
    missing_in_txt: set[tuple] = set()
    for d in decisions:
        k = _key(d)
        if k not in txt_keys:
            missing_in_txt.add(k)
            continue
        if txt_keys[k].strip() != (d.get('new_gloss') or '').strip():
            # Drift tolerance: P7 may have collapsed this P6 row's gloss.
            # P8 may have migrated this P6 row's gloss to a new convention
            # taxonomy entry (different gloss text). The P6 decisions file
            # still has the un-collapsed gloss; the TXT cell reflects the
            # later verdict. Skip the failure.
            target_audit = next(
                (r for r in audit
                 if (r.get('word') or '').strip().lower() == k[0]
                 and (r.get('pos') or '').strip().lower() == k[1]
                 and (r.get('cefr') or '').strip().upper() == k[2]),
                None,
            )
            if target_audit:
                target_fix = target_audit.get('fix_status', '').strip()
                target_rule = target_audit.get('rule_applied', '').strip()
                if target_fix in ('p7_redundant_sense_trimmed', 'p15_simple_gloss_repaired'):
                    continue
                # P8 migration: rule moved to a P8 successor of multi_sense_distinct.
                if target_rule in P8_P6_SUCCESSOR_RULES and target_rule != 'multi_sense_distinct':
                    continue
            failures.append(
                f'  TXT {k} def={txt_keys[k]!r} '
                f'!= decision new_gloss={(d.get("new_gloss") or "")!r}'
            )
        n_txt_synced += 1
    print(f'  TXT cells synced: {n_txt_synced}/117; missing: {len(missing_in_txt)}')
    for k in sorted(missing_in_txt):
        print(f'    missing: {k}')
    if missing_in_txt != EXPECTED_DEFERRED_KEYS:
        unexpected = missing_in_txt - EXPECTED_DEFERRED_KEYS
        missing_from_expected = EXPECTED_DEFERRED_KEYS - missing_in_txt
        if unexpected:
            failures.append(f'  unexpected deferred keys: {unexpected}')
        if missing_from_expected:
            failures.append(
                f'  expected deferred keys missing: {missing_from_expected}'
            )
    else:
        print(f'  Deferred keys match expected: {sorted(EXPECTED_DEFERRED_KEYS)}')

    # No rule_shape_contradiction introduced for P6 rows.
    print('\n[5] Rule-shape check...')
    from tools._audit_gloss_policy_coverage import (  # noqa: E402
        PICK_RULES, _classify_row,
    )
    for d in decisions:
        k = _key(d)
        rows = audit_by_key.get(k, [])
        if not rows:
            continue
        target = rows[0]
        bucket, reason = _classify_row(target)
        if bucket == 'rule_shape_contradiction':
            failures.append(
                f'  P6 row {k} mis-classified as rule_shape_contradiction: {reason}'
            )
    print(f'  No P6 row is rule_shape_contradiction.')

    # Final verdict.
    print()
    if failures:
        print('=' * 72)
        print(f'FAIL -- P6 verification has {len(failures)} error(s):')
        for f in failures[:30]:
            print(f)
        if len(failures) > 30:
            print(f'  ... and {len(failures) - 30} more')
        print('=' * 72)
        return 1
    print('=' * 72)
    print(
        f'PASS -- P6 verified: 117 decisions; 117 audit rows synced; '
        f'{n_txt_synced} TXT cells synced; 3 expected deferred keys.'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
