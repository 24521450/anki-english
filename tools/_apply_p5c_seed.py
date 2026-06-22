"""P5C Seed Apply -- apply `additionally` precision-phrase repair.

P5C Plan § P5C Seed Fix:
- additionally|adverb|B2: `in addition` -> `also`
- rule_applied: `precision_phrase` (unchanged)
- fix_status: `p5c_loop_guard_repaired`
- loop_type: `word_family_loop`

Updates:
- audit row: `gloss_after`, `gloss_word_count`, `fix_status`
  (separator/rule_applied stay as-is).
- TXT def cell.
- (Rebuild JSONL via build_notes after apply.)

Guardrails:
- Backups captured before any write.
- Exactly one audit row matches the (word, pos, cefr) key.
- The new gloss `also` is in BASIC_STOPWORDS (no longer a hard synonym).

Run:
  python -m tools._apply_p5c_seed              # dry-run (default)
  python -m tools._apply_p5c_seed --apply      # write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'

WORD = 'additionally'
POS = 'adverb'
CEFR = 'B2'
NEW_GLOSS = 'also'
FIX_STATUS = 'p5c_loop_guard_repaired'
LOOP_TYPE = 'word_family_loop'


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='Write changes (default: dry-run)')
    args = ap.parse_args()

    print('=' * 72)
    print(f'P5C Seed Apply -- additionally -> also (apply={args.apply})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load audit.
    audit = [
        json.loads(l)
        for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]
    print(f'\n  Loaded {len(audit)} audit rows.')

    # Find target.
    matches = [
        r for r in audit
        if (r.get('word') or '').strip().lower() == WORD.lower()
        and (r.get('pos') or '').strip().lower() == POS.lower()
        and (r.get('cefr') or '').strip().upper() == CEFR.upper()
    ]
    if len(matches) != 1:
        print(f'FATAL: expected exactly 1 audit row, got {len(matches)}')
        return 1
    target = matches[0]
    print(
        f'  Target: {WORD}|{POS}|{CEFR} '
        f'old_gloss={target["gloss_after"]!r} '
        f'rule_applied={target.get("rule_applied")!r} '
        f'fix_status={target.get("fix_status")!r}'
    )

    # Sanity: confirm old_gloss matches the plan (in addition).
    if target['gloss_after'].strip() != 'in addition':
        print(
            f'FATAL: expected old gloss "in addition", got {target["gloss_after"]!r}'
        )
        return 1

    # Sanity: confirm new_gloss passes word count + basic-stopword check.
    new_words = NEW_GLOSS.split()
    if len(new_words) > 6:
        print(f'FATAL: new gloss too long ({len(new_words)} words)')
        return 1
    if len(new_words) < 1:
        print('FATAL: new gloss empty')
        return 1

    # Build updated row.
    new_row = dict(target)
    new_row['gloss_after'] = NEW_GLOSS
    new_row['gloss_word_count'] = len(new_words)
    new_row['separator'] = 'none'
    new_row['rule_applied'] = target.get('rule_applied') or 'precision_phrase'
    new_row['fix_status'] = FIX_STATUS
    new_row['loop_type'] = LOOP_TYPE
    new_row['gate_status'] = 'pass'

    print(
        f'  New:    gloss_after={new_row["gloss_after"]!r} '
        f'rule_applied={new_row["rule_applied"]!r} '
        f'fix_status={new_row["fix_status"]!r} '
        f'loop_type={new_row["loop_type"]!r}'
    )

    if not args.apply:
        print('\n[DRY-RUN] No files written. Pass --apply to write.')
        return 0

    # === Apply ===
    print('\n[5] Writing changes...')
    audit_bak = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f'.bak_pre_p5c_seed_{_ts()}')
    txt_bak = TXT_PATH.with_suffix(TXT_PATH.suffix + f'.bak_pre_p5c_seed_{_ts()}')

    audit_bak.write_text(AUDIT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    txt_bak.write_text(TXT_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'  Audit backup:  {audit_bak.name}')
    print(f'  TXT backup:    {txt_bak.name}')

    # Write audit (replace the matched row).
    new_audit = [new_row if r is target else r for r in audit]
    assert sum(1 for r in new_audit if r is new_row) == 1
    AUDIT_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in new_audit) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote audit:   {AUDIT_PATH.name} ({len(new_audit)} rows)')

    # Write TXT (replace def cell for matching key).
    lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
    new_lines: list[str] = []
    replaced = 0
    for line in lines:
        if line.startswith('#') or not line.strip():
            new_lines.append(line)
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            new_lines.append(line)
            continue
        if (
            parts[3].strip().lower() == WORD.lower()
            and parts[4].strip().lower() == POS.lower()
            and parts[14].strip().upper() == CEFR.upper()
        ):
            parts[6] = NEW_GLOSS
            new_lines.append('\t'.join(parts))
            replaced += 1
        else:
            new_lines.append(line)
    if replaced != 1:
        print(f'FATAL: TXT replaced {replaced} rows (expected 1)')
        return 1
    TXT_PATH.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    print(f'  Wrote TXT:     {TXT_PATH.name} ({replaced} cell replaced)')

    print('\nDone. Run `python -m tools.build_notes` to regenerate JSONL.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
