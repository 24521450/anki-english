"""P7 Redundant/Minor Sense Trim -- import + canonicalize.

Reads the user's external v3 patched file
(`C:\\Users\\admin\\Downloads\\audit_full_deck_v2_multisense_patched_v3 (1).jsonl`)
and writes a canonical decisions file
(`data/redundant_sense_trim_p7_decisions.jsonl`).

P7 policy (locked 2026-06-22):
- Apply ONLY the 59 gloss-only diffs (skip metadata-only diffs like
  rule-code backdrifts from `multi_sense_distinct` to legacy labels).
- New rule codes:
  - `common_core_trimmed` -- single-chunk collapse of redundant subsenses
    (countable/uncountable, process/result, noun/verb, subtype).
  - `trimmed_multisense` -- 2+ distinct chunks kept with `|` after
    redundant-sense trim (e.g. `gut` from 5sense_distinct -> 5 chunks).
- Do NOT import v3's raw rule labels (`3sense_distinct`, `4sense_distinct`,
  `5sense_distinct`, `common_core_trimmed` raw form); recompute the
  canonical rule from the separator.
- Do NOT import v3's raw `fix_status`; normalize to
  `p7_redundant_sense_trimmed`.
- Recompute `separator` and `gloss_word_count` from the canonical gloss.
- Don't touch rows whose `gloss_after` is unchanged (e.g. `arrow`).

Canonical schema:
  {
    "word": ..., "pos": ..., "cefr": ...,
    "def_before": ..., "old_gloss": ..., "new_gloss": ...,
    "rule_after": "common_core_trimmed" | "trimmed_multisense",
    "separator": "none" | "|",
    "gloss_word_count": int,
    "fix_status": "p7_redundant_sense_trimmed",
    "notes": "p7 redundant sense trim",
    "p7_version": "2026-06-22"
  }

Guardrails:
  - External file must have exactly 2487 rows with same keyset as current.
  - Exactly 59 gloss-only diffs expected.
  - All 59 decisions' `new_gloss` must pass `validate_verdict`.
  - All 59 decisions' `gloss_word_count` must match actual count.
  - No duplicate `(word, pos, cefr)` guards.

Run: `python -m tools._import_p7_decisions`
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

V3_PATH = Path(
    r'C:\Users\admin\Downloads\audit_full_deck_v2_multisense_patched_v3 (1).jsonl'
)
CURRENT_AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'redundant_sense_trim_p7_decisions.jsonl'


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _compute_separator_count(gloss: str) -> tuple[str, int]:
    if '|' in gloss:
        sep = '|'
    elif ';' in gloss:
        sep = ';'
    else:
        sep = 'none'
    chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
    wc = sum(len(c.split()) for c in chunks)
    return sep, wc


def _key(r: dict) -> tuple[str, str, str]:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
    )


def main() -> int:
    print('=' * 72)
    print('P7 REDUNDANT SENSE TRIM -- IMPORT + CANONICALIZE')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load both files.
    print('\n[1] Loading inputs...')
    if not V3_PATH.exists():
        print(f'FATAL: v3 file not found: {V3_PATH}')
        return 1
    v3 = [json.loads(l) for l in V3_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
    current = [json.loads(l) for l in CURRENT_AUDIT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
    print(f'  v3: {len(v3)} rows')
    print(f'  current: {len(current)} rows')

    if len(v3) != 2487:
        print(f'FATAL: v3 has {len(v3)} rows (expected 2487)')
        return 1
    if len(current) != 2487:
        print(f'FATAL: current has {len(current)} rows (expected 2487)')
        return 1

    current_by_key = {_key(r): r for r in current}
    v3_by_key = {_key(r): r for r in v3}

    # Filter: gloss-only diffs (skip metadata-only backdrift rows).
    print('\n[2] Filtering to gloss-only diffs (skip metadata-only)...')
    diff_keys: list[tuple[str, str, str]] = []
    metadata_only = 0
    for k in v3_by_key:
        v = v3_by_key[k]
        c = current_by_key.get(k)
        if c is None:
            print(f'FATAL: v3 key {k} not in current audit')
            return 1
        if v['gloss_after'] != c['gloss_after']:
            diff_keys.append(k)
        else:
            metadata_only += 1
    print(f'  gloss-only diffs: {len(diff_keys)}')
    print(f'  metadata-only diffs (skipped): {metadata_only}')

    if len(diff_keys) != 59:
        print(f'FATAL: expected 59 gloss-only diffs, got {len(diff_keys)}')
        return 1

    # Build canonical decisions.
    print('\n[3] Building canonical decisions...')
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    seen_guards: dict[tuple, int] = {}
    out_rows: list[dict] = []
    validator_failures: list[str] = []
    sep_dist: dict[str, int] = {'none': 0, '|': 0, ';': 0}

    for k in diff_keys:
        word, pos, cefr = k
        v = v3_by_key[k]
        c = current_by_key[k]

        old_gloss = (c.get('gloss_after') or '').strip()
        new_gloss = (v.get('gloss_after') or '').strip()

        # Recompute separator + word_count from canonical gloss.
        sep, wc = _compute_separator_count(new_gloss)
        sep_dist[sep] += 1

        # Normalize rule: separator=none -> common_core_trimmed; else trimmed_multisense.
        rule_after = 'common_core_trimmed' if sep == 'none' else 'trimmed_multisense'

        # Validate.
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', new_gloss) if c.strip()]
        v_errors = validate_verdict(word, new_gloss, sep, len(chunks))
        if v_errors:
            validator_failures.append(
                f'  ({word}, {pos}, {cefr}) gloss={new_gloss!r} fails validator: {v_errors}'
            )
            continue

        # Duplicate guard.
        g = (word, pos, cefr)
        seen_guards[g] = seen_guards.get(g, 0) + 1

        out_rows.append({
            'word': v.get('word', word),
            'pos': pos,
            'cefr': cefr,
            'def_before': (v.get('def_before') or c.get('def_before') or ''),
            'old_gloss': old_gloss,
            'new_gloss': new_gloss,
            'rule_after': rule_after,
            'separator': sep,
            'gloss_word_count': wc,
            'fix_status': 'p7_redundant_sense_trimmed',
            'notes': 'p7 redundant sense trim',
            'p7_version': '2026-06-22',
        })

    if validator_failures:
        print('FATAL: validator failures:')
        for f in validator_failures:
            print(f)
        return 1

    dups = [g for g, n in seen_guards.items() if n > 1]
    if dups:
        print(f'FATAL: {len(dups)} duplicate guards')
        return 1

    # Distribution check.
    n_single = sep_dist['none']
    n_multi = sep_dist['|'] + sep_dist[';']
    print(f'  Built {len(out_rows)} decisions')
    print(f'  Single-chunk (common_core_trimmed): {n_single}')
    print(f'  Multi-chunk (trimmed_multisense): {n_multi}')
    if n_single + n_multi != 59:
        print(f'FATAL: split does not sum to 59 ({n_single} + {n_multi})')
        return 1

    # Write canonical decisions.
    print('\n[4] Writing canonical decisions...')
    DECISIONS_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in out_rows) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote {len(out_rows)} rows to {DECISIONS_PATH.name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
