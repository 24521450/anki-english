"""Simplify sense grouping for a single record.

Pure functions. No I/O.

Pipeline per record:
  1. For each (pos, def), resolve the sense's CEFR: def.cefr OR oxford_badge OR 'UNCLASSIFIED'.
  2. Group senses by resolved CEFR (card-level grouping).
  3. Within each CEFR group, cluster senses that are mergeable:
     - First implementation: bucket by (resolved_cefr, pos). All senses in the
       same (pos, cefr) bucket form a single cluster.
  4. For each cluster of size 1: keep the original sense as-is.
  5. For each cluster of size > 1: merge into a single sense.
  6. Drop senses where cefr resolved to UNCLASSIFIED AND the same POS has
     a stronger CEFR signal elsewhere. Exception: keep all if record has no
     def.cefr signal at all (per user rule).

A merged sense retains:
  - text = " | "-joined from all source texts
  - cefr = the cluster's resolved CEFR
  - register_tags = union (first-appearance order)
  - topics = union by (name, cefr) tuple
  - collocations = union per bucket
  - examples = up to 2, prioritized by non-null-cefr source
  - countability = most common non-null
  - domain = most common non-null
"""
from __future__ import annotations
from collections import Counter
from typing import NamedTuple

from src.deck_builder.beta_score import evaluate_pair
from src.scraper.oxford_labels import CONFLICT_PAIRS  # noqa: F401 — re-exported for back-compat

# Separator for merged text fields. Use ' ; ' (semicolon, not ' | ') per user preference.
# Risk: Oxford defs may contain ';' mid-sentence, so we keep spaces around to make the
# boundary detectable by a regex like ' ; ' in downstream consumers.
TEXT_JOIN_SEPARATOR = ' ; '


class MergedSense(NamedTuple):
    pos: str
    cefr: str
    text: str
    register_tags: list[str]
    topics: list[dict]
    collocations: dict
    examples: list[dict]
    countability: str | None
    domain: str | None
    is_phrase: bool
    is_idiom: bool
    # Audit metadata
    source_pdd_idx: list[int]
    source_def_idx: list[int]
    cefr_originals: list[str | None]
    cefr_sources: list[str]
    # β heuristic metadata (only set when cluster size > 1)
    semantic_score: float | None = None  # weighted 0.5/0.3/0.2 score
    beta_decision: str | None = None  # 'merge' | 'split' | 'review' (None = size 1, no check)
    review_needed: bool = False  # True if decision is 'review' (kept as merge, but flagged)
    split_reason: str | None = None  # human-readable: which pair triggered split
    # CEFR rule label (per CONTEXT.md)
    rule_label: str | None = None  # e.g. 'Rule 1+3: surviving senses all have own CEFR (dropped 1 unlisted)'
    # Lexical relation specs — paired sense-level synonyms and antonyms
    # for each example in this merged sense. Consumed by the relation
    # annotator in src/deck_builder/synonym_annotator.py.
    # Each entry: {"text": ex_text, "synonyms": [...], "antonyms": [...]}.
    relation_specs: list[dict] | None = None
    # Sense label specs — source definition text and labels contributing to this sense.
    # Consumed by the sense label annotator in src/deck_builder/sense_labels.py.
    # Each entry: {"source_definition": str, "register_tags": list[str], "domain": str | None}.
    label_specs: list[dict] | None = None


class FlatSense(NamedTuple):
    """Internal: a sense flattened from pos_data with its origin tracked.

    cefr_source captures the resolution path (matches CONTEXT.md
    "CEFR Sense-Level Assignment Rule"):
      - 'sense_badge': def had its own CEFR (Rule 1)
      - 'inherited_single': word has 1 sense, def null, fell back to headword (Rule 2)
      - 'unlisted': word has 2+ senses, def null, but ANOTHER sense has CEFR (Rule 3)
      - 'inherited_primary': all senses null, sense[0] inherits headword (Rule 4)
      - 'unlisted': all senses null, sense[>0] no signal (Rule 4 secondary)
      - 'no_data': headword itself has no CEFR (Rule 5)
    """
    pos: str
    cefr_original: str | None
    cefr_resolved: str
    cefr_source: str
    pd_idx: int
    def_idx: int


