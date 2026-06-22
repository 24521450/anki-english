"""Extract 988 P5 review_candidate rows for manual gloss fill.

Reads `data/gloss_precision_phrase_p5.jsonl`, filters to rows where
`decision == "review_candidate"`, and writes them to
`data/manual_gloss_review_p5_candidates.jsonl` with empty fields for
manual filling.

Output schema (one JSON object per line):
{
  "word": "...",                    # original from P5 ledger
  "pos": "...",                     # original
  "cefr": "...",                    # original
  "rule_applied": "...",            # original (pre-P5)
  "risk_type": "...",               # original (heuristic hint)
  "def_before": "...",              # original
  "old_gloss": "...",               # original
  "decision": "pending",            # user fills: repair_gloss | keep_current
  "manual_gloss_after": "",         # user fills: new gloss
  "manual_rule_after": "",          # user fills: precision_phrase | (other)
  "notes": ""                       # user fills: short reason
}

Guardrails:
- Only review_candidate rows are emitted.
- The 2 P5 seed repair rows (mediate, solo) are NOT included.
- Original audit / TXT / JSONL files are NOT touched.

Run: `python -m tools._extract_p5_review_candidates`
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

P5_LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_precision_phrase_p5.jsonl'
OUTPUT_PATH = PROJECT_ROOT / 'data' / 'manual_gloss_review_p5_candidates.jsonl'


def main() -> int:
    if not P5_LEDGER_PATH.exists():
        print(f'FATAL: P5 ledger not found: {P5_LEDGER_PATH}')
        return 1

    p5_rows: list[dict] = []
    with P5_LEDGER_PATH.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            p5_rows.append(json.loads(line))
    print(f'Loaded {len(p5_rows)} rows from {P5_LEDGER_PATH.name}')

    # Filter to review_candidate rows
    review_rows = [r for r in p5_rows if r.get('decision') == 'review_candidate']
    n_repair = sum(1 for r in p5_rows if r.get('decision') == 'repair_gloss')
    n_keep = sum(1 for r in p5_rows if r.get('decision') == 'keep_current')
    print(f'  P5 ledger breakdown: {n_repair} repair_gloss + {len(review_rows)} review_candidate + {n_keep} keep_current')

    if len(review_rows) != 988:
        print(f'FATAL: expected 988 review_candidate rows, got {len(review_rows)}')
        return 1

    # Check uniqueness by (word, pos, cefr, old_gloss)
    seen: dict[tuple, int] = {}
    for r in review_rows:
        g = (
            (r.get('word') or '').strip().lower(),
            (r.get('pos') or '').strip().lower(),
            (r.get('cefr') or '').strip().upper(),
            (r.get('old_gloss') or '').strip(),
        )
        seen[g] = seen.get(g, 0) + 1
    dups = [g for g, n in seen.items() if n > 1]
    if dups:
        print(f'FATAL: {len(dups)} duplicate (word, pos, cefr, old_gloss) keys:')
        for g in dups[:5]:
            print(f'  {g}')
        return 1

    # Map to output schema
    out_rows: list[dict] = []
    for r in review_rows:
        out_rows.append({
            'word': r.get('word', ''),
            'pos': r.get('pos', ''),
            'cefr': r.get('cefr', ''),
            'rule_applied': r.get('rule_applied', ''),
            'risk_type': r.get('risk_type', ''),
            'def_before': r.get('def_before', ''),
            'old_gloss': r.get('old_gloss', ''),
            'decision': 'pending',
            'manual_gloss_after': '',
            'manual_rule_after': '',
            'notes': '',
        })

    # Write output
    OUTPUT_PATH.write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in out_rows) + '\n',
        encoding='utf-8',
    )
    print(f'Wrote {len(out_rows)} rows to {OUTPUT_PATH}')

    # Distribution by risk_type
    by_risk = Counter(r['risk_type'] for r in out_rows)
    print('  by risk_type:')
    for risk, n in by_risk.most_common():
        print(f'    {risk}: {n}')

    # Distribution by rule_applied
    by_rule = Counter(r['rule_applied'] or '(empty)' for r in out_rows)
    print('  by rule_applied:')
    for rule, n in by_rule.most_common():
        print(f'    {rule}: {n}')

    # Distribution by cefr
    by_cefr = Counter(r['cefr'] for r in out_rows)
    print('  by cefr:')
    for cefr, n in by_cefr.most_common():
        print(f'    {cefr}: {n}')

    return 0


if __name__ == '__main__':
    sys.exit(main())