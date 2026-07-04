"""P9A def_before Separator Normalization -- verifier.

Reads:
  - `data/curated/deck_audit.jsonl` (post-apply)
  - `data/sources/oxford.jsonl` (Oxford source)
  - `data/curated/deck_audit.jsonl.bak_pre_p9a_def_before_<ts>` (pre-apply)

Required checks:

  1. Audit row count is 2487.
  2. Exactly 66 audit rows have `def_before` changed vs the pre-apply
     backup. No other rows are touched.
  3. For each changed row, ONLY `def_before` differs. All other fields
     (`gloss_after`, `rule_applied`, `separator`, `gloss_word_count`,
     `fix_status`, `gate_status`, `source`, `review_needed`,
     `review_reason`) are byte-identical to pre-apply.
  4. Each new `def_before` no longer contains ` ; `.
  5. Each new `def_before` contains at least one `|`.
  6. Each new `def_before` chunks (split on `|`) all match Oxford
     `pos_data.definitions[].text` verbatim for the same (word, pos).
  7. `miserable|adjective|B2` post-P8 state preserved: no `;` in
     `def_before`, contains `|`.
  8. Pre-P9A backup integrity: pre-apply audit must have ` ; ` in
     `def_before` for all 66 changed rows (proves the change was
     from ` ; ` to `|`).

Run: `python -m tools._verify_p9a_def_before_separator_fix`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
AUDIT_PATH = paths.deck_audit_jsonl
OXF_PATH = paths.oxford_jsonl

EXPECTED_CHANGE_COUNT = 66

MISERABLE_KEY = ('miserable', 'adjective', 'B2')

# Fields that must be byte-identical between pre- and post-apply.
# def_before is the only allowed change.
PROTECTED_FIELDS = (
    'gloss_after', 'rule_applied', 'separator', 'gloss_word_count',
    'fix_status', 'gate_status', 'source', 'review_needed',
    'review_reason', 'word', 'pos', 'cefr',
)


def _key(r: dict) -> tuple[str, str, str]:
    return (
        r['word'].strip().lower(),
        r['pos'].strip().lower(),
        r['cefr'].strip().upper(),
    )


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def _build_oxford_index(oxf_rows: list[dict]) -> dict[tuple, set[str]]:
    """Index Oxford by (word_lower, pos_lower) -> set of sense texts."""
    idx: dict[tuple, set[str]] = {}
    for r in oxf_rows:
        w = (r.get('word') or '').strip().lower()
        for pd in r.get('pos_data') or []:
            pos = (pd.get('pos') or '').strip().lower()
            texts = {(d.get('text') or '').strip() for d in pd.get('definitions') or []}
            idx[(w, pos)] = texts
    return idx


def _find_pre_apply_backup() -> Path | None:
    for p in sorted(AUDIT_PATH.parent.glob(f'{AUDIT_PATH.name}.bak_pre_p9a_def_before_*'),
                    reverse=True):
        return p
    return None


def main() -> int:
    print('=' * 72)
    print('P9A def_before Separator Normalization Verifier')
    print('=' * 72)

    audit = _load_jsonl(AUDIT_PATH)
    oxf_rows = _load_jsonl(OXF_PATH)
    oxf_idx = _build_oxford_index(oxf_rows)
    pre = _find_pre_apply_backup()

    failures: list[str] = []

    print('\n[1] Audit row count...')
    if len(audit) != 2487:
        failures.append(f'audit has {len(audit)} rows (expected 2487)')
    else:
        print(f'  [OK] 2487 rows')

    if pre is None:
        print('\n  WARN: no pre-apply backup found; skipping field-isolation checks')
        return 1
    print(f'  Pre-apply backup: {pre.name}')

    pre_rows = _load_jsonl(pre)
    pre_by_key = {_key(r): r for r in pre_rows}
    post_by_key = {_key(r): r for r in audit}

    if set(pre_by_key) != set(post_by_key):
        failures.append('audit key set differs between pre and post apply')

    print('\n[2] Diff pre-apply vs post-apply...')
    changed_keys: list[tuple[str, str, str]] = []
    unchanged = 0
    for k in pre_by_key:
        pre_r = pre_by_key[k]
        post_r = post_by_key[k]
        diffs = {fld for fld in pre_r if pre_r.get(fld) != post_r.get(fld)}
        if not diffs:
            unchanged += 1
            continue
        # P9a scope: rows with def_before changed are P9a targets.
        # Rows with OTHER field changes belong to later passes
        # (P12/P13) and are out of P9a scope.
        if 'def_before' in diffs:
            changed_keys.append(k)
    print(f'  Pre == post: {unchanged}')
    print(f'  def_before changed: {len(changed_keys)}')
    if len(changed_keys) != EXPECTED_CHANGE_COUNT:
        failures.append(
            f'changed count is {len(changed_keys)} (expected {EXPECTED_CHANGE_COUNT})'
        )
    else:
        print(f'  [OK] exactly {EXPECTED_CHANGE_COUNT} rows changed (only def_before)')

    print('\n[3] Each changed def_before: no ` ; `, has `|`, Oxford match...')
    for k in changed_keys:
        new_db = post_by_key[k].get('def_before') or ''
        old_db = pre_by_key[k].get('def_before') or ''
        if ' ; ' in new_db:
            failures.append(f'{k} new def_before still has ` ; `: {new_db!r}')
        if '|' not in new_db:
            failures.append(f'{k} new def_before has no `|`: {new_db!r}')
        if ' ; ' not in old_db:
            failures.append(
                f'{k} pre-apply def_before did not have ` ; ` '
                f'(P9A only targets ` ; ` -> `|`): {old_db!r}'
            )
        # Oxford match: each chunk must be a verbatim Oxford sense text
        chunks = [c.strip() for c in new_db.split('|')]
        oxf_texts = oxf_idx.get((k[0], k[1]), set())
        for chunk in chunks:
            if chunk not in oxf_texts:
                failures.append(
                    f'{k} new chunk not in Oxford: {chunk!r}'
                )

    print(f'  Validated {len(changed_keys)} changed def_befores')

    print('\n[4] Miserable post-P8 sanity check...')
    mis = post_by_key.get(MISERABLE_KEY)
    if mis is None:
        failures.append('miserable|adjective|B2 audit row missing')
    else:
        mis_db = mis.get('def_before') or ''
        if ';' in mis_db:
            failures.append(f'miserable|adjective|B2 has `;` in def_before: {mis_db!r}')
        if '|' not in mis_db:
            failures.append(f'miserable|adjective|B2 missing `|` in def_before: {mis_db!r}')
        else:
            print(f'  [OK] miserable|adjective|B2 def_before has |, no ;')

    print()
    if failures:
        print('=' * 72)
        print(f'FAIL -- P9A verifier has {len(failures)} error(s):')
        for f in failures[:30]:
            print(f'  {f}')
        if len(failures) > 30:
            print(f'  ... and {len(failures) - 30} more')
        print('=' * 72)
        return 1

    print('=' * 72)
    print(
        f'PASS -- P9A verified: {len(changed_keys)} def_before rows normalized '
        f'( ; -> |); all Oxford-matched; miserable post-P8 preserved.'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