def resolve_sense_cefr(
    def_cefr: str | None,
    headword_cefr: str | None,
    sense_idx: int = 0,
    total_senses: int = 1,
    any_other_has_badge: bool = False,
) -> tuple[str, str]:
    """Per-sense CEFR resolution per CONTEXT.md rule.

    Returns: (cefr_value, source_label) where source_label is one of:
      - 'sense_badge', 'inherited_single', 'inherited_primary',
        'unlisted', 'no_data'

    Args:
      def_cefr: this sense's def.cefr (may be null)
      headword_cefr: oxford_badge for the whole record (may be null)
      sense_idx: global flat index of this sense
      total_senses: total number of senses across all pos_data entries
      any_other_has_badge: pre-computed — does any other sense in the
        record have a non-null sense_cefr? Required for Rule 3 detection.
    """
    # Rule 1: def has its own CEFR
    if def_cefr is not None:
        return def_cefr, "sense_badge"

    # Rule 2: single-sense word, fall back to headword
    if total_senses == 1:
        if headword_cefr is not None:
            return headword_cefr, "inherited_single"
        return None, "no_data"

    # total_senses > 1
    # Rule 3: another sense has a badge — this sense is unlisted
    if any_other_has_badge:
        return None, "unlisted"

    # Rule 4: all senses null, multi-sense
    if sense_idx == 0:
        if headword_cefr is not None:
            return headword_cefr, "inherited_primary"
        return None, "no_data"

    # sense_idx > 0, all senses null
    return None, "unlisted"


# Rule 5 fallback is implicit: when headword_cefr is null AND def_cefr is null
# AND no other sense has CEFR, the function returns (None, "no_data") which
# is caught by the caller's drop_redundant_unclassified pass.


def _flatten_senses(record: dict) -> list[FlatSense]:
    """Flatten all senses across pos_data, tracking origin + cefr resolution source.

    For Rule 3 detection (any_other_has_badge), we need to know if any sense
    in the record has non-null sense_cefr. We pre-compute this once per record.
    """
    pos_data = record.get("pos_data", [])
    badge = record.get("oxford_badge")
    total_senses = sum(len(pd.get("definitions", [])) for pd in pos_data)

    # Pre-compute which flat indices have their own badge
    flat_with_badge: set[int] = set()
    flat_idx = 0
    for pd in pos_data:
        for d in pd.get("definitions", []):
            if d.get("cefr") is not None:
                flat_with_badge.add(flat_idx)
            flat_idx += 1

    flat: list[FlatSense] = []
    flat_idx = 0
    for pd_idx, pd in enumerate(pos_data):
        pos = pd.get("pos", "")
        for def_idx, d in enumerate(pd.get("definitions", [])):
            cefr_orig = d.get("cefr")
            # "any other has badge" = at least one other sense has it (not self)
            any_other = (len(flat_with_badge) > 0) and (flat_idx not in flat_with_badge or len(flat_with_badge) > 1)
            cefr_resolved, source = resolve_sense_cefr(
                cefr_orig, badge,
                sense_idx=flat_idx,
                total_senses=total_senses,
                any_other_has_badge=any_other,
            )
            flat.append(FlatSense(
                pos=pos,
                cefr_original=cefr_orig,
                cefr_resolved=cefr_resolved,
                cefr_source=source,
                pd_idx=pd_idx,
                def_idx=def_idx,
            ))
            flat_idx += 1
    return flat


def _merge_texts(texts: list[str]) -> str:
    parts = [(t or "").strip() for t in texts]
    parts = [p for p in parts if p]
    return TEXT_JOIN_SEPARATOR.join(parts)


def _merge_register_tags(sources: list[list[str]]) -> list[str]:
    """Union register_tags from multiple source definitions (first-appearance order).

    Conflicts (formal+informal etc.) are passed through intact so that
    sense_labels.py can detect them and require an explicit override.
    Silent suppression here would hide corruption in the source data.
    """
    out = []
    for src in sources:
        for t in src or []:
            if t and t not in out:
                out.append(t)
    return out


