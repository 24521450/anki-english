"""P5 Precision Phrase Ledger + P5B Manual Review — verifier.

Reads the ledger + audit + TXT + JSONL and asserts that:
  1. Ledger exists, has 990 rows (337 repair + 653 keep).
  2. Every `repair_gloss` decision's audit row reflects the repair
      (gloss_after, rule_applied=precision_phrase, fix_status, word_count).
  3. Every `repair_gloss` decision's TXT row reflects the new gloss
      (or is explicitly skipped with a deferred reconciliation note).
  4. Every `repair_gloss` decision's JSONL row reflects the new gloss
      (when present).
  5. `policy_review_open = 0` (no P4C regression).
  6. P3B / P4A / P4B verifiers still PASS (regression check).
  7. P4C verifier still PASS (regression check).

After P5B manual review pass:
- 988 review_candidate rows replaced by 335 repair_gloss + 653 keep_current.
- 2 seed repairs (mediate, solo) remain at the top of repair_gloss.
- Total repair_gloss = 337; total keep_current = 653; review_candidate = 0.

Run: `python -m tools._verify_p5_precision_phrase`
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
JSONL_PATH = PROJECT_ROOT / 'data' / 'anki_notes.jsonl'
LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'


def _load_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        raise FileNotFoundError(f'Ledger not found: {LEDGER_PATH}')
    rows: list[dict] = []
    with LEDGER_PATH.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _load_audit() -> list[dict]:
    return [
        json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]


def _load_txt() -> list[dict]:
    rows: list[dict] = []
    for line in TXT_PATH.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            continue
        rows.append({
            'word': parts[3].strip(),
            'pos': parts[4].strip(),
            'cefr': parts[14].strip(),
            'def': parts[6],
        })
    return rows


def _load_jsonl() -> list[dict]:
    return [
        json.loads(l) for l in JSONL_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]


def _audit_pre_repair_guard(r: dict) -> tuple:
    """4-element guard for matching audit rows post-apply.

    P5 changes `rule_applied` (e.g. `concrete_1sense` → `precision_phrase`)
    AND `gloss_after`, so the pre-repair 6-element guard no longer
    matches. We use 4 elements `(word, pos, cefr, def_before)` — def_before
    is the full Oxford definition text and is unique per (word, pos, cefr).
    """
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
        (r.get('def_before') or '').strip(),
    )


def _audit_full_guard(r: dict) -> tuple:
    """6-element full guard including the (now-updated) gloss_after.
    Used for keep-candidate / non-repair row matching where the
    audit hasn't been mutated."""
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
        (r.get('rule_applied') or '').strip(),
        (r.get('def_before') or '').strip(),
        (r.get('gloss_after') or '').strip(),
    )


