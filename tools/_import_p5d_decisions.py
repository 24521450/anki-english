"""P5D Manual Review Decisions -- import + canonicalize (v2 file, post word-count-limit-removal).

Reads the user's v2 filled external file and writes a canonical decisions
file inside the repo (`data/manual_gloss_review_p5d_decisions.jsonl`).
The canonical file is the source of truth for the P5D apply pass.

This is the v2 pass: the v1 (`_import_p5b_decisions.py`) imported a file
where 8 long glosses had been artificially shortened to fit the 1-6
word validator cap. The v2 file has the unconstrained glosses. After
the P5D validator change (removed word-count limits), all 988 v2 rows
pass `validate_verdict` without any QA normalizations.

Input:
    `C:\\Users\\admin\\Downloads\\manual_gloss_review_p5_candidates_filled_QA_patched_v2 (1).jsonl`
    (988 rows; user-filled v2 decision / manual_gloss_after / manual_rule_after / notes)

Output:
    `data/manual_gloss_review_p5d_decisions.jsonl` (988 rows in canonical schema)

Canonical schema (same as P5B):
    {
      "word": ...,
      "pos": ...,
      "cefr": ...,
      "rule_applied": ...,
      "risk_type": ...,
      "def_before": ...,
      "old_gloss": ...,
      "decision": "repair_gloss" | "keep_current",
      "new_gloss": ...,
      "rule_after": "precision_phrase",
      "separator": "|" | ";" | "none",
      "gloss_word_count": int,
      "notes": ...,
      "qa_normalized": false,
      "qa_original": "",
      "p5d_version": "2026-06-22"
    }

Guardrails:
    - Input must have exactly 988 rows.
    - All decisions in {keep_current, repair_gloss}.
    - All repair rows pass `validate_verdict` (post P5D, word-count limits removed).
    - All keep rows have empty manual_gloss_after / manual_rule_after.
    - No duplicate (word, pos, cefr, old_gloss) guards.

Run:
    python -m tools._import_p5d_decisions
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

FILLED_PATH = Path(
    r'C:\Users\admin\Downloads\manual_gloss_review_p5_candidates_filled_QA_patched_v2 (1).jsonl'
)
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5d_decisions.jsonl'


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


def main() -> int:
    print('=' * 72)
    print('P5D MANUAL REVIEW DECISIONS -- IMPORT + CANONICALIZE (v2)')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load filled file.
    print('\n[1] Loading filled file...')
    if not FILLED_PATH.exists():
        print(f'FATAL: filled file not found: {FILLED_PATH}')
        return 1
    filled: list[dict] = []
    with FILLED_PATH.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            filled.append(json.loads(line))
    print(f'  Loaded {len(filled)} filled rows.')

    # Hard guards.
    if len(filled) != 988:
        print(f'FATAL: filled file has {len(filled)} rows (expected 988)')
        return 1

    valid_decisions = {'keep_current', 'repair_gloss'}
    n_keep = 0
    n_repair = 0
    seen_guards: dict[tuple, int] = {}
    out_rows: list[dict] = []

    from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

    for r in filled:
        word = (r.get('word') or '').strip()
        pos = (r.get('pos') or '').strip()
        cefr = (r.get('cefr') or '').strip()
        decision = (r.get('decision') or '').strip()
        rule_after = (r.get('manual_rule_after') or '').strip()
        gloss = (r.get('manual_gloss_after') or '').strip()
        notes = (r.get('notes') or '').strip()

        # Decision validity.
        if decision not in valid_decisions:
            print(f'FATAL: ({word}, {pos}, {cefr}) invalid decision={decision!r}')
            return 1

        # Guard uniqueness.
        g = (
            word.lower(), pos.lower(), cefr.upper(),
            (r.get('def_before') or '').strip(),
            (r.get('old_gloss') or '').strip(),
        )
        seen_guards[g] = seen_guards.get(g, 0) + 1

        if decision == 'keep_current':
            n_keep += 1
            if gloss:
                print(f'FATAL: ({word}, {pos}, {cefr}) keep_current but manual_gloss_after={gloss!r} set')
                return 1
            if rule_after:
                print(f'FATAL: ({word}, {pos}, {cefr}) keep_current but manual_rule_after={rule_after!r} set')
                return 1
            out_rows.append({
                'word': word,
                'pos': pos,
                'cefr': cefr,
                'rule_applied': r.get('rule_applied', ''),
                'risk_type': r.get('risk_type', ''),
                'def_before': r.get('def_before', ''),
                'old_gloss': r.get('old_gloss', ''),
                'decision': 'keep_current',
                'new_gloss': '',
                'rule_after': '',
                'separator': 'none',
                'gloss_word_count': 0,
                'notes': notes,
                'qa_normalized': False,
                'qa_original': '',
                'p5d_version': '2026-06-22',
            })
            continue

        # decision == 'repair_gloss'
        n_repair += 1
        if not gloss:
            print(f'FATAL: ({word}, {pos}, {cefr}) repair_gloss but manual_gloss_after empty')
            return 1
        if rule_after != 'precision_phrase':
            print(
                f'FATAL: ({word}, {pos}, {cefr}) repair_gloss but manual_rule_after={rule_after!r} '
                f'(expected precision_phrase)'
            )
            return 1

        # Validate (post P5D: only structure + headword checks).
        sep, wc = _compute_separator_count(gloss)
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
        v = validate_verdict(word, gloss, sep, len(chunks))
        if v:
            print(f'FATAL: ({word}, {pos}, {cefr}) gloss={gloss!r} fails validator: {v}')
            return 1

        out_rows.append({
            'word': word,
            'pos': pos,
            'cefr': cefr,
            'rule_applied': r.get('rule_applied', ''),
            'risk_type': r.get('risk_type', ''),
            'def_before': r.get('def_before', ''),
            'old_gloss': r.get('old_gloss', ''),
            'decision': 'repair_gloss',
            'new_gloss': gloss,
            'rule_after': rule_after,
            'separator': sep,
            'gloss_word_count': wc,
            'notes': notes,
            'qa_normalized': False,
            'qa_original': '',
            'p5d_version': '2026-06-22',
        })

    # Duplicate guards.
    dups = [g for g, n in seen_guards.items() if n > 1]
    if dups:
        print(f'FATAL: {len(dups)} duplicate (word, pos, cefr, def_before, old_gloss) guards')
        for g in dups[:5]:
            print(f'  {g}')
        return 1

    # Write canonical decisions file.
    print('\n[2] Writing canonical decisions...')
    DECISIONS_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in out_rows) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote {len(out_rows)} rows to {DECISIONS_PATH.name}')
    print(f'  Distribution: {n_repair} repair_gloss + {n_keep} keep_current')
    return 0


if __name__ == '__main__':
    sys.exit(main())
