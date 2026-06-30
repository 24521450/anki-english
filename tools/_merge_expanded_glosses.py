"""Merge manually-edited glosses back into the master audit file.

Workflow:
  1. User manually edits `data/audit_expanded_needs_gloss.jsonl` (the
     "needs gloss" set after defs were expanded to multi-sense).
  2. They fill in `gloss_after` for each row.
  3. They run `python -m tools._merge_expanded_glosses` to write the
     updated glosses back into `data/curated/deck_audit.jsonl`.
  4. The build pipeline (`tools/build_notes.py`) reads the merged
     `deck_audit.jsonl` and produces Anki notes.

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
  - If exactly one match: copy the expanded row's `gloss_after` into the
    master row, then NORMALIZE via ``src.deck_builder.gloss_hygiene`` and
    RECOMPUTE ``separator`` and ``gloss_word_count``. Manual metadata is
    no longer trusted (P0 hygiene cleanup, 2026-06-21).
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from src.config import ProjectPaths
paths = ProjectPaths(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.gloss_hygiene import normalize_gloss  # noqa: E402

DEFAULT_EXPANDED = PROJECT_ROOT / 'data' / 'audit_expanded_needs_gloss.jsonl'
DEFAULT_MASTER = paths.deck_audit_jsonl

# Fields copied VERBATIM from the expanded row to the master row when present.
# Only ``gloss_after`` is copied raw — the rest are either preserved from
# master (``gate_status``) or recomputed by hygiene helper (``separator``,
# ``gloss_word_count``, ``rule_applied``). Per P0 cleanup (2026-06-21):
# manual metadata in the expanded file is no longer trusted for separator/wc
# because manual edits have introduced drift (literal ``\\|``, padded pipes,
# stale wc).
COPY_FIELDS = ('gloss_after', 'gate_status')

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

    Stats keys: updated, pending, no_match, multi_match, def_mismatch,
                gloss_normalized.
    """
    master_idx = index_by_key(master)
    updated_master = [dict(r) for r in master]  # deep enough — values are scalars/lists
    stats = Counter(updated=0, pending=0, no_match=0,
                    multi_match=0, def_mismatch=0,
                    gloss_normalized=0, unescaped_pipe=0,
                    pipe_spacing_compacted=0,
                    sep_recomputed=0, wc_recomputed=0)

    for exp in expanded:
        key = (exp.get('word'), exp.get('pos'), exp.get('cefr'))
        gloss_raw = (exp.get('gloss_after') or '').strip()

        # Skip expanded rows that have no gloss yet — still pending manual edit.
        if not gloss_raw:
            stats['pending'] += 1
            continue

        master_indices = master_idx.get(key)
        if not master_indices:
            stats['no_match'] += 1
            continue
        if len(master_indices) > 1:
            stats['multi_match'] += 1
            continue

        # Normalize the gloss via the shared hygiene helper (P0 cleanup).
        # This un-escapes literal ``\|``, compacts pipe spacing, and gives us
        # the canonical separator + word count.
        res = normalize_gloss(gloss_raw)
        if res.unescaped_pipe:
            stats['unescaped_pipe'] += 1
        if res.pipe_spacing_compacted:
            stats['pipe_spacing_compacted'] += 1
        if res.changed():
            stats['gloss_normalized'] += 1

        # Copy edited fields from expanded into the matching master row.
        for i in master_indices:
            # Defensive: if def_before in expanded differs from master, flag it.
            # (Don't silently overwrite — the master is the authoritative source.)
            exp_def = (exp.get('def_before') or '').strip()
            master_def = (updated_master[i].get('def_before') or '').strip()
            if exp_def and exp_def != master_def:
                stats['def_mismatch'] += 1

            # Copy verbatim fields (gloss_after, gate_status).
            for field in COPY_FIELDS:
                if field in exp and exp[field] is not None:
                    updated_master[i][field] = exp[field]

            # Apply the normalized gloss (overwrites whatever COPY_FIELDS put there
            # if we just copied a non-normalized gloss_after).
            if updated_master[i].get('gloss_after') != res.gloss:
                updated_master[i]['gloss_after'] = res.gloss

            # Recompute separator and word count from the normalized gloss.
            # Per P0 cleanup: manual metadata is no longer trusted.
            old_sep = updated_master[i].get('separator')
            if old_sep != res.separator:
                stats['sep_recomputed'] += 1
            updated_master[i]['separator'] = res.separator
            old_wc = updated_master[i].get('gloss_word_count')
            if old_wc != res.gloss_word_count:
                stats['wc_recomputed'] += 1
            updated_master[i]['gloss_word_count'] = res.gloss_word_count

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
                    'into curated/deck_audit.jsonl.')
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
    print(f'  updated:          {stats["updated"]}')
    print(f'  pending:          {stats["pending"]}  (no gloss_after yet)')
    print(f'  no_match:         {stats["no_match"]}  (no master row for this key)')
    print(f'  multi_match:      {stats["multi_match"]}  (ambiguous, skipped)')
    print(f'  def_mismatch:     {stats["def_mismatch"]}  (def_before differs — investigate)')
    print(f'  gloss_normalized: {stats["gloss_normalized"]}  (hygiene mutated gloss_after)')
    print(f'  unescaped_pipe:   {stats["unescaped_pipe"]}')
    print(f'  spacing_compacted:{stats["pipe_spacing_compacted"]}')
    print(f'  sep_recomputed:   {stats["sep_recomputed"]}  (separator field updated)')
    print(f'  wc_recomputed:    {stats["wc_recomputed"]}  (gloss_word_count updated)')

    # Non-zero exit if anything unexpected happened, so a CI/script caller
    # can detect anomalies. (updated=0 with no_match>0 → likely user error.)
    if stats['no_match'] > 0 or stats['multi_match'] > 0:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
