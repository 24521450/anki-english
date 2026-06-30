"""P6 Multisense Hard-Drop Repair -- import + canonicalize.

Reads the user's external patched file
(`C:\\Users\\admin\\Downloads\\audit_full_deck_v2_multisense_patched.jsonl`)
and writes a canonical decisions file inside the repo
(`data/multisense_harddrop_p6_decisions.jsonl`).

The canonical file is the source of truth for the P6 apply pass.

P6 policy (locked 2026-06-22):
- 117 rows patched by user to avoid hard-dropping distinct senses.
- New rule code `multi_sense_distinct` supersedes the legacy `3sense_distinct`
  / `4sense_distinct`. P6 imports normalize all P6 rows to `multi_sense_distinct`.
- The validator (`validate_verdict`) keeps structure + headword-leak checks.
  Word-count limits were already removed in P5D.
- The legacy "NEVER pick 3" rule is RETIRED for distinct multisense cases;
  P6 keeps all high-value distinct senses with `|`.

Input (external):
  Full audit master (2487 rows) where 117 rows differ from current audit.
  The import identifies the 117 diffs and treats ONLY those as P6 decisions.
  The remaining 2370 unchanged rows are ignored.

Normalization applied during import (per P6 plan):
  1. Hard-coded headword-leak fixes for 8 raw-validator-failure rows:
     arrow, compound, democratic, lens, patrol, squad, tap, top.
  2. `rule_applied` is normalized to `multi_sense_distinct` for ALL 117 rows.
  3. `separator` and `gloss_word_count` are RECOMPUTED from the new gloss
     (do not trust external metadata blindly).
  4. `fix_status` is set to `p6_multisense_harddrop_repaired`.

Canonical schema:
  {
    "word": ..., "pos": ..., "cefr": ...,
    "def_before": ..., "old_gloss": ..., "new_gloss": ...,
    "old_rule": "...",                # rule from CURRENT audit (pre-P6)
    "rule_after": "multi_sense_distinct",
    "separator": "|",
    "gloss_word_count": int,
    "fix_status": "p6_multisense_harddrop_repaired",
    "notes": "..."                    # source provenance
  }

Guardrails:
  - External file must have exactly 2487 rows with the same keyset as
    current audit.
  - Exactly 117 diffs expected.
  - All 8 raw validator failures must be normalized to pass `validate_verdict`.
  - All 117 decisions must use `rule_after = multi_sense_distinct`.
  - No duplicate `(word, pos, cefr)` guards.
  - `gloss_word_count` must match actual count.

Run: `python -m tools._import_p6_multisense`
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

PATCHED_PATH = Path(
    r'C:\Users\admin\Downloads\audit_full_deck_v2_multisense_patched.jsonl'
)
CURRENT_AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'multisense_harddrop_p6_decisions.jsonl'

# Hard-coded headword-leak normalizations for the 8 raw-validator-failure
# rows. The replacement gloss moves the headword OUT of the chunk where
# it was leaking (preserves semantic content + drops the literal headword
# token from the gloss).
HEADWORD_LEAK_FIXES: dict[tuple[str, str, str], str] = {
    ('arrow', 'noun', 'B2'): 'bow projectile|direction mark',
    ('compound', 'noun', 'B2'): 'combined thing|chemical substance|word combination',
    ('democratic', 'adjective', 'B2'): 'people-ruled|member-equal|socially equal|US party-related',
    ('lens', 'noun', 'B2'): 'curved seeing glass|camera glass|contact eyewear',
    ('patrol', 'noun, verb', 'C1'): 'checking round|security group|go round checking',
    ('squad', 'noun', 'C1'): 'police unit|sports team|soldier group',
    ('tap', 'noun, verb', 'B2'): 'water valve|light touch|touch lightly|rhythmic beat',
    ('top', 'verb', 'C1'): 'exceed|rank first|place above',
}


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
    print('P6 MULTISENSE HARD-DROP REPAIR -- IMPORT + CANONICALIZE')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load both files.
    print('\n[1] Loading inputs...')
    if not PATCHED_PATH.exists():
        print(f'FATAL: patched file not found: {PATCHED_PATH}')
        return 1
    patched = [json.loads(l) for l in PATCHED_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
    current = [json.loads(l) for l in CURRENT_AUDIT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
    print(f'  patched: {len(patched)} rows')
    print(f'  current: {len(current)} rows')

    if len(patched) != 2487:
        print(f'FATAL: patched has {len(patched)} rows (expected 2487)')
        return 1
    if len(current) != 2487:
        print(f'FATAL: current has {len(current)} rows (expected 2487)')
        return 1

    current_by_key = {_key(r): r for r in current}
    patched_by_key = {_key(r): r for r in patched}

    # Find 117 diffs.
    print('\n[2] Computing diffs (117 expected)...')
    diff_keys: list[tuple[str, str, str]] = []
    for k in patched_by_key:
        p = patched_by_key[k]
        c = current_by_key.get(k)
        if c is None:
            print(f'FATAL: patched key {k} not in current audit')
            return 1
        if p['gloss_after'] != c['gloss_after']:
            diff_keys.append(k)
    print(f'  diffs: {len(diff_keys)}')
    if len(diff_keys) != 117:
        print(f'FATAL: expected 117 diffs, got {len(diff_keys)}')
        return 1

    # Build canonical decisions.
    print('\n[3] Building canonical decisions...')
    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    seen_guards: dict[tuple, int] = {}
    out_rows: list[dict] = []
    validator_failures: list[str] = []

    for k in diff_keys:
        word, pos, cefr = k
        p = patched_by_key[k]
        c = current_by_key[k]

        old_gloss = (c.get('gloss_after') or '').strip()
        old_rule = (c.get('rule_applied') or '').strip()
        raw_gloss = (p.get('gloss_after') or '').strip()

        # Apply headword-leak fix if this key has one.
        fix_key = (word, pos, cefr)
        if fix_key in HEADWORD_LEAK_FIXES:
            canonical_gloss = HEADWORD_LEAK_FIXES[fix_key]
            qa_applied = (canonical_gloss != raw_gloss)
        else:
            canonical_gloss = raw_gloss
            qa_applied = False

        # Recompute separator and word_count from canonical gloss.
        sep, wc = _compute_separator_count(canonical_gloss)

        # Validate.
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', canonical_gloss) if c.strip()]
        v = validate_verdict(word, canonical_gloss, sep, len(chunks))
        if v:
            validator_failures.append(
                f'  ({word}, {pos}, {cefr}) gloss={canonical_gloss!r} fails validator: {v}'
            )
            continue

        # Rule is always normalized to multi_sense_distinct.
        rule_after = 'multi_sense_distinct'

        # Duplicate guard.
        g = (word, pos, cefr)
        seen_guards[g] = seen_guards.get(g, 0) + 1

        out_rows.append({
            'word': p.get('word', word),
            'pos': pos,
            'cefr': cefr,
            'def_before': (p.get('def_before') or c.get('def_before') or ''),
            'old_gloss': old_gloss,
            'new_gloss': canonical_gloss,
            'old_rule': old_rule,
            'rule_after': rule_after,
            'separator': sep,
            'gloss_word_count': wc,
            'fix_status': 'p6_multisense_harddrop_repaired',
            'notes': 'p6 multisense hard-drop repair',
            'qa_normalized': qa_applied,
            'qa_original': raw_gloss if qa_applied else '',
            'p6_version': '2026-06-22',
        })

    if validator_failures:
        print('FATAL: validator failures:')
        for f in validator_failures:
            print(f)
        return 1

    # Duplicate guards.
    dups = [g for g, n in seen_guards.items() if n > 1]
    if dups:
        print(f'FATAL: {len(dups)} duplicate (word, pos, cefr) guards')
        for g in dups[:5]:
            print(f'  {g}')
        return 1

    # Distribution check.
    n_qa = sum(1 for r in out_rows if r['qa_normalized'])
    print(f'  Built {len(out_rows)} decisions ({n_qa} QA-normalized)')

    # Write canonical decisions.
    print('\n[4] Writing canonical decisions...')
    DECISIONS_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in out_rows) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote {len(out_rows)} rows to {DECISIONS_PATH.name}')
    print(f'  All decisions use rule_after = multi_sense_distinct')
    return 0


if __name__ == '__main__':
    sys.exit(main())
