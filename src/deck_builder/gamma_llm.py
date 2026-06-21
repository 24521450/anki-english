"""γ (gamma) — LLM-as-judge for review-band sense clusters.

DESIGN NOTE (2026-06-16):
We do NOT call an external LLM via HTTP. The agent itself is MiniMax-M3, and
the orchestrator (this session) acts as the γ LLM. This file defines:

  1. The schema for cluster input (what γ sees)
  2. The schema for γ verdict (what γ outputs)
  3. The prompt template γ uses (to be embedded in the orchestrator's reasoning)
  4. Pure helpers for export/import of JSON review-band files

The orchestrator reads `data/simplify_diff/review_band.json`, reasons about each
cluster, and writes verdicts to `data/simplify_diff/gamma_verdicts.json`.
Then `tools/_apply_gamma_verdicts.py` applies the verdicts to produce the
final simplified output.

Why no HTTP client? See user decision 2026-06-16:
  "không cần model bên ngoài, bạn là minimax M3"
"""
from __future__ import annotations
import json
import hashlib
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClusterInput:
    """One cluster needing γ review."""
    word: str
    pos: str
    headword_cefr: str | None
    senses: list[dict]   # each: {def_idx, text, cefr, examples: [str]}

    def content_hash(self) -> str:
        """Stable hash of (word, pos, sorted_def_texts) for caching."""
        key = self.word.lower() + '|' + self.pos
        key += '|' + '|'.join(sorted(s['text'] for s in self.senses))
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class GammaVerdict:
    """γ's verdict on one cluster."""
    decision: Literal['merge', 'split', 'unsure']
    confidence: float  # 0.0 - 1.0
    reasoning: str     # 1-sentence justification
    examples_substitutable_pct: int  # 0-100, the user's 80-90% rule
    # If decision == 'merge', the merged text (1-line). Else None.
    merged_text: str | None = None


# ---------------------------------------------------------------------------
# Prompt template (for M3 to follow when acting as γ)
# ---------------------------------------------------------------------------

GAMMA_SYSTEM_PROMPT = """You are an English vocabulary teacher reviewing 2-3 senses of a single word for an IELTS learner's flashcard.

YOUR RULE (the user's "80-90% rule"):
Merge the senses ONLY IF a single definition lets the learner understand AT LEAST 80-90% of all examples across the senses. Otherwise SPLIT.

OUTPUT FORMAT (strict JSON, no prose):
{
  "decision": "merge" | "split" | "unsure",
  "confidence": 0.0-1.0,
  "reasoning": "1 sentence",
  "examples_substitutable_pct": 0-100,
  "merged_text": "single definition" | null
}

DECISION RULES:
- merge:    1 def covers >=80% examples, learner doesn't need separate cards
- split:    senses are too distinct, need 2+ cards
- unsure:   borderline 70-80%, default to SPLIT in production (conservative)

NEVER merge senses that are clearly different POS, register, or context (e.g. "go" verb vs "go" noun)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def export_review_band(
    in_jsonl: str,
    out_json: str,
    max_records: int | None = None,
) -> int:
    """Read oxford_merged.jsonl, run simplify_record, collect review-band clusters
    into a JSON file for γ review. Returns count of clusters exported.
    """
    from src.deck_builder.simplify_senses import simplify_record, _resolve_def

    clusters: list[dict] = []
    n_records = 0
    for line in open(in_jsonl, encoding='utf-8'):
        r = json.loads(line)
        n_records += 1
        if max_records and n_records > max_records:
            break
        word = r.get('word', '???')
        headword_cefr = r.get('oxford_badge') or r.get('cefr') or None

        result = simplify_record(r)
        for ms in result:
            if ms.beta_decision != 'review':
                continue
            # Gather the source senses for this cluster
            senses_data = []
            for pd_idx, def_idx in zip(ms.source_pdd_idx, ms.source_def_idx):
                d = _resolve_def(r, pd_idx, def_idx)
                senses_data.append({
                    'pd_idx': pd_idx,
                    'def_idx': def_idx,
                    'text': (d.get('text') or '').strip(),
                    'cefr': d.get('cefr'),
                    'examples': [
                        ex.get('text', '').strip()
                        for ex in (d.get('examples') or [])[:5]
                    ],
                })
            if not senses_data:
                continue
            ci = ClusterInput(
                word=word, pos=ms.pos, headword_cefr=headword_cefr, senses=senses_data,
            )
            clusters.append({
                'cluster_hash': ci.content_hash(),
                'word': ci.word,
                'pos': ci.pos,
                'headword_cefr': ci.headword_cefr,
                'senses': ci.senses,
                'current_score': ms.semantic_score,
                'current_split_reason': ms.split_reason,
            })

    out_path = Path(out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_clusters': len(clusters),
            'note': 'Each cluster needs a γ verdict. See GAMMA_SYSTEM_PROMPT in src/deck_builder/gamma_llm.py for the rules.',
            'clusters': clusters,
        }, f, ensure_ascii=False, indent=2)
    return len(clusters)


def load_verdicts(path: str) -> dict[str, GammaVerdict]:
    """Load verdicts from a JSON file keyed by cluster_hash."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    out: dict[str, GammaVerdict] = {}
    for entry in data.get('verdicts', []):
        h = entry['cluster_hash']
        out[h] = GammaVerdict(
            decision=entry['decision'],
            confidence=float(entry.get('confidence', 0.5)),
            reasoning=entry.get('reasoning', ''),
            examples_substitutable_pct=int(entry.get('examples_substitutable_pct', 0)),
            merged_text=entry.get('merged_text'),
        )
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main_export() -> int:
    """CLI: export review-band clusters to JSON."""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--in-jsonl', default='data/oxford_merged.jsonl')
    p.add_argument('--out', default='data/simplify_diff/review_band.json')
    p.add_argument('--max-records', type=int, default=None,
                   help='Limit records to read (for pilot).')
    args = p.parse_args()
    n = export_review_band(args.in_jsonl, args.out, args.max_records)
    print(f'Exported {n} review-band clusters to {args.out}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main_export())