def _merge_topics(sources: list[list[dict]]) -> list[dict]:
    seen = set()
    out = []
    for src in sources:
        for t in src or []:
            if not t or not isinstance(t, dict):
                continue
            name = t.get("name")
            t_cefr = t.get("cefr") or ""
            key = (name, t_cefr)
            if name and key not in seen:
                seen.add(key)
                out.append(t)
    return out


def _merge_collocations(sources: list[dict]) -> dict:
    out: dict[str, list[str]] = {}
    seen_per_bucket: dict[str, set[str]] = {}
    for src in sources:
        if not src:
            continue
        for bucket, values in src.items():
            if not bucket:
                continue
            if bucket not in out:
                out[bucket] = []
                seen_per_bucket[bucket] = set()
            for v in values or []:
                if v and v not in seen_per_bucket[bucket]:
                    seen_per_bucket[bucket].add(v)
                    out[bucket].append(v)
    return out


def _pick_examples(sources: list[list[dict]], max_n: int = 2) -> list[dict]:
    flat = []
    for examples in sources:
        for ex in examples or []:
            if ex and isinstance(ex, dict):
                flat.append(ex)
    seen_text = set()
    deduped = []
    for ex in flat:
        text = (ex.get("text") or "").strip()
        if text and text not in seen_text:
            seen_text.add(text)
            deduped.append(ex)
    return deduped[:max_n]


def _merge_countability(sources: list[str | None]) -> str | None:
    valid = [s for s in sources if s]
    if not valid:
        return None
    return Counter(valid).most_common(1)[0][0]


def _merge_domain(sources: list[str | None]) -> str | None:
    return _merge_countability(sources)


def cluster_senses(flat: list[FlatSense]) -> list[list[int]]:
    """Bucket senses by (cefr_original, pos) — NOT cefr_resolved.

    Why: a null-cefr sense in the same pos as a set-cefr sense should NOT
    cluster with the set-cefr sense. Otherwise drop_redundant_unclassified
    can't separate them. We bucket by the ORIGINAL def.cefr (which can be
    None), and resolve to cefr_resolved only AFTER deciding what to keep.
    """
    buckets: dict[tuple, list[int]] = {}
    for i, fs in enumerate(flat):
        # Bucket by (cefr_original, pos) — None is a valid key
        key = (fs.cefr_original, fs.pos)
        buckets.setdefault(key, []).append(i)
    return list(buckets.values())


def drop_redundant_unclassified(flat: list[FlatSense], clusters: list[list[int]]) -> list[list[int]]:
    """Drop 'unlisted' and 'no_data' clusters when same pos has a stronger signal.

    The 'stronger signal' sources are: 'sense_badge', 'inherited_single', 'inherited_primary'.

    Rule:
      - If a cluster is 'unlisted' or 'no_data' (no useful CEFR), but another
        cluster in the same POS has a signal -> drop this cluster.
      - If NO cluster in the record has a signal -> keep everything (Rule 4).
    """
    SIGNAL_SOURCES = ('sense_badge', 'inherited_single', 'inherited_primary')
    has_any_signal = any(fs.cefr_source in SIGNAL_SOURCES for fs in flat)
    if not has_any_signal:
        return clusters  # no signal anywhere, keep all
    kept = []
    for cluster_indices in clusters:
        cluster_fs = [flat[i] for i in cluster_indices]
        if any(fs.cefr_source in SIGNAL_SOURCES for fs in cluster_fs):
            kept.append(cluster_indices)
            continue
        # This cluster has no signal. Check if any other cluster in same pos does.
        cluster_pos = cluster_fs[0].pos
        same_pos_has_signal = False
        for other_idx in clusters:
            if other_idx == cluster_indices:
                continue
            for idx in other_idx:
                if flat[idx].pos == cluster_pos and flat[idx].cefr_source in SIGNAL_SOURCES:
                    same_pos_has_signal = True
                    break
            if same_pos_has_signal:
                break
        if not same_pos_has_signal:
            kept.append(cluster_indices)
    return kept


