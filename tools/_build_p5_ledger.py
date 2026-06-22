"""Build the P5 Precision Phrase Ledger.

Reads the current audit and emits `data/gloss_precision_phrase_p5.jsonl`
with:
  - 2 confirmed `repair_gloss` rows (mediate, solo)
  - N `review_candidate` rows from the heuristic scan of single-word
    single-chunk glosses at advanced CEFR (B2/C1/C2/UNCLASSIFIED)

Decision values:
  - repair_gloss      — confirmed semantic loss with phrase replacement
  - review_candidate  — heuristic flag for future human review (no change)
  - keep_current      — explicitly confirmed adequate (no change)

Run: `python -m tools._build_p5_ledger`
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'

P5_VERSION = '2026-06-21'


# Confirmed seed repairs. These come from manual review of the audit
# against Oxford source pages — not a heuristic guess.
SEED_REPAIRS = [
    {
        'word': 'mediate',
        'pos': 'verb',
        'cefr': 'C2',
        'candidate_gloss': 'help resolve a dispute',
        'rule_after': 'precision_phrase',
        'reason': (
            'mediator helps parties reach agreement; arbitrator decides '
            'the dispute. Using `arbitrate` as the gloss for `mediate` '
            'is a contrast-pair error — the words describe different '
            'roles in conflict resolution.'
        ),
        'risk_type': 'contrast_pair',
    },
    {
        'word': 'solo',
        'pos': 'noun',
        'cefr': 'C1',
        'candidate_gloss': 'single-performer music',
        'rule_after': 'precision_phrase',
        'reason': (
            '`recital` narrows to a performance event. Oxford sense '
            'covers composition, passage, OR performance by one person — '
            'a composition or passage is not a recital.'
        ),
        'risk_type': 'type_narrowing',
    },
]


# Advanced CEFR levels where precision-phrase is worth flagging.
ADVANCED_CEFR = {'B2', 'C1', 'C2', 'UNCLASSIFIED'}


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


def _build_seed_repair_rows(audit_rows: list[dict]) -> list[dict]:
    """Convert SEED_REPAIRS into ledger rows by pulling def_before + rule
    from the current audit row. Aborts if a seed isn't found in audit."""
    by_key: dict[tuple, dict] = {}
    for r in audit_rows:
        g = (
            r.get('word', '').strip().lower(),
            r.get('pos', '').strip().lower(),
            r.get('cefr', '').strip().upper(),
        )
        by_key[g] = r

    out: list[dict] = []
    for seed in SEED_REPAIRS:
        key = (
            seed['word'].lower(),
            seed['pos'].lower(),
            seed['cefr'].upper(),
        )
        audit_row = by_key.get(key)
        if audit_row is None:
            print(f'FATAL: seed repair {key} not found in audit')
            sys.exit(1)
        gloss = seed['candidate_gloss']
        sep, wc = _compute_separator_count(gloss)
        if wc < 1 or wc > 6:
            print(f'FATAL: seed gloss {gloss!r} for {key} has {wc} words (must be 1-6)')
            sys.exit(1)
        out.append({
            'word': seed['word'],
            'pos': seed['pos'],
            'cefr': seed['cefr'],
            'rule_applied': audit_row.get('rule_applied', ''),
            'def_before': audit_row.get('def_before', ''),
            'old_gloss': audit_row.get('gloss_after', ''),
            'candidate_gloss': gloss,
            'decision': 'repair_gloss',
            'new_gloss': gloss,
            'rule_after': seed['rule_after'],
            'separator': sep,
            'gloss_word_count': wc,
            'reason': seed['reason'],
            'risk_type': seed['risk_type'],
            'p5_version': P5_VERSION,
        })
    return out


def _build_review_candidate_rows(audit_rows: list[dict], seed_keys: set[tuple]) -> list[dict]:
    """Generate `review_candidate` rows for every heuristic-discovery
    single-word single-chunk gloss at advanced CEFR, EXCEPT seed keys
    and rows already triaged as P4C `repair_gloss` (those have already
    been fixed in P4C and are not in scope here)."""
    from src.deck_builder.gloss_llm import validate_verdict

    out: list[dict] = []
    for r in audit_rows:
        gloss = (r.get('gloss_after') or '').strip()
        if not gloss or '|' in gloss or ';' in gloss:
            continue
        if len(gloss.split()) != 1:
            continue
        cefr = (r.get('cefr') or '').strip().upper()
        if cefr not in ADVANCED_CEFR:
            continue
        rule = (r.get('rule_applied') or '').strip()
        # Skip POS_DEF_MISMATCH_fixed (often legitimate narrowing)
        if rule == 'POS_DEF_MISMATCH_fixed':
            continue
        key = (
            r.get('word', '').strip().lower(),
            r.get('pos', '').strip().lower(),
            cefr,
        )
        if key in seed_keys:
            continue
        # Risk type hint (heuristic): multi-POS + 1-word → multi_pos_loss;
        # long def_before + 1-word → domain_loss; otherwise generic.
        if ',' in (r.get('pos') or ''):
            risk_type = 'multi_pos_loss'
        elif len(r.get('def_before') or '') > 200:
            risk_type = 'domain_loss'
        else:
            risk_type = 'overgeneralized_synonym'
        wc = len(gloss.split())
        out.append({
            'word': r.get('word', ''),
            'pos': r.get('pos', ''),
            'cefr': cefr,
            'rule_applied': rule,
            'def_before': r.get('def_before', ''),
            'old_gloss': gloss,
            'candidate_gloss': '',
            'decision': 'review_candidate',
            'new_gloss': None,
            'rule_after': None,
            'separator': 'none',
            'gloss_word_count': wc,
            'reason': f'heuristic: {risk_type} candidate at {cefr}',
            'risk_type': risk_type,
            'p5_version': P5_VERSION,
        })
    return out


def main() -> int:
    audit_rows = [
        json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines()
        if l.strip()
    ]
    print(f'Loaded {len(audit_rows)} audit rows.')

    seed_rows = _build_seed_repair_rows(audit_rows)
    print(f'Seed repairs: {len(seed_rows)}')
    for r in seed_rows:
        print(f"  {r['word']}|{r['pos']}|{r['cefr']}: {r['old_gloss']!r} → {r['new_gloss']!r} ({r['risk_type']})")

    seed_keys = {(r['word'].lower(), r['pos'].lower(), r['cefr'].upper()) for r in seed_rows}
    review_rows = _build_review_candidate_rows(audit_rows, seed_keys)
    print(f'Review candidates: {len(review_rows)} (heuristic discoveries)')

    ledger = seed_rows + review_rows
    LEDGER_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in ledger) + '\n',
        encoding='utf-8',
    )
    print(f'Wrote {len(ledger)} rows to {LEDGER_PATH}')
    print(f'  repair_gloss:      {sum(1 for r in ledger if r["decision"] == "repair_gloss")}')
    print(f'  review_candidate:  {sum(1 for r in ledger if r["decision"] == "review_candidate")}')
    print(f'  keep_current:      {sum(1 for r in ledger if r["decision"] == "keep_current")}')
    return 0


if __name__ == '__main__':
    sys.exit(main())