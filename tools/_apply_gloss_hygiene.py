"""Apply P0 gloss hygiene cleanup.

Per user plan (2026-06-21, "P0 Gloss Hygiene Cleanup"):

  1. Unescape literal ``\\|`` → ``|`` in gloss text.
  2. Normalize pipe spacing to compact.
  3. Recompute ``separator`` and ``gloss_word_count`` (validator's rule).
  4. Remove only EXACT duplicate rows (full canonical tuple match),
     preserving first occurrence / file order.

Touches:
  - ``data/curated/deck_audit.jsonl``
  - ``data/audit_expanded_needs_gloss_filled.jsonl``
  - ``data/build/anki_notes.txt`` — only Definition column (col index 6).

Backups:
  - Each target gets a ``.bak_pre_gloss_hygiene_<timestamp>`` next to it.

Usage:
  python -m tools._apply_gloss_hygiene           # apply
  python -m tools._apply_gloss_hygiene --dry-run # preview only
  python -m tools._apply_gloss_hygiene --no-dedup # skip dedup pass (hygiene only)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ProjectPaths

paths = ProjectPaths(PROJECT_ROOT)

from src.deck_builder.gloss_hygiene import (  # noqa: E402
    normalize_gloss,
    compact_pipe_in_text,
)

MASTER_AUDIT = paths.deck_audit_jsonl
EXPANDED_FILLED = PROJECT_ROOT / 'data' / 'audit_expanded_needs_gloss_filled.jsonl'
DECK_TXT = paths.anki_notes_txt

# Field names in canonical order used for "exact duplicate" detection.
CANONICAL_FIELDS = (
    'word', 'pos', 'cefr', 'def_before', 'gloss_after', 'separator',
    'rule_applied', 'gloss_word_count', 'gate_status', 'source', 'fix_status',
)


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + f'.bak_pre_gloss_hygiene_{_ts()}')
    bak.write_bytes(path.read_bytes())
    return bak


# =============================================================================
# Audit JSONL files
# =============================================================================

def apply_audit(path: Path, *, dry_run: bool, dedup: bool) -> dict:
    """Apply hygiene + optional dedup to an audit JSONL file.

    Returns stats dict.
    """
    stats = Counter(
        total=0,
        gloss_normalized=0,           # gloss_after was mutated by hygiene
        sep_field_updated=0,          # separator field changed
        wc_field_updated=0,           # gloss_word_count field changed
        unescaped_pipe=0,             # \\| → |
        pipe_spacing_compacted=0,
        deduped_exact=0,
        rows_in=0,
        rows_out=0,
    )

    rows_in = []
    with path.open(encoding='utf-8') as fp:
        for line in fp:
            if not line.strip():
                continue
            rows_in.append(json.loads(line))

    stats['rows_in'] = len(rows_in)

    new_rows = []
    seen_canonical: set[tuple] = set()
    for r in rows_in:
        stats['total'] += 1
        row_changed = False

        # Normalize gloss_after if present.
        g = r.get('gloss_after')
        if isinstance(g, str) and g.strip():
            res = normalize_gloss(g)
            if res.unescaped_pipe:
                stats['unescaped_pipe'] += 1
                row_changed = True
            if res.pipe_spacing_compacted:
                stats['pipe_spacing_compacted'] += 1
                row_changed = True
            if res.gloss != g:
                r['gloss_after'] = res.gloss
                stats['gloss_normalized'] += 1
                row_changed = True
            # Recompute separator + word count (overwrite manual metadata).
            old_sep = r.get('separator')
            new_sep = res.separator
            if old_sep != new_sep:
                stats['sep_field_updated'] += 1
                r['separator'] = new_sep
                row_changed = True
            old_wc = r.get('gloss_word_count')
            new_wc = res.gloss_word_count
            if old_wc != new_wc:
                stats['wc_field_updated'] += 1
                r['gloss_word_count'] = new_wc
                row_changed = True

        # Dedup: only exact tuple match (preserves first occurrence).
        if dedup:
            canon = tuple(r.get(k) for k in CANONICAL_FIELDS)
            if canon in seen_canonical:
                stats['deduped_exact'] += 1
                continue
            seen_canonical.add(canon)

        new_rows.append(r)

    stats['rows_out'] = len(new_rows)

    if not dry_run and (stats['gloss_normalized'] or stats['deduped_exact']
                       or stats['sep_field_updated'] or stats['wc_field_updated']):
        # Atomic write via tmp + rename.
        tmp = path.with_suffix(path.suffix + '.tmp_hygiene')
        with tmp.open('w', encoding='utf-8', newline='') as fp:
            for r in new_rows:
                fp.write(json.dumps(r, ensure_ascii=False))
                fp.write('\n')
        tmp.replace(path)

    return dict(stats)


# =============================================================================
# TXT deck file
# =============================================================================

def apply_txt(path: Path, *, dry_run: bool) -> dict:
    """Apply hygiene to the Definition column (index 6) of the TXT deck file.

    The 6 leading ``#`` comment lines are preserved verbatim. Only the def
    column is touched — examples / audio / tags / etc. are passed through.
    """
    stats = Counter(
        total=0,
        def_normalized=0,
        unescaped_pipe=0,
        pipe_spacing_compacted=0,
        rows_in=0,
        rows_out=0,
    )

    raw_lines = path.read_text(encoding='utf-8').splitlines(keepends=False)

    # Identify the header comment block (first 6 lines starting with '#').
    header_lines = []
    body_start = 0
    for i, line in enumerate(raw_lines):
        if line.startswith('#'):
            header_lines.append(line)
        else:
            body_start = i
            break
    else:
        body_start = len(raw_lines)

    body_lines = raw_lines[body_start:]
    new_body = []
    for line in body_lines:
        if not line.strip():
            new_body.append(line)
            continue
        stats['rows_in'] += 1
        # Split on tab — but be careful with tabs inside quoted fields.
        # Anki's TXT uses no quoting for tabs in def, so split works.
        fields = line.split('\t')
        if len(fields) <= 6:
            # Defensive: row doesn't have a def column, pass through.
            new_body.append(line)
            continue
        def_col = fields[6]
        new_def, changed = compact_pipe_in_text(def_col)
        if changed:
            stats['def_normalized'] += 1
            # Reconstruct: only update def column. Pad back to original field count.
            fields[6] = new_def
            new_line = '\t'.join(fields)
            new_body.append(new_line)
            if '\\|' in def_col:
                stats['unescaped_pipe'] += 1
            if ' | ' in def_col or ' |' in def_col or '| ' in def_col:
                stats['pipe_spacing_compacted'] += 1
        else:
            new_body.append(line)
        stats['rows_out'] += 1

    if not dry_run and stats['def_normalized']:
        # Write back: header + body + trailing newline (preserve original behavior).
        all_lines = header_lines + new_body
        text_out = '\n'.join(all_lines) + '\n'
        tmp = path.with_suffix(path.suffix + '.tmp_hygiene')
        tmp.write_text(text_out, encoding='utf-8')
        tmp.replace(path)

    return dict(stats)


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description='Apply P0 gloss hygiene cleanup.')
    ap.add_argument('--dry-run', action='store_true',
                    help='Preview without writing.')
    ap.add_argument('--no-dedup', action='store_true',
                    help='Skip the exact-duplicate dedup pass.')
    ap.add_argument('--targets', nargs='*',
                    choices=['master', 'filled', 'txt'],
                    help='Limit which files to touch (default: all).')
    args = ap.parse_args()

    targets = args.targets or ['master', 'filled', 'txt']
    do_dedup = not args.no_dedup

    print('=' * 72)
    print(f'P0 Gloss Hygiene Cleanup  (dry-run={args.dry_run}, dedup={do_dedup})')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # --- Audit: master ---
    if 'master' in targets:
        print(f'\n[1/3] {MASTER_AUDIT.name}')
        if not args.dry_run:
            bak = backup(MASTER_AUDIT)
            print(f'  backup: {bak.name}')
        s = apply_audit(MASTER_AUDIT, dry_run=args.dry_run, dedup=do_dedup)
        print(f'  rows: in={s["rows_in"]} out={s["rows_out"]}')
        print(f'  gloss normalized: {s["gloss_normalized"]}')
        print(f'  separator field updated: {s["sep_field_updated"]}')
        print(f'  wc field updated: {s["wc_field_updated"]}')
        print(f'  unescaped pipe: {s["unescaped_pipe"]}')
        print(f'  pipe spacing compacted: {s["pipe_spacing_compacted"]}')
        print(f'  exact duplicates removed: {s["deduped_exact"]}')

    # --- Audit: filled ---
    if 'filled' in targets:
        print(f'\n[2/3] {EXPANDED_FILLED.name}')
        if not args.dry_run:
            bak = backup(EXPANDED_FILLED)
            print(f'  backup: {bak.name}')
        s = apply_audit(EXPANDED_FILLED, dry_run=args.dry_run, dedup=do_dedup)
        print(f'  rows: in={s["rows_in"]} out={s["rows_out"]}')
        print(f'  gloss normalized: {s["gloss_normalized"]}')
        print(f'  separator field updated: {s["sep_field_updated"]}')
        print(f'  wc field updated: {s["wc_field_updated"]}')
        print(f'  unescaped pipe: {s["unescaped_pipe"]}')
        print(f'  pipe spacing compacted: {s["pipe_spacing_compacted"]}')
        print(f'  exact duplicates removed: {s["deduped_exact"]}')

    # --- TXT ---
    if 'txt' in targets:
        print(f'\n[3/3] {DECK_TXT.name}')
        if not args.dry_run:
            bak = backup(DECK_TXT)
            print(f'  backup: {bak.name}')
        s = apply_txt(DECK_TXT, dry_run=args.dry_run)
        print(f'  rows: in={s["rows_in"]} out={s["rows_out"]}')
        print(f'  def cells normalized: {s["def_normalized"]}')
        print(f'  unescaped pipe: {s["unescaped_pipe"]}')
        print(f'  pipe spacing compacted: {s["pipe_spacing_compacted"]}')

    print('\nDone.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
