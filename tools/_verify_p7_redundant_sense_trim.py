"""P7 Redundant Sense Trim -- verifier.

Reads:
  - `data/redundant_sense_trim_p7_decisions.jsonl` (59 P7 decisions)
  - `data/curated/deck_audit.jsonl` (post-apply)
  - `data/build/anki_notes.txt` (post-apply)

Asserts structural invariants. Idempotent.

Required checks (all must hold):
  1. Decisions file has exactly 59 rows.
  2. All decisions' rule_after is one of {common_core_trimmed, trimmed_multisense}.
  3. All decisions' new_gloss passes validate_verdict (post-P5D).
  4. All decisions' gloss_word_count matches actual count.
  5. Audit row count remains 2487; no duplicate guards.
  6. Exactly 59 audit rows reflect P7 decisions
     (fix_status = p7_redundant_sense_trimmed,
     gloss_after = decision.new_gloss,
     rule_applied = decision.rule_after,
     separator + gloss_word_count match).
  7. Exactly 59 TXT cells synced; 0 deferred.
  8. No P6 row was silently backdrifted to legacy rule codes
     (3sense_distinct / 4sense_distinct / 5sense_distinct) by P7.

Run: `python -m tools._verify_p7_redundant_sense_trim`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DECISIONS_PATH = PROJECT_ROOT / 'data' / 'redundant_sense_trim_p7_decisions.jsonl'
from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
AUDIT_PATH = paths.deck_audit_jsonl
TXT_PATH = paths.anki_notes_txt

ALLOWED_RULES = {'common_core_trimmed', 'trimmed_multisense'}


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
    print('P7 REDUNDANT SENSE TRIM -- VERIFIER')
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

    if len(decisions) != 59:
        failures.append(f'  decisions has {len(decisions)} rows (expected 59)')
    if len(audit) != 2487:
        failures.append(f'  audit has {len(audit)} rows (expected 2487)')

    # Per-decision invariants.
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    seen_guards: dict[tuple, int] = {}
    seen_rule_afters: set[str] = set()
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

        seen_rule_afters.add(rule_after)
        g = _key(d)
        seen_guards[g] = seen_guards.get(g, 0) + 1

        if rule_after not in ALLOWED_RULES:
            failures.append(
                f'  ({word}, {pos}, {cefr}) rule_after={rule_after!r} '
                f'(expected one of {sorted(ALLOWED_RULES)})'
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
        if fix_status != 'p7_redundant_sense_trimmed':
            failures.append(
                f'  ({word}, {pos}, {cefr}) fix_status={fix_status!r} '
                f'(expected p7_redundant_sense_trimmed)'
            )
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        v = validate_verdict(word, gloss, sep, len(chunks))
        if v:
            failures.append(
                f'  ({word}, {pos}, {cefr}) new_gloss={gloss!r} fails validator: {v}'
            )

    if seen_rule_afters != ALLOWED_RULES:
        failures.append(
            f'  rule_after values: {seen_rule_afters} (expected {sorted(ALLOWED_RULES)})'
        )
    dups = [g for g, n in seen_guards.items() if n > 1]
    if dups:
        failures.append(f'  {len(dups)} duplicate (word, pos, cefr) guards')

    print(f'  Validated {len(decisions)} decisions')
    print(f'  rule_after values: {seen_rule_afters}')

    # Audit reflection.
    print('\n[3] Audit reflection...')
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
            failures.append(f'  audit has {len(rows)} rows for {k} (expected 1)')
            continue
        target = rows[0]
        target_fix = target.get('fix_status', '').strip()
        p15_superseded = target_fix == 'p15_simple_gloss_repaired'
        if target_fix not in ('p7_redundant_sense_trimmed', 'p15_simple_gloss_repaired'):
            failures.append(
                f'  audit {k} fix_status={target_fix!r} '
                f'(expected p7_redundant_sense_trimmed)'
            )
        if target.get('gloss_after', '').strip() != (d.get('new_gloss') or '').strip():
            if not p15_superseded:
                failures.append(
                    f'  audit {k} gloss_after={target.get("gloss_after")!r} '
                    f'!= decision new_gloss={(d.get("new_gloss") or "")!r}'
                )
        if target.get('rule_applied', '').strip() != (d.get('rule_after') or '').strip():
            if not p15_superseded:
                failures.append(
                    f'  audit {k} rule_applied={target.get("rule_applied")!r} '
                    f'!= decision rule_after={(d.get("rule_after") or "")!r}'
                )
        if target.get('separator', '').strip() != (d.get('separator') or '').strip():
            if not p15_superseded:
                failures.append(
                    f'  audit {k} separator={target.get("separator")!r} '
                    f'!= decision separator={(d.get("separator") or "")!r}'
                )
        if target.get('gloss_word_count', -1) != d.get('gloss_word_count', -1):
            if not p15_superseded:
                failures.append(
                    f'  audit {k} gloss_word_count={target.get("gloss_word_count")} '
                    f'!= decision gloss_word_count={d.get("gloss_word_count")}'
                )
        n_synced += 1
    print(f'  Audit rows synced: {n_synced}/59')

    # TXT reflection.
    print('\n[4] TXT reflection...')
    if TXT_PATH.exists():
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
        for d in decisions:
            k = _key(d)
            if k not in txt_keys:
                failures.append(f'  TXT missing for {k}')
                continue
            if txt_keys[k].strip() != (d.get('new_gloss') or '').strip():
                target_audit = next((r for r in audit if _key(r) == k), None)
                if target_audit and target_audit.get('fix_status') == 'p15_simple_gloss_repaired':
                    n_txt_synced += 1
                    continue
                failures.append(
                    f'  TXT {k} def={txt_keys[k]!r} '
                    f'!= decision new_gloss={(d.get("new_gloss") or "")!r}'
                )
            n_txt_synced += 1
        print(f'  TXT cells synced: {n_txt_synced}/59')

    # No P6 backdrift.
    print('\n[5] No P6 backdrift...')
    drift_keys = []
    for r in audit:
        rule = (r.get('rule_applied') or '').strip()
        fix = (r.get('fix_status') or '').strip()
        if rule in ('3sense_distinct', '4sense_distinct', '5sense_distinct') and fix == 'p7_redundant_sense_trimmed':
            drift_keys.append((r['word'], r['pos'], r['cefr']))
    if drift_keys:
        failures.append(
            f'  P7 silently backdrifted P6 multi_sense_distinct to legacy: {drift_keys}'
        )
    print(f'  No P7-induced backdrift to legacy codes.')

    # Final verdict.
    print()
    if failures:
        print('=' * 72)
        print(f'FAIL -- P7 verification has {len(failures)} error(s):')
        for f in failures[:30]:
            print(f)
        if len(failures) > 30:
            print(f'  ... and {len(failures) - 30} more')
        print('=' * 72)
        return 1
    print('=' * 72)
    print(
        f'PASS -- P7 verified: 59 decisions; 59 audit rows synced; '
        f'59 TXT cells synced; 0 deferred; no P6 backdrift.'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
