"""Policy-Aware Gloss Coverage Audit — read-only classification.

Classifies every audit row into exactly one of:
  - `allowed_single_gloss` — rule permits one chunk (rule_b_pick1,
    concrete_1sense, multi_pos_pick1, pos_aware_gloss, etc.).
  - `rule_shape_contradiction` — rule says pick2/distinct but the gloss
    has only 1 chunk. These are P4B targets.
  - `policy_review` — pos_aware_gloss or 2sense_samedomain collapsed
    to one chunk; Rule A may justify or M3/human review is needed.
  - `metadata_error` — separator / count / validator mismatch.
  - `other` — already multi-chunk per rule, no action needed.

Reports:
  - Bucket counts
  - Naive multi-def one-gloss count (informational — NOT a fail)
  - Rule-shape contradiction examples (if any)
  - Policy review examples (count, with sample)

Exit code:
  0 — no rule_shape_contradiction, no metadata_error
  1 — any rule_shape_contradiction or metadata_error present
  Policy review rows are REPORTED but do NOT cause exit 1.

Run: `python -m tools._audit_gloss_policy_coverage`
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'

# Rules that require multi-chunk gloss (per CONTEXT.md § Rule-Shape Consistency).
PICK_RULES = {
    '2sense_distinct', '3sense_distinct',
    'rule_b_pick2', 'rule_b_pick2_addendum',
    'multi_pos_pick2',
}
# Rules that explicitly allow a one-chunk gloss.
SINGLE_ALLOWED = {
    'rule_b_pick1',
    'concrete_1sense',
    'multi_pos_pick1',
}
# Rules where one-chunk is policy-review (needs M3/human check).
# Both `pos_aware_gloss` and `2sense_samedomain` may legitimately collapse
# to one chunk (Rule A or multi-POS policy), but cannot be verified
# mechanically — flag for human review.
POLICY_REVIEW = {
    '2sense_samedomain',
    'pos_aware_gloss',
}
# Rules that count as "other" (typically POS-fixing or unknown) — also
# single-chunk allowed. These don't fall into the contradiction or
# policy_review buckets.
MISC_ALLOWED = {
    'POS_DEF_MISMATCH_fixed', 'B', 'concise_def_skip', '',
}


def _classify_row(r: dict) -> tuple[str, str | None]:
    """Return (bucket, reason_if_review)."""
    rule = (r.get('rule_applied') or '').strip()
    gloss = (r.get('gloss_after') or '').strip()
    sep = (r.get('separator') or 'none').strip()
    is_single = '|' not in gloss and ';' not in gloss
    has_multi = '|' in gloss or ';' in gloss

    # Metadata check first — runs on every row regardless of rule.
    actual_sep = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
    if actual_sep != sep:
        return ('metadata_error', f'separator {sep!r} != actual {actual_sep!r}')

    # Multi-chunk row: shape is satisfied regardless of rule.
    if has_multi:
        return ('other', None)

    # Single-chunk row: classify by rule.
    if rule in PICK_RULES:
        return (
            'rule_shape_contradiction',
            f'rule {rule!r} requires multi-chunk, got single {gloss!r}',
        )
    if rule in POLICY_REVIEW:
        return (
            'policy_review',
            f'rule {rule!r} one-chunk — may be Rule A synonym collapse, needs M3+human review',
        )
    if rule in SINGLE_ALLOWED:
        return ('allowed_single_gloss', None)
    if rule in MISC_ALLOWED:
        return ('allowed_single_gloss', None)
    return ('allowed_single_gloss', None)


def _is_multi_def_one_gloss(r: dict) -> bool:
    """Naive diagnostic: def_before has multiple sense-segments but the
    gloss is a single chunk. NOT a defect (Rule A/B/C may justify) but
    worth reporting for transparency."""
    def_before = r.get('def_before') or ''
    gloss = (r.get('gloss_after') or '').strip()
    is_single = '|' not in gloss and ';' not in gloss
    return '|' in def_before and is_single


def main() -> int:
    print('=' * 72)
    print('POLICY-AWARE GLOSS COVERAGE AUDIT')
    print('=' * 72)

    audit = [
        json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]
    print(f'\nLoaded {len(audit)} audit rows.')

    # Classify every row.
    buckets: Counter = Counter()
    by_rule: dict[str, Counter] = defaultdict(Counter)
    contradiction_samples: list[dict] = []
    policy_review_samples: list[dict] = []
    metadata_error_samples: list[dict] = []
    naive_multi_def_one_gloss = 0

    for r in audit:
        bucket, reason = _classify_row(r)
        buckets[bucket] += 1
        rule = (r.get('rule_applied') or '').strip() or '(empty)'
        by_rule[rule][bucket] += 1
        if _is_multi_def_one_gloss(r):
            naive_multi_def_one_gloss += 1
        if bucket == 'rule_shape_contradiction' and len(contradiction_samples) < 10:
            contradiction_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule, 'gloss': r.get('gloss_after'),
            })
        if bucket == 'policy_review' and len(policy_review_samples) < 8:
            policy_review_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule, 'gloss': r.get('gloss_after'),
            })
        if bucket == 'metadata_error' and len(metadata_error_samples) < 5:
            metadata_error_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule, 'gloss': r.get('gloss_after'),
                'reason': reason,
            })

    # === Report ===
    print('\n[1] Policy bucket counts:')
    for bucket, count in sorted(buckets.items(), key=lambda x: -x[1]):
        label = {
            'allowed_single_gloss': 'rule permits one chunk (no action)',
            'rule_shape_contradiction': 'PICK rule + single chunk (P4B scope)',
            'policy_review': 'samedomain/pos_aware one-chunk (M3+human)',
            'metadata_error': 'separator/count/validator mismatch',
            'other': 'already multi-chunk per rule',
        }.get(bucket, bucket)
        print(f'  {bucket:30s}  {count:5d}  {label}')
    print(f'  {"TOTAL":30s}  {sum(buckets.values()):5d}  (audit row count)')

    print('\n[2] Naive multi-def one-gloss (informational only):')
    print(f'  count: {naive_multi_def_one_gloss}')
    print('  (NOT a defect — Rule A near-synonyms, Rule B same-domain')
    print('   variants, and Rule C safety net all legitimately collapse')
    print('   multiple def_before segments into one gloss word.)')

    if contradiction_samples:
        print('\n[3] Rule-shape contradiction samples:')
        for s in contradiction_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} [{s['rule']}] {s['gloss']!r}")

    if policy_review_samples:
        print('\n[4] Policy review samples (M3+human needed):')
        for s in policy_review_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} [{s['rule']}] {s['gloss']!r}")

    if metadata_error_samples:
        print('\n[5] Metadata error samples:')
        for s in metadata_error_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} [{s['rule']}] — {s['reason']}")

    print('\n[6] Per-rule bucket distribution:')
    print(f"  {'rule':30s} {'total':>6s} {'cont':>6s} {'policy':>7s} {'allow':>6s} {'other':>6s}")
    for rule, rule_buckets in sorted(by_rule.items(), key=lambda x: -sum(x[1].values())):
        total = sum(rule_buckets.values())
        cont = rule_buckets.get('rule_shape_contradiction', 0)
        pol = rule_buckets.get('policy_review', 0)
        allow = rule_buckets.get('allowed_single_gloss', 0)
        other = rule_buckets.get('other', 0)
        meta = rule_buckets.get('metadata_error', 0)
        meta_str = f' meta={meta}' if meta else ''
        print(f"  {rule:30s} {total:>6d} {cont:>6d} {pol:>7d} {allow:>6d} {other:>6d}{meta_str}")

    # === Verdict ===
    hard_fail = (
        buckets.get('rule_shape_contradiction', 0) > 0
        or buckets.get('metadata_error', 0) > 0
    )
    print('\n' + '=' * 72)
    if hard_fail:
        print(
            f'FAIL: rule_shape_contradiction={buckets["rule_shape_contradiction"]}, '
            f'metadata_error={buckets["metadata_error"]}'
        )
        print('  (Run P4B to fix rule-shape contradictions:')
        print('     python -m tools._apply_p4b_rule_shape_fix --apply)')
        print('=' * 72)
        return 1

    print('OK: no rule_shape_contradiction, no metadata_error.')
    print(f'  policy_review={buckets["policy_review"]} '
          f'(M3+human review needed, not auto-fixed)')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())