def refine_clusters_by_beta(
    record: dict, flat: list[FlatSense], clusters: list[list[int]]
) -> list[tuple[list[int], dict]]:
    """Apply β heuristic to each cluster. Returns list of (cluster, beta_meta).

    For each cluster of size > 1:
      - Compute β between consecutive pairs (0-1, 1-2, 2-3, ...).
      - If any pair is 'split' (score <= 0.3): split cluster into individual
        senses (each its own cluster). mark split_reason.
      - Else: keep cluster. Compute aggregate score (mean of pair scores).
        If mean is in review band (0.3-0.7): mark review_needed=True.
      - Else (mean >= 0.7): clean merge, no flag.

    For clusters of size 1: pass through with no β metadata.
    """
    out: list[tuple[list[int], dict]] = []
    for cluster_indices in clusters:
        if len(cluster_indices) == 1:
            out.append((cluster_indices, {
                'semantic_score': None,
                'beta_decision': None,
                'review_needed': False,
                'split_reason': None,
            }))
            continue

        # Compute pair scores
        pair_scores: list[tuple[int, int, float, str]] = []  # (i, j, score, decision)
        for k in range(len(cluster_indices) - 1):
            i = cluster_indices[k]
            j = cluster_indices[k + 1]
            d_i = _resolve_def(record, flat[i].pd_idx, flat[i].def_idx)
            d_j = _resolve_def(record, flat[j].pd_idx, flat[j].def_idx)
            verdict = evaluate_pair(d_i, d_j)
            pair_scores.append((i, j, verdict.score, verdict.decision))

        # If any pair is 'split', split the cluster into individual senses
        split_pairs = [(i, j, s) for (i, j, s, d) in pair_scores if d == 'split']
        if split_pairs:
            # Split: each sense its own cluster
            for idx in cluster_indices:
                out.append(([idx], {
                    'semantic_score': None,
                    'beta_decision': 'split',
                    'review_needed': False,
                    'split_reason': f'split: β({flat[split_pairs[0][0]].def_idx},{flat[split_pairs[0][1]].def_idx})={split_pairs[0][2]:.2f}',
                }))
        else:
            # No split. Compute mean score, decide if review
            mean_score = sum(s for (_, _, s, _) in pair_scores) / len(pair_scores)
            review_needed = any(d == 'review' for (_, _, _, d) in pair_scores)
            if all(d == 'merge' for (_, _, _, d) in pair_scores):
                decision = 'merge'
            elif review_needed:
                decision = 'review'
            else:
                # Should not happen (we caught 'split' above)
                decision = 'review'
            out.append((cluster_indices, {
                'semantic_score': mean_score,
                'beta_decision': decision,
                'review_needed': review_needed,
                'split_reason': None,
            }))
    return out


def _resolve_def(record: dict, pd_idx: int, def_idx: int) -> dict:
    """Get the def dict at given (pd_idx, def_idx)."""
    return record.get("pos_data", [])[pd_idx].get("definitions", [])[def_idx]


