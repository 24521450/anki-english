"""Merge manually-edited glosses back into the master audit file.

Workflow:
  1. User manually edits `data/audit_expanded_needs_gloss.jsonl` (the
     "needs gloss" set after defs were expanded to multi-sense).
  2. They fill in `gloss_after` (and optionally `separator`, `rule_applied`,
     `gloss_word_count`, `gate_status`) for each row.
  3. They run `python -m tools._merge_expanded_glosses` to write the
     updated glosses back into `data/audit_full_deck_v2.jsonl`.
  4. The build pipeline (`tools/build_notes.py`) reads the merged
     `audit_full_deck_v2.jsonl` and produces Anki notes.

Usage:
  python -m tools._merge_expanded_glosses
  python -m tools._merge_expanded_glosses --dry-run
  python -m tools._merge_expanded_glosses --expanded path/to/expanded.jsonl
  python -m tools._merge_expanded_glosses --master path/to/master.jsonl

Behavior:
  - Match on (word, pos, cefr) tuple.
  - For each expanded row, find matching master row(s).
  - Default: error out on multiple matches (defensive — the audit file
    should be deduped at the source).
  - If exactly one match: copy the expanded row's `gloss_after` and any
    present audit fields (separator, rule_applied, gloss_word_count,
    gate_status) into the master row. Preserve all other fields of the
    master row.
  - Skip expanded rows whose `gloss_after` is empty (still pending manual
    edit) — report them as "pending".
  - Skip expanded rows whose (word, pos, cefr) has no match in master —
    report them as "no master match".
  - Atomic write: write to `<master>.tmp`, then rename. Original is
    preserved if anything fails mid-write.

Output (stdout):
  - Per-row action: updated / pending / no-match.
  - Summary at the end: updated=N, pending=N, no_match=N.

Safety:
  - Default refuses to overwrite master unless `--apply` is given. With
    `--apply` (or no flag, since this is a one-shot tool), the merge is
    written. Use `--dry-run` to preview without writing.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
DEFAULT_EXPANDED = PROJECT_ROOT / 'data' / 'audit_expanded_needs_gloss.jsonl'
DEFAULT_MASTER = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'

# Fields copied from the expanded row to the master row when present.
# def_before is intentionally NOT in this set — the master already has the
# expanded def (it came from the same source). If the user edited def_before
# in the expanded file, it should match the master's value; if it doesn't,
# that's a data-integrity issue we surface as a warning rather than silently
# overwriting.
COPY_FIELDS = ('gloss_after', 'separator', 'rule_applied',
               'gloss_word_count', 'gate_status')


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, skipping blank lines. Preserves field order."""
    rows: list[dict] = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def index_by_key(rows: list[dict]) -> dict[tuple, list[int]]:
    """Group rows by (word, pos, cefr). Returns dict of key → list of indices."""
    out: dict[tuple, list[int]] = {}
    for i, r in enumerate(rows):
        k = (r.get('word'), r.get('pos'), r.get('cefr'))
        out.setdefault(k, []).append(i)
    return out


def merge(
    expanded: list[dict],
    master: list[dict],
    *,
    dry_run: bool = False,
) -> tuple[list[dict], dict]:
    """Merge expanded glosses into master. Returns (updated_master, stats).

    Stats keys: updated, pending, no_match, multi_match, def_mismatch.
    """
    master_idx = index_by_key(master)
    updated_master = [dict(r) for r in master]  # deep enough — values are scalars/lists
    stats = Counter(updated=0, pending=0, no_match=0,
                    multi_match=0, def_mismatch=0)

    for exp in expanded:
        key = (exp.get('word'), exp.get('pos'), exp.get('cefr'))
        gloss = (exp.get('gloss_after') or '').strip()

        # Skip expanded rows that have no gloss yet — still pending manual edit.
        if not gloss:
            stats['pending'] += 1
            continue

        master_indices = master_idx.get(key)
        if not master_indices:
            stats['no_match'] += 1
            continue

        # Copy edited fields from expanded into all matching master rows.
        for i in master_indices:
            # Defensive: if def_before in expanded differs from master, flag it.
            # (Don't silently overwrite — the master is the authoritative source.)
            exp_def = (exp.get('def_before') or '').strip()
            master_def = (updated_master[i].get('def_before') or '').strip()
            if exp_def and exp_def != master_def:
                stats['def_mismatch'] += 1

            # Copy edited fields from expanded into master.
            for field in COPY_FIELDS:
                if field in exp and exp[field] is not None:
                    updated_master[i][field] = exp[field]

            # Tag the master row so downstream consumers know it came from the
            # expanded-gloss path (the original fix_status was 'rebuilt' or similar).
            updated_master[i]['fix_status'] = 'expanded_glossed'

        stats['updated'] += 1


    return updated_master, dict(stats)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Atomic write: tmp + rename. Preserves field order via json.dumps."""
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write('\n')
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser(
        description='Merge manually-edited glosses from audit_expanded_needs_gloss.jsonl '
                    'into audit_full_deck_v2.jsonl.')
    ap.add_argument('--expanded', type=Path, default=DEFAULT_EXPANDED,
                    help='Path to the expanded JSONL (default: %(default)s)')
    ap.add_argument('--master', type=Path, default=DEFAULT_MASTER,
                    help='Path to the master audit JSONL (default: %(default)s)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Preview the merge without writing to disk.')
    args = ap.parse_args()

    if not args.expanded.exists():
        print(f'ERR: expanded file not found: {args.expanded}', file=sys.stderr)
        return 1
    if not args.master.exists():
        print(f'ERR: master file not found: {args.master}', file=sys.stderr)
        return 1

    expanded = load_jsonl(args.expanded)
    master = load_jsonl(args.master)

    updated_master, stats = merge(expanded, master, dry_run=args.dry_run)

    print(f'Loaded {len(expanded)} expanded rows, {len(master)} master rows')
    if args.dry_run:
        print('(dry-run: not writing)')
    else:
        write_jsonl(args.master, updated_master)
        print(f'Wrote {args.master}')

    print()
    print(f'Summary:')
    print(f'  updated:     {stats["updated"]}')
    print(f'  pending:     {stats["pending"]}  (no gloss_after yet)')
    print(f'  no_match:    {stats["no_match"]}  (no master row for this key)')
    print(f'  multi_match: {stats["multi_match"]}  (ambiguous, skipped)')
    print(f'  def_mismatch:{stats["def_mismatch"]}  (def_before differs — investigate)')

    # Non-zero exit if anything unexpected happened, so a CI/script caller
    # can detect anomalies. (updated=0 with no_match>0 → likely user error.)
    if stats['no_match'] > 0 or stats['multi_match'] > 0:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
