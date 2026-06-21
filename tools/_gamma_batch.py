"""γ batch processor.

Picks N clusters from review_band_full.json (excluding already-verdicted ones),
outputs a per-cluster input file the M3 can reason about, plus a stats template.

Usage:
  python tools/_gamma_batch.py export --n 100 --batch 1
  → outputs data/simplify_diff/gamma_batch_1_input.json (100 clusters)

  Then M3 reasons about each cluster inline and writes verdicts to
  data/simplify_diff/gamma_batch_1_verdicts.json

  Then apply:
  python tools/_gamma_batch.py apply --verdicts data/simplify_diff/gamma_batch_1_verdicts.json

Stats are collected per batch.
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, '.')
from src.deck_builder.gamma_llm import (
    load_verdicts, ClusterInput, GAMMA_SYSTEM_PROMPT,
)


def export_batch(
    in_path: str = 'data/simplify_diff/review_band_full.json',
    out_path: str = 'data/simplify_diff/gamma_batch_input.json',
    n: int = 100,
    skip_verdicts: list[str] | None = None,
    seed: int = 42,
    include_words: list[str] | None = None,
) -> int:
    """Pick N clusters, optionally preferring certain words."""
    import random
    data = json.loads(Path(in_path).read_text(encoding='utf-8'))
    clusters = data['clusters']
    skip = set(skip_verdicts or [])

    # Filter out already-verdicted
    available = [c for c in clusters if c['cluster_hash'] not in skip]

    # If user requested specific words, prioritize those
    selected: list[dict] = []
    if include_words:
        priority_lower = [w.lower() for w in include_words]
        priority = [c for c in available if c['word'].lower() in priority_lower]
        selected.extend(priority)
        for c in priority:
            available.remove(c)

    # Fill rest with stratified random sample: sample by word to avoid over-weighting
    # any one word (one word may have many review clusters).
    random.seed(seed)
    by_word: dict[str, list[dict]] = defaultdict(list)
    for c in available:
        by_word[c['word'].lower()].append(c)

    # Round-robin: take 1 from each word until we have enough
    words = list(by_word.keys())
    random.shuffle(words)
    while len(selected) < n and any(by_word.values()):
        for w in words[:]:
            if len(selected) >= n:
                break
            if by_word[w]:
                selected.append(by_word[w].pop(0))
            else:
                words.remove(w)

    selected = selected[:n]
    out = {
        'note': (
            f'γ batch input. {len(selected)} clusters.\n\n'
            f'For each cluster, output a verdict in strict JSON:\n'
            f'  {{"cluster_hash": "<hash>", "word": "<word>", "decision": "merge|split|unsure", '
            f'"confidence": 0.0-1.0, "reasoning": "1 sentence", '
            f'"examples_substitutable_pct": 0-100, "merged_text": "..." | null}}\n\n'
            f'Save as: data/simplify_diff/gamma_batch_verdicts.json\n\n'
            f'GAMMA_SYSTEM_PROMPT:\n{GAMMA_SYSTEM_PROMPT}'
        ),
        'total_clusters': len(selected),
        'clusters': selected,
    }
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return len(selected)


def collect_stats(verdicts_path: str) -> dict:
    """Compute stats from a verdicts file."""
    data = json.loads(Path(verdicts_path).read_text(encoding='utf-8'))
    verdicts = data.get('verdicts', [])
    if not verdicts:
        return {'n': 0}

    decisions = Counter(v['decision'] for v in verdicts)
    confidences = [float(v.get('confidence', 0)) for v in verdicts]
    pct_subs = [int(v.get('examples_substitutable_pct', 0)) for v in verdicts]

    # β vs γ correlation (we have beta_score from the cluster input, but verdicts
    # file doesn't include it. Caller should pass it via input file)
    return {
        'n': len(verdicts),
        'merge_count': decisions.get('merge', 0),
        'split_count': decisions.get('split', 0),
        'unsure_count': decisions.get('unsure', 0),
        'merge_rate_pct': round(100 * decisions.get('merge', 0) / len(verdicts), 1),
        'avg_confidence': round(sum(confidences) / len(confidences), 3),
        'min_confidence': min(confidences),
        'max_confidence': max(confidences),
        'avg_examples_substitutable_pct': round(sum(pct_subs) / len(pct_subs), 1),
        'confidence_distribution': {
            'low (0.0-0.5)': sum(1 for c in confidences if c < 0.5),
            'med (0.5-0.8)': sum(1 for c in confidences if 0.5 <= c < 0.8),
            'high (0.8-1.0)': sum(1 for c in confidences if c >= 0.8),
        },
    }


def correlate_beta_vs_gamma(verdicts_path: str, input_path: str) -> dict:
    """Cross-reference verdicts with input clusters to compute β-vs-γ correlation."""
    verdicts = json.loads(Path(verdicts_path).read_text(encoding='utf-8'))['verdicts']
    inputs = json.loads(Path(input_path).read_text(encoding='utf-8'))['clusters']
    by_hash = {c['cluster_hash']: c for c in inputs}

    # Bucket verdicts by β score range
    buckets: dict[tuple, list[str]] = defaultdict(list)
    for v in verdicts:
        h = v['cluster_hash']
        if h not in by_hash:
            continue
        beta = by_hash[h].get('current_score', 0.0)
        if beta < 0.4:
            bucket = (0.30, 0.40)
        elif beta < 0.5:
            bucket = (0.40, 0.50)
        elif beta < 0.6:
            bucket = (0.50, 0.60)
        else:
            bucket = (0.60, 0.70)
        buckets[bucket].append(v['decision'])

    rows = []
    for bucket in sorted(buckets.keys()):
        decs = Counter(buckets[bucket])
        total = sum(decs.values())
        merge_rate = round(100 * decs.get('merge', 0) / total, 1)
        rows.append({
            'beta_range': f'[{bucket[0]:.2f}, {bucket[1]:.2f})',
            'n': total,
            'merge_count': decs.get('merge', 0),
            'split_count': decs.get('split', 0),
            'unsure_count': decs.get('unsure', 0),
            'merge_rate_pct': merge_rate,
        })
    return {'beta_vs_gamma': rows}


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd')

    p_exp = sub.add_parser('export')
    p_exp.add_argument('--in', dest='in_path', default='data/simplify_diff/review_band_full.json')
    p_exp.add_argument('--out', default='data/simplify_diff/gamma_batch_input.json')
    p_exp.add_argument('--n', type=int, default=100)
    p_exp.add_argument('--skip-verdicts', nargs='*', default=None,
                       help='cluster_hash values to skip (already verdicted)')
    p_exp.add_argument('--include-words', nargs='*', default=None,
                       help='specific words to prioritize (e.g. set hold run make get take turn)')
    p_exp.add_argument('--seed', type=int, default=42)

    p_stats = sub.add_parser('stats')
    p_stats.add_argument('verdicts_path')

    p_corr = sub.add_parser('correlate')
    p_corr.add_argument('verdicts_path')
    p_corr.add_argument('input_path')

    args = p.parse_args()
    if args.cmd == 'export':
        n = export_batch(
            in_path=args.in_path,
            out_path=args.out,
            n=args.n,
            skip_verdicts=args.skip_verdicts,
            include_words=args.include_words,
            seed=args.seed,
        )
        print(f'Exported {n} clusters to {args.out}', file=sys.stderr)
    elif args.cmd == 'stats':
        print(json.dumps(collect_stats(args.verdicts_path), indent=2))
    elif args.cmd == 'correlate':
        print(json.dumps(correlate_beta_vs_gamma(args.verdicts_path, args.input_path), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