def merge_cluster(
    record: dict,
    flat: list[FlatSense],
    cluster_indices: list[int],
    beta_meta: dict | None = None,
) -> MergedSense:
    """Merge a cluster into a single sense. Optional beta_meta carries
    β heuristic results (semantic_score, beta_decision, review_needed, split_reason)."""
    src_fs = [flat[i] for i in cluster_indices]
    pos = src_fs[0].pos
    cefr_resolved = src_fs[0].cefr_resolved

    src_defs = [_resolve_def(record, fs.pd_idx, fs.def_idx) for fs in src_fs]
    src_texts = [d.get("text", "") for d in src_defs]
    src_register = [d.get("register_tags") or [] for d in src_defs]
    src_topics = [d.get("topics") or [] for d in src_defs]
    src_collocations = [d.get("collocations") or {} for d in src_defs]
    src_examples = []
    for d in src_defs:
        syns = d.get("synonyms") or []
        exs = []
        for ex in d.get("examples") or []:
            if isinstance(ex, dict):
                ex_copy = dict(ex)
                ex_copy["synonyms"] = syns
                exs.append(ex_copy)
        src_examples.append(exs)
    src_countability = [d.get("countability") for d in src_defs]
    src_domain = [d.get("domain") for d in src_defs]
    src_phrase = [bool(d.get("is_phrase")) for d in src_defs]
    src_idiom = [bool(d.get("is_idiom")) for d in src_defs]
    cefr_originals = [d.get("cefr") for d in src_defs]

    # Collect lexical relation specs from original uncapped examples of the
    # senses in this cluster. Each example gets the paired (synonyms, antonyms)
    # of its source def. When the cluster merged multiple defs, we attach one
    # spec per (example, source def) pair so the annotator can pick the exact
    # Oxford sense that owns the example.
    relation_specs = []
    for d in src_defs:
        syns = d.get("synonyms") or []
        ants = d.get("antonyms") or []
        for ex in d.get("examples") or []:
            ex_text = (ex.get("text") or "").strip()
            if ex_text:
                relation_specs.append({
                    "text": ex_text,
                    "synonyms": syns,
                    "antonyms": ants,
                })

    # Collect sense label specs from source definitions in this cluster.
    label_specs = []
    for d in src_defs:
        def_text = (d.get("text") or "").strip()
        reg_tags = d.get("register_tags") or []
        dom = d.get("domain")
        label_specs.append({
            "source_definition": def_text,
            "register_tags": list(reg_tags),
            "domain": dom,
        })

    bm = beta_meta or {}
    return MergedSense(
        pos=pos,
        cefr=cefr_resolved,
        text=_merge_texts(src_texts),
        register_tags=_merge_register_tags(src_register),
        topics=_merge_topics(src_topics),
        collocations=_merge_collocations(src_collocations),
        examples=_pick_examples(src_examples, max_n=2),
        countability=_merge_countability(src_countability),
        domain=_merge_domain(src_domain),
        is_phrase=any(src_phrase),
        is_idiom=any(src_idiom),
        source_pdd_idx=[fs.pd_idx for fs in src_fs],
        source_def_idx=[fs.def_idx for fs in src_fs],
        cefr_originals=cefr_originals,
        cefr_sources=[fs.cefr_source for fs in src_fs],
        semantic_score=bm.get('semantic_score'),
        beta_decision=bm.get('beta_decision'),
        review_needed=bm.get('review_needed', False),
        split_reason=bm.get('split_reason'),
        relation_specs=relation_specs,
        label_specs=label_specs,
    )


def simplify_record(record: dict) -> list[MergedSense]:
    """Top-level: simplify all senses in a record. Returns list of MergedSense.

    Pipeline:
      1. Flatten senses (per-sense CEFR resolution)
      2. Cluster by (cefr_original, pos) — cheap first pass
      3. Drop redundant unlisted/no_data clusters
      4. Refine clusters with β heuristic — split low-similarity pairs,
         flag review band clusters
      5. Merge each cluster into a MergedSense
    """
    pos_data = record.get("pos_data", [])
    if not pos_data:
        return []

    flat = _flatten_senses(record)
    if not flat:
        return []

    # Capture original sources BEFORE drops (for rule_label accuracy)
    original_sources = [fs.cefr_source for fs in flat]

    raw_clusters = cluster_senses(flat)
    kept_clusters = drop_redundant_unclassified(flat, raw_clusters)
    refined = refine_clusters_by_beta(record, flat, kept_clusters)

    out: list[MergedSense] = []
    for cluster_indices, beta_meta in refined:
        merged = merge_cluster(record, flat, cluster_indices, beta_meta=beta_meta)
        out.append(merged)

    # Attach rule_label to each merged sense (based on original + surviving sources)
    enriched: list[MergedSense] = []
    for ms in out:
        enriched.append(ms._replace(rule_label=detect_rule_label(
            surviving_sources=ms.cefr_sources,
            original_sources=original_sources,
        )))
    return enriched


