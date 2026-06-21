"""β heuristic: semantic_score for sense merging.

Rule: merge 2 senses only if a single definition can explain ≥80-90% of their
examples (user's "semantic substitutability" criterion).

Score formula (weighted):
  semantic_score =
    0.5 * collocation_overlap  (Jaccard on flattened collocation values)
    + 0.3 * example_overlap      (Jaccard on example text)
    + 0.2 * definition_similarity (Jaccard on token sets, no stopwords)

Thresholds:
  score >= 0.7 → merge (high confidence)
  0.3 < score < 0.7 → review_needed (merge but flag for audit)
  score <= 0.3 → split (don't merge, treat senses as distinct)

Design note (user feedback 2026-06-15):
  - CEFR is NOT a merge signal. Same CEFR does not imply same concept.
  - Semantic similarity dominates CEFR similarity.
  - Some senses have empty collocations/examples (e.g. set up) — score
    components degrade gracefully (Jaccard of empty set = 0; or
    Jaccard of set A and empty = 0).
"""
from __future__ import annotations
from typing import NamedTuple

# English stopwords (small set; full NLTK list would be ~180 — overkill for this)
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "to", "of", "in", "on", "at",
    "by", "for", "with", "as", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "that", "this",
    "these", "those", "i", "you", "he", "she", "it", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "its", "our", "their",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "not", "no", "yes",
})


def _tokenize(text: str) -> set[str]:
    """Lowercase + split on non-alpha + remove stopwords + drop short tokens."""
    if not text:
        return set()
    raw = text.lower()
    # Split on non-alpha
    tokens: list[str] = []
    current = []
    for ch in raw:
        if ch.isalpha():
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity. Returns 0 if both sets are empty (avoids div by 0)."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _flatten_collocations(collocations: dict) -> set[str]:
    """Flatten collocations dict to set of values (all buckets merged).

    Skip the bucket keys themselves — only the values.
    """
    if not collocations:
        return set()
    out: set[str] = set()
    for bucket, values in collocations.items():
        for v in values or []:
            if v:
                out.add(v)
    return out


def collocation_overlap(c1: dict, c2: dict) -> float:
    """Jaccard on flattened collocation values."""
    return _jaccard(_flatten_collocations(c1), _flatten_collocations(c2))


def example_overlap(e1: list[dict], e2: list[dict]) -> float:
    """Jaccard on example text (lowercased, tokenized)."""
    def _ex_text(examples):
        out = set()
        for ex in examples or []:
            t = (ex.get("text") or "").lower().strip()
            if t:
                out.add(t)
        return out
    return _jaccard(_ex_text(e1), _ex_text(e2))


def definition_similarity(d1: str, d2: str) -> float:
    """Jaccard on token sets of two definitions."""
    return _jaccard(_tokenize(d1 or ""), _tokenize(d2 or ""))


def semantic_score(sense_a: dict, sense_b: dict) -> float:
    """Compute weighted semantic score between two sense dicts.

    sense_a and sense_b are def dicts with fields:
      - text: str
      - examples: list[dict] with .text
      - collocations: dict[str, list[str]]
    """
    coll = collocation_overlap(
        sense_a.get("collocations") or {},
        sense_b.get("collocations") or {},
    )
    ex = example_overlap(
        sense_a.get("examples") or [],
        sense_b.get("examples") or [],
    )
    defn = definition_similarity(
        sense_a.get("text") or "",
        sense_b.get("text") or "",
    )
    return 0.5 * coll + 0.3 * ex + 0.2 * defn


class ScoreVerdict(NamedTuple):
    score: float
    collocation: float
    example: float
    definition: float
    decision: str  # 'merge' | 'split' | 'review'
    threshold_merge: float = 0.7
    threshold_split: float = 0.3


def evaluate_pair(sense_a: dict, sense_b: dict) -> ScoreVerdict:
    """Return score + per-component breakdown + decision."""
    coll = collocation_overlap(
        sense_a.get("collocations") or {},
        sense_b.get("collocations") or {},
    )
    ex = example_overlap(
        sense_a.get("examples") or [],
        sense_b.get("examples") or [],
    )
    defn = definition_similarity(
        sense_a.get("text") or "",
        sense_b.get("text") or "",
    )
    score = 0.5 * coll + 0.3 * ex + 0.2 * defn
    if score >= 0.7:
        decision = "merge"
    elif score <= 0.3:
        decision = "split"
    else:
        decision = "review"
    return ScoreVerdict(
        score=score, collocation=coll, example=ex, definition=defn,
        decision=decision,
    )