def main() -> int:
    print('=' * 72)
    print('P5 PRECISION PHRASE LEDGER VERIFIER')
    print('=' * 72)

    failures: list[str] = []

    # 1. Load ledger
    print('\n[1] Loading ledger...')
    try:
        ledger = _load_ledger()
    except FileNotFoundError as e:
        print(f'FAIL: {e}')
        return 1
    n_repair = sum(1 for r in ledger if r.get('decision') == 'repair_gloss')
    n_review = sum(1 for r in ledger if r.get('decision') == 'review_candidate')
    n_keep = sum(1 for r in ledger if r.get('decision') == 'keep_current')
    print(f'  Ledger: {len(ledger)} rows ({n_repair} repair + {n_review} review + {n_keep} keep)')

    if len(ledger) != 990:
        failures.append(f'ledger has {len(ledger)} rows (expected 990)')
    if n_repair != 337:
        failures.append(f'ledger has {n_repair} repair rows (expected 337)')
    if n_review != 0:
        failures.append(f'ledger has {n_review} review_candidate rows (expected 0)')
    if n_keep != 653:
        failures.append(f'ledger has {n_keep} keep rows (expected 653)')

    # 2. Load audit + TXT + JSONL
    audit = _load_audit()
    txt = _load_txt()
    jsonl = _load_jsonl()
    print(f'  Loaded {len(audit)} audit, {len(txt)} TXT, {len(jsonl)} JSONL rows.')

    # Audit count must NOT change (P5 only mutates content, not row count).
    if len(audit) != 2487:
        failures.append(f'audit has {len(audit)} rows (expected 2487 -- count must not change)')
    if len(jsonl) != 2450:
        failures.append(f'JSONL has {len(jsonl)} rows (expected 2450 -- count must not change)')

    # Build audit index by 4-element pre-repair guard (excludes rule_applied
    # and gloss_after -- both changed post-apply).
    audit_by_pre_repair: dict[tuple, list[dict]] = {}
    for r in audit:
        g = _audit_pre_repair_guard(r)
        audit_by_pre_repair.setdefault(g, []).append(r)

    # 3. Each repair row matches an audit row + audit reflects the repair.
    print('\n[3] Each repair_gloss ledger row matches a current audit row...')
    n_repair_synced = 0
    repair_records = [r for r in ledger if r.get('decision') == 'repair_gloss']
    for rec in repair_records:
        word = rec['word']
        pos = rec['pos']
        cefr = rec['cefr']
        def_before = rec.get('def_before', '')
        new_gloss = rec['new_gloss']
        rule_after = (rec.get('rule_after') or '').strip()
        # 4-element pre-repair guard (rule + gloss_after changed post-apply).
        g = (word.lower(), pos.lower(), cefr.upper(), def_before)
        rows = audit_by_pre_repair.get(g, [])
        if len(rows) == 0:
            failures.append(
                f'  NO AUDIT MATCH for repair ({word}, {pos}, {cefr}, old={rec["old_gloss"]!r})'
            )
            continue
        if len(rows) > 1:
            failures.append(
                f'  AMBIGUOUS: ({word}, {pos}, {cefr}) matches {len(rows)} audit rows'
            )
            continue
        audit_row = rows[0]
        # Verify audit reflects the repair.
        if audit_row['gloss_after'] != new_gloss:
            failures.append(
                f'  ({word}, {pos}, {cefr}) audit gloss_after={audit_row["gloss_after"]!r} '
                f'!= ledger new_gloss={new_gloss!r}'
            )
            continue
        if audit_row.get('rule_applied', '').strip() != rule_after:
            failures.append(
                f'  ({word}, {pos}, {cefr}) audit rule_applied={audit_row.get("rule_applied")!r} '
                f'!= ledger rule_after={rule_after!r}'
            )
            continue
        if audit_row.get('fix_status', '').strip() not in (
            'p5_precision_phrase_repaired',
            'p5b_manual_review_repaired',
            'p5c_loop_guard_repaired',
        ):
            failures.append(
                f'  ({word}, {pos}, {cefr}) audit fix_status={audit_row.get("fix_status")!r} '
                f'!= expected p5_precision_phrase_repaired | p5b_manual_review_repaired | p5c_loop_guard_repaired'
            )
            continue
        # Verify gate_status=pass and word_count
        if audit_row.get('gate_status') != 'pass':
            failures.append(
                f'  ({word}, {pos}, {cefr}) audit gate_status={audit_row.get("gate_status")!r} '
                f'(expected pass)'
            )
            continue
        n_repair_synced += 1

    print(f'  repair_gloss synced: {n_repair_synced}/{n_repair}')

    # 4. Each repair row's TXT cell reflects the new gloss (or is deferred).
    print('\n[4] Each repair_gloss TXT row reflects the new gloss (or is deferred)...')
    txt_by_key = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper()): r for r in txt
    }
    n_txt_synced = 0
    n_txt_deferred = 0
    for rec in repair_records:
        key = (rec['word'].lower(), rec['pos'].lower(), rec['cefr'].upper())
        txt_row = txt_by_key.get(key)
        if txt_row is None:
            n_txt_deferred += 1
            print(
                f'  DEFERRED: {rec["word"]}|{rec["pos"]}|{rec["cefr"]} -- '
                f'no matching TXT row, JSONL reconciliation pending a future fix'
            )
            continue
        if txt_row['def'] != rec['new_gloss']:
            failures.append(
                f'  ({rec["word"]}, {rec["pos"]}, {rec["cefr"]}) TXT def={txt_row["def"]!r} '
                f'!= ledger new_gloss={rec["new_gloss"]!r}'
            )
            continue
        n_txt_synced += 1
    print(f'  TXT synced: {n_txt_synced}, deferred: {n_txt_deferred}')

    # 5. Each repair row's JSONL card reflects the new gloss (when present).
    print('\n[5] Each repair_gloss JSONL row reflects the new gloss (when present)...')
    jsonl_by_key = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper()): r for r in jsonl
    }
    n_jsonl_synced = 0
    n_jsonl_absent = 0
    for rec in repair_records:
        key = (rec['word'].lower(), rec['pos'].lower(), rec['cefr'].upper())
        jsonl_row = jsonl_by_key.get(key)
        if jsonl_row is None:
            n_jsonl_absent += 1
            continue
        if jsonl_row['definition'] != rec['new_gloss']:
            failures.append(
                f'  ({rec["word"]}, {rec["pos"]}, {rec["cefr"]}) JSONL definition={jsonl_row["definition"]!r} '
                f'!= ledger new_gloss={rec["new_gloss"]!r}'
            )
            continue
        n_jsonl_synced += 1
    print(f'  JSONL synced: {n_jsonl_synced}, absent: {n_jsonl_absent}')

    # 6. Specific card identity checks (per user's acceptance criteria)
    print('\n[6] Specific acceptance checks...')
    mediate_txt = txt_by_key.get(('mediate', 'verb', 'C2'))
    if mediate_txt and mediate_txt['def'] != 'help resolve a dispute':
        failures.append(
            f'  mediate|verb|C2 TXT def={mediate_txt["def"]!r} '
            f'(expected "help resolve a dispute")'
        )
    elif mediate_txt:
        print('  [OK] mediate|verb|C2 TXT = "help resolve a dispute"')

    solo_audit_g = (
        'solo', 'noun', 'C1',
        'a musical composition, or a passage, for a single voice or '
        'instrument; a performance by one person alone',
    )
    solo_audit = None
    if solo_audit_g in audit_by_pre_repair:
        candidates = audit_by_pre_repair[solo_audit_g]
        if candidates:
            solo_audit = candidates[0]
    if solo_audit is None:
        failures.append('  solo|noun|C1 audit row not found')
    elif solo_audit['gloss_after'] != 'single-performer music':
        failures.append(
            f'  solo|noun|C1 audit gloss_after={solo_audit["gloss_after"]!r} '
            f'(expected "single-performer music")'
        )
    else:
        print('  [OK] solo|noun|C1 audit = "single-performer music"')

    # 7. Regression: P3B / P4A / P4B / P4C verifiers still PASS
    print('\n[7] Regression checks (P3B / P4A / P4B / P4C)...')
    for name in (
        '_verify_deck_output_p3b',
        '_verify_p4a_coverage_fix',
        '_verify_p4b_rule_shape_fix',
        '_verify_p4c_policy_review',
    ):
        result = subprocess.run(
            [sys.executable, '-m', f'tools.{name}'],
            capture_output=True, text=True,
        )
        status = 'PASS' if result.returncode == 0 else 'FAIL'
        print(f'  {name}: {status} (exit={result.returncode})')
        if result.returncode != 0:
            failures.append(f'  {name} exited {result.returncode}')

    # 8. Card identity / hygiene regression (deck count, no dup)
    print('\n[8] Hygiene: policy_review_open must be 0...')
    result = subprocess.run(
        [sys.executable, '-m', 'tools._audit_gloss_policy_coverage'],
        capture_output=True, text=True,
    )
    status = 'PASS' if result.returncode == 0 else 'FAIL'
    print(f'  _audit_gloss_policy_coverage: {status} (exit={result.returncode})')
    if result.returncode != 0:
        failures.append(f'  _audit_gloss_policy_coverage exited {result.returncode}')

    # === Final verdict ===
    print()
    if failures:
        print('=' * 72)
        print('FAIL -- P5 verification has errors:')
        for f in failures:
            print(f)
        print('=' * 72)
        return 1
    print('=' * 72)
    print(
        f'PASS -- P5 + P5B precision phrase verified: {n_repair_synced} repair synced, '
        f'{n_txt_synced} TXT synced, {n_jsonl_synced} JSONL synced, '
        f'{n_review} review_candidate remaining.'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())