def detect_rule_label(
    surviving_sources: list[str],
    original_sources: list[str] | None = None,
) -> str:
    """Auto-detect which CEFR rule from CONTEXT.md applied. Pure function.

    Args:
      surviving_sources: cefr_source labels of senses that survived (post-drop).
      original_sources: cefr_source labels of senses BEFORE dropping unlisted/no_data
        (i.e. the full pre-simplify list). If None, falls back to using surviving_sources.

    Returns a human-readable label that distinguishes:
      - 'Rule 1: all senses originally have own CEFR' (originally all sense_badge, all survived)
      - 'Rule 2: single-sense word inherits headword CEFR'
      - 'Rule 3: mixed CEFR, dropped unlisted senses' (originally had mix, some dropped)
      - 'Rule 4: all senses null, primary inherited, secondary unlisted'
      - 'Rule 5: no headword CEFR (no_data)'
      - 'Rule 1+3: surviving senses all have own CEFR (dropped N unlisted)' (survived all sense_badge, but originally had unlisted)
    """
    if original_sources is None:
        original_sources = surviving_sources
    surviving_set = set(surviving_sources)
    original_set = set(original_sources)

    # Count drops: how many original senses were dropped?
    dropped_count = len(set(original_sources)) - len(set(surviving_sources))  # rough proxy
    # More accurate: count actual items dropped
    surviving_counter: dict[str, int] = {}
    for s in surviving_sources:
        surviving_counter[s] = surviving_counter.get(s, 0) + 1
    original_counter: dict[str, int] = {}
    for s in original_sources:
        original_counter[s] = original_counter.get(s, 0) + 1
    dropped_unlisted = original_counter.get('unlisted', 0) - surviving_counter.get('unlisted', 0)

    # Rule 5: no headword CEFR anywhere
    if surviving_set <= {'no_data', 'unlisted'} and original_set <= {'no_data', 'unlisted'}:
        if surviving_set == {'no_data', 'unlisted'} or surviving_set == {'no_data'} or surviving_set == set():
            # Empty original/surviving is also "no data" — but only if it's truly empty
            if not surviving_sources and not original_sources:
                return 'Unknown'
            return 'Rule 5: no headword CEFR (no_data)'

    # Rule 2: single-sense word inherits
    if surviving_set == {'inherited_single'}:
        return 'Rule 2: single-sense word inherits headword CEFR'

    # Rule 4: all senses null, primary inherited, secondary unlisted
    if surviving_set <= {'inherited_primary', 'unlisted'} and 'inherited_primary' in surviving_set:
        if original_set == {'inherited_primary', 'unlisted'} or original_set == {'inherited_primary'}:
            return 'Rule 4: all senses null, primary inherited'

    # Rule 1+3: surviving senses all sense_badge, but originally had unlisted
    if surviving_set <= {'sense_badge'} and 'unlisted' in original_set:
        if dropped_unlisted > 0:
            return f'Rule 1+3: surviving senses all have own CEFR (dropped {dropped_unlisted} unlisted)'

    # Rule 1: all senses originally sense_badge, no drops
    if surviving_set <= {'sense_badge'} and original_set <= {'sense_badge'}:
        return 'Rule 1: all senses originally have own CEFR'

    # Rule 3: mixed surviving has both sense_badge and unlisted
    if surviving_set == {'sense_badge', 'unlisted'}:
        return 'Rule 3: surviving senses mix sense_badge and unlisted (review)'
    if surviving_set == {'sense_badge'} and 'sense_badge' in original_set and len(original_set) > 1:
        # had mixed originally, all sense_badge survived
        if dropped_unlisted > 0:
            return f'Rule 3: dropped {dropped_unlisted} unlisted senses (no_data/inherited_primary kept)'
        return 'Rule 3: mixed CEFR originally, all surviving have own CEFR'

    # Rule 3 catch-all
    if 'unlisted' in original_set or 'no_data' in original_set:
        if dropped_unlisted > 0:
            return f'Rule 3: dropped unlisted senses (only no_data primary survived)'
        return f'Rule 3: mixed CEFR (original distribution: {dict(original_counter)})'

    # Default — only when nothing matches
    if not original_sources and not surviving_sources:
        return 'Unknown'
    return 'Unknown'
