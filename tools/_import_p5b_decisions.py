"""P5b Manual Review Decisions — import + canonicalize.

Reads the user's filled external file and writes a canonical decisions
file inside the repo (`data/manual_gloss_review_p5_decisions.jsonl`).
The canonical file is the source of truth for downstream apply.

Input:
    `C:\\Users\\admin\\Downloads\\manual_gloss_review_p5_candidates_filled_QA_patched.jsonl`
    (988 rows; user-filled decision / manual_gloss_after / manual_rule_after / notes)

Output:
    `data/manual_gloss_review_p5_decisions.jsonl` (988 rows in canonical schema)

QA normalizations:
    The user's filled file contains 7 rows whose `manual_gloss_after`
    fails `validate_verdict`. These are normalized to canonical glosses
    that pass the gate before being written. The set of normalizations
    is hard-coded and validated exhaustively: any unanticipated
    validator failure aborts the run.

Canonical schema:
    {
      "word": ...,
      "pos": ...,
      "cefr": ...,
      "rule_applied": ...,
      "risk_type": ...,
      "def_before": ...,
      "old_gloss": ...,
      "decision": "repair_gloss" | "keep_current",
      "new_gloss": ...,                  # filled from manual_gloss_after
      "rule_after": "precision_phrase",  # filled from manual_rule_after
      "separator": "|" | ";" | "none",   # inferred from new_gloss
      "gloss_word_count": int,           # inferred
      "notes": ...,
      "qa_normalized": bool,             # True iff QA override applied
      "qa_original": "..."               # original gloss if normalized
    }

Guardrails:
    - Input must have exactly 988 rows.
    - All decisions must be in {keep_current, repair_gloss}.
    - All repair rows must pass `validate_verdict` after QA normalization.
    - All keep rows must have empty `manual_gloss_after` / `manual_rule_after`.
    - No duplicate `(word, pos, cefr, old_gloss)` guards.
    - Every row's `(word, pos, cefr, def_before, old_gloss)` must match
      a row in the P5 ledger with `decision == "review_candidate"`.

Run:
    python -m tools._import_p5b_decisions
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
    r'C:\Users\admin\Downloads\manual_gloss_review_p5_candidates_filled_QA_patched.jsonl'
)
P5_LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5_decisions.jsonl'

# 7 known QA normalizations: current invalid gloss -> canonical gloss.
# Verified exhaustively against `validate_verdict` (see _diag_p5b_validate_check
# removed after verification; QA overrides are the ONLY known rewriters).
QA_NORMALIZATIONS: dict[str, str] = {
    'burst|verb|C1': 'break open|move suddenly|be full',
    'compromise|noun, verb|C1': 'agreement by concession|lower standards|endanger',
    'outrage|noun, verb|C1': 'shock anger|wrong act|enrage',
    'overwhelm|verb|C1': 'affect strongly|defeat|overload',
    'pop|verb|C1': 'short sound|burst|go/put/appear quickly',
    'punk|noun|B2': 'rock subculture member',
    'whip|verb|C1': 'strike|move suddenly|mix fast',
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


def _qa_key(word: str, pos: str, cefr: str) -> str:
    return f'{word.strip().lower()}|{pos.strip().lower()}|{cefr.strip().upper()}'


def main() -> int:
    print('=' * 72)
    print('P5B MANUAL REVIEW DECISIONS -- IMPORT + CANONICALIZE')
    print(f'Timestamp: {_ts()}')
    print('=' * 72)

    # Load P5 ledger (for review_candidate membership guard).
    print('\n[1] Loading P5 ledger...')
    if not P5_LEDGER_PATH.exists():
        print(f'FATAL: P5 ledger not found: {P5_LEDGER_PATH}')
        return 1
    p5_rows: list[dict] = []
    with P5_LEDGER_PATH.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            p5_rows.append(json.loads(line))
    p5_review_guards: set[tuple] = {
        (
            r['word'].strip().lower(),
            r['pos'].strip().lower(),
            r['cefr'].strip().upper(),
            r['def_before'],
            (r.get('old_gloss') or '').strip(),
        )
        for r in p5_rows if r.get('decision') == 'review_candidate'
    }
    print(f'  P5 ledger review_candidate guards: {len(p5_review_guards)}')

    # Load filled file.
    print('\n[2] Loading filled file...')
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
    n_qa = 0
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

        # P5 ledger membership.
        if g not in p5_review_guards:
            print(f'FATAL: ({word}, {pos}, {cefr}) not in P5 review_candidate set')
            return 1

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

        # Apply QA normalization if this key has a known override.
        qa_normalized = False
        qa_original = ''
        qk = _qa_key(word, pos, cefr)
        if qk in QA_NORMALIZATIONS:
            qa_target = QA_NORMALIZATIONS[qk]
            if gloss != qa_target:
                qa_normalized = True
                qa_original = gloss
                gloss = qa_target
                n_qa += 1

        # Validate (after QA normalization).
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
            'qa_normalized': qa_normalized,
            'qa_original': qa_original,
        })

    # Duplicate guards.
    dups = [g for g, n in seen_guards.items() if n > 1]
    if dups:
        print(f'FATAL: {len(dups)} duplicate (word, pos, cefr, def_before, old_gloss) guards')
        for g in dups[:5]:
            print(f'  {g}')
        return 1

    # Cross-check QA normalizations: any expected QA key not seen is fatal.
    seen_qa_keys: set[str] = set()
    for r in filled:
        if r.get('decision') == 'repair_gloss':
            qk = _qa_key(r['word'], r['pos'], r['cefr'])
            if qk in QA_NORMALIZATIONS:
                seen_qa_keys.add(qk)
    expected_qa = set(QA_NORMALIZATIONS.keys())
    missing_qa = expected_qa - seen_qa_keys
    if missing_qa:
        print(f'FATAL: expected QA keys not present as repair_gloss: {missing_qa}')
        return 1
    print(f'  All {len(expected_qa)} expected QA normalizations were triggered (or already canonical).')

    # Write canonical decisions file.
    print('\n[3] Writing canonical decisions...')
    DECISIONS_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in out_rows) + '\n',
        encoding='utf-8',
    )
    print(f'  Wrote {len(out_rows)} rows to {DECISIONS_PATH.name}')
    print(f'  Distribution: {n_repair} repair_gloss + {n_keep} keep_current')
    print(f'  QA normalizations applied: {n_qa}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
