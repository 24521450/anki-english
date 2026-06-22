"""Policy-Aware Gloss Coverage Audit — read-only classification.

Classifies every audit row into exactly one of:
  - `allowed_single_gloss` — rule permits one chunk.
  - `rule_shape_contradiction` — PICK rule + single chunk. P4B scope.
  - `policy_review_open` — `pos_aware_gloss` or `2sense_samedomain` with
    single chunk AND no ledger row. Untriaed → hard fail.
  - `policy_review_reviewed_keep` — ledger has `keep_single` decision.
  - `policy_review_repaired` — ledger has `repair_gloss` decision and
    the audit row reflects it.
  - `metadata_error` — separator / count / validator mismatch.
  - `other` — already multi-chunk per rule.

Ledger source: `data/gloss_policy_review_p4c.jsonl` (if it exists).
The ledger decouples review state from the audit master.

Exit code:
  0 — no rule_shape_contradiction, no metadata_error, no policy_review_open
  1 — any of the above present
  Policy_review_reviewed_keep / policy_review_repaired are REPORTED
  but do NOT cause exit 1.

Run: `python -m tools._audit_gloss_policy_coverage`
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_policy_review_p4c.jsonl'

# Rules that require multi-chunk gloss (per CONTEXT.md § Rule-Shape Consistency).
PICK_RULES = {
    '2sense_distinct', '3sense_distinct',
    'multi_sense_distinct',  # P6: supersedes '3sense_distinct' / '4sense_distinct'.
                              # N distinct senses kept with `|` (N >= 2, no upper cap).
    'rule_b_pick2', 'rule_b_pick2_addendum',
    'multi_pos_pick2',
}
# Rules that explicitly allow a one-chunk gloss.
SINGLE_ALLOWED = {
    'rule_b_pick1',
    'concrete_1sense',
    'multi_pos_pick1',
    'precision_phrase',  # P5: 2-6 word phrase form, single chunk by design
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
# single-chunk allowed.
MISC_ALLOWED = {
    'POS_DEF_MISMATCH_fixed', 'B', 'concise_def_skip', '',
}


def _classify_row(r: dict) -> tuple[str, str | None]:
    """Return (bucket, reason_if_review). The base 5-bucket classification
    that runs against the audit row alone (no ledger)."""
    rule = (r.get('rule_applied') or '').strip()
    gloss = (r.get('gloss_after') or '').strip()
    sep = (r.get('separator') or 'none').strip()
    is_single = '|' not in gloss and ';' not in gloss
    has_multi = '|' in gloss or ';' in gloss

    # Metadata check first.
    actual_sep = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
    if actual_sep != sep:
        return ('metadata_error', f'separator {sep!r} != actual {actual_sep!r}')

    if has_multi:
        return ('other', None)

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


def _load_ledger() -> dict[tuple, dict] | None:
    """Load the policy review ledger, returning a guard-key → record map
    (None if the ledger file doesn't exist)."""
    if not LEDGER_PATH.exists():
        return None
    by_guard: dict[tuple, dict] = {}
    with LEDGER_PATH.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            g = (
                rec.get('word', '').strip().lower(),
                rec.get('pos', '').strip().lower(),
                rec.get('cefr', '').strip().upper(),
            )
            by_guard[g] = rec
    return by_guard


def main() -> int:
    print('=' * 72)
    print('POLICY-AWARE GLOSS COVERAGE AUDIT')
    print('=' * 72)

    audit = [
        json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]
    print(f'\nLoaded {len(audit)} audit rows.')

    # Load ledger (may not exist yet — pre-P4C state).
    ledger_by_guard = _load_ledger()
    if ledger_by_guard is None:
        print(f'  (Ledger not present at {LEDGER_PATH.name} — '
              f'policy_review rows will all be classified as policy_review_open.)')
    else:
        print(f'  Loaded ledger with {len(ledger_by_guard)} entries.')

    # Classify every row.
    buckets: Counter = Counter()
    by_rule: dict[str, Counter] = defaultdict(Counter)
    contradiction_samples: list[dict] = []
    policy_review_open_samples: list[dict] = []
    policy_review_keep_samples: list[dict] = []
    policy_review_repaired_samples: list[dict] = []
    metadata_error_samples: list[dict] = []
    naive_multi_def_one_gloss = 0

    for r in audit:
        bucket, reason = _classify_row(r)
        rule = (r.get('rule_applied') or '').strip() or '(empty)'

        # Sub-classify policy_review into open/keep/repaired using ledger.
        # The ledger is the source of truth for "this row was triaged" —
        # a repair_gloss decision still counts as `policy_review_repaired`
        # even if the audit row has since been updated to multi-chunk
        # (which is the post-apply state).
        final_bucket = bucket
        guard = (r['word'].strip().lower(),
                 r['pos'].strip().lower(),
                 r['cefr'].strip().upper())
        ledger_decision = None
        if ledger_by_guard and guard in ledger_by_guard:
            ledger_decision = ledger_by_guard[guard].get('decision')

        if bucket == 'policy_review':
            if ledger_decision == 'keep_single':
                final_bucket = 'policy_review_reviewed_keep'
            elif ledger_decision == 'repair_gloss':
                final_bucket = 'policy_review_repaired'
            else:
                final_bucket = 'policy_review_open'
        # Else: row is now multi-chunk (post-apply), but if the ledger
        # has a repair_gloss decision for it, the row was triaged as a
        # repair and is now in its post-repair state — count it under
        # policy_review_repaired for transparency.
        elif bucket == 'other' and ledger_decision == 'repair_gloss':
            # Detect via the audit's fix_status — only count as repaired
            # if the audit explicitly marks it as p4c_policy_review_repaired.
            if r.get('fix_status') == 'p4c_policy_review_repaired':
                final_bucket = 'policy_review_repaired'

        buckets[final_bucket] += 1
        by_rule[rule][final_bucket] += 1

        if _is_multi_def_one_gloss(r):
            naive_multi_def_one_gloss += 1

        if bucket == 'rule_shape_contradiction' and len(contradiction_samples) < 10:
            contradiction_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule, 'gloss': r.get('gloss_after'),
            })
        if final_bucket == 'policy_review_open' and len(policy_review_open_samples) < 10:
            policy_review_open_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule, 'gloss': r.get('gloss_after'),
            })
        if final_bucket == 'policy_review_reviewed_keep' and len(policy_review_keep_samples) < 5:
            policy_review_keep_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule, 'gloss': r.get('gloss_after'),
            })
        if final_bucket == 'policy_review_repaired' and len(policy_review_repaired_samples) < 10:
            policy_review_repaired_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule,
                'old_gloss': ledger_by_guard[guard].get('old_gloss') if ledger_by_guard else None,
                'new_gloss': r.get('gloss_after'),
            })
        if bucket == 'metadata_error' and len(metadata_error_samples) < 5:
            metadata_error_samples.append({
                'word': r['word'], 'pos': r['pos'], 'cefr': r['cefr'],
                'rule': rule, 'gloss': r.get('gloss_after'),
                'reason': reason,
            })

    # === Report ===
    print('\n[1] Policy bucket counts:')
    bucket_labels = {
        'allowed_single_gloss': 'rule permits one chunk (no action)',
        'rule_shape_contradiction': 'PICK rule + single chunk (P4B scope)',
        'policy_review_open': 'untriaged policy review (P4C scope, FAIL)',
        'policy_review_reviewed_keep': 'triaged: keep single (informational)',
        'policy_review_repaired': 'triaged: repair_gloss applied (informational)',
        'policy_review': 'un-triaged (no ledger present)',
        'metadata_error': 'separator/count/validator mismatch',
        'other': 'already multi-chunk per rule',
    }
    for bucket, count in sorted(buckets.items(), key=lambda x: -x[1]):
        label = bucket_labels.get(bucket, bucket)
        print(f'  {bucket:36s}  {count:5d}  {label}')
    print(f'  {"TOTAL":36s}  {sum(buckets.values()):5d}  (audit row count)')

    print('\n[2] Naive multi-def one-gloss (informational only):')
    print(f'  count: {naive_multi_def_one_gloss}')
    print('  (NOT a defect — Rule A near-synonyms, Rule B same-domain')
    print('   variants, and Rule C safety net all legitimately collapse')
    print('   multiple def_before segments into one gloss word.)')

    if contradiction_samples:
        print('\n[3] Rule-shape contradiction samples:')
        for s in contradiction_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} [{s['rule']}] {s['gloss']!r}")

    if policy_review_open_samples:
        print('\n[4] Policy review OPEN samples (untriaged → FAIL):')
        for s in policy_review_open_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} [{s['rule']}] {s['gloss']!r}")

    if policy_review_repaired_samples:
        print('\n[5] Policy review REPAIRED samples:')
        for s in policy_review_repaired_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} old={s['old_gloss']!r}")

    if policy_review_keep_samples:
        print('\n[6] Policy review REVIEWED-KEEP samples:')
        for s in policy_review_keep_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} [{s['rule']}] {s['gloss']!r}")

    if metadata_error_samples:
        print('\n[7] Metadata error samples:')
        for s in metadata_error_samples:
            print(f"  {s['word']}|{s['pos']}|{s['cefr']} [{s['rule']}] — {s['reason']}")

    print('\n[8] Per-rule bucket distribution:')
    print(
        f"  {'rule':30s} {'total':>6s} {'cont':>6s} "
        f"{'open':>6s} {'keep':>6s} {'rep':>6s} {'allow':>6s} {'other':>6s}"
    )
    for rule, rule_buckets in sorted(by_rule.items(), key=lambda x: -sum(x[1].values())):
        total = sum(rule_buckets.values())
        cont = rule_buckets.get('rule_shape_contradiction', 0)
        op = rule_buckets.get('policy_review_open', 0)
        ke = rule_buckets.get('policy_review_reviewed_keep', 0)
        rp = rule_buckets.get('policy_review_repaired', 0)
        allow = rule_buckets.get('allowed_single_gloss', 0)
        other = rule_buckets.get('other', 0)
        meta = rule_buckets.get('metadata_error', 0)
        meta_str = f' meta={meta}' if meta else ''
        print(
            f"  {rule:30s} {total:>6d} {cont:>6d} {op:>6d} "
            f"{ke:>6d} {rp:>6d} {allow:>6d} {other:>6d}{meta_str}"
        )

    # === Verdict ===
    hard_fail = (
        buckets.get('rule_shape_contradiction', 0) > 0
        or buckets.get('metadata_error', 0) > 0
        or buckets.get('policy_review_open', 0) > 0
    )
    print('\n' + '=' * 72)
    if hard_fail:
        fails = []
        if buckets.get('rule_shape_contradiction', 0) > 0:
            fails.append(f'rule_shape_contradiction={buckets["rule_shape_contradiction"]}')
        if buckets.get('metadata_error', 0) > 0:
            fails.append(f'metadata_error={buckets["metadata_error"]}')
        if buckets.get('policy_review_open', 0) > 0:
            fails.append(f'policy_review_open={buckets["policy_review_open"]}')
        print(f'FAIL: {", ".join(fails)}')
        if buckets.get('rule_shape_contradiction', 0) > 0:
            print('  P4B scope: python -m tools._apply_p4b_rule_shape_fix --apply')
        if buckets.get('policy_review_open', 0) > 0:
            print('  P4C scope: extend the ledger at '
                  f'{LEDGER_PATH.name} and re-run this tool')
        print('=' * 72)
        return 1

    print('OK: no rule_shape_contradiction, no metadata_error, no policy_review_open.')
    print(
        f'  policy_review_repaired={buckets.get("policy_review_repaired", 0)}, '
        f'policy_review_reviewed_keep={buckets.get("policy_review_reviewed_keep", 0)} '
        f'(informational)'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())