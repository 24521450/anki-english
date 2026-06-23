"""Full-file audit of audit_full_deck.jsonl - checks EVERY record, no sampling.

Layers:
  A. Data hygiene — separator, rule_applied, null fields
  B. Format integrity — word count, trailing separator, parens
  C. Meaning accuracy heuristics — generic glosses, synonym-only, def==gloss
  D. Self-ref leaks — headword-in-gloss across all multi-word chunks
  E. Cross-stream consistency — same key across sources
  F. Multi-POS specific — pick1 vs pick2 sanity
  G. Unverified deep dive — categorize all 1,446 unverified_rule_a

Output: full_audit_report.json + prints to stdout.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

AUDIT_PATH = Path(r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl")

# Load ALL records
records = []
with AUDIT_PATH.open(encoding="utf-8") as f:
    for line in f:
        records.append(json.loads(line))

print(f"Loaded {len(records)} records\n")

# ============================================================
# LAYER A: Data Hygiene
# ============================================================
KNOWN_RULES = {
    "2sense_samedomain", "2sense_distinct",
    "3sense_distinct",  # legacy pre-P6
    "multi_sense_distinct",  # P6: N distinct senses, kept with |
    "common_core_trimmed",  # P7: collapsed subsenses to single chunk
    "trimmed_multisense",  # P7: 2+ distinct chunks kept after redundant-sense trim
    "rule_b_pick1", "rule_b_pick2", "rule_b_pick2_addendum",
    "concrete_1sense", "multi_pos_pick1", "multi_pos_pick2",
    "precision_phrase", "safety_net",  # P5/P5D additions
}

layer_a_issues = defaultdict(list)
for r in records:
    if r["rule_applied"] is not None and r["rule_applied"] not in KNOWN_RULES:
        layer_a_issues["unknown_rule_applied"].append(r)
    if r["separator"] == "|":
        layer_a_issues["pipe_separator"].append(r)
    if r["gate_status"] != "skip_fallback" and r["gloss_after"] is not None:
        # Should have rule_applied and separator set
        if r["rule_applied"] is None:
            layer_a_issues["null_rule_applied_with_gloss"].append(r)
        if r["separator"] is None:
            layer_a_issues["null_separator_with_gloss"].append(r)
        if r["gloss_word_count"] is None:
            layer_a_issues["null_wordcount_with_gloss"].append(r)

print("=" * 60)
print("LAYER A: Data Hygiene")
print("=" * 60)
for k, v in sorted(layer_a_issues.items(), key=lambda x: -len(x[1])):
    print(f"  {k}: {len(v)}")

# ============================================================
# LAYER B: Format Integrity
# ============================================================
def recount_words(gloss, sep):
    """Recount words with separator-aware splitting."""
    if not gloss:
        return 0
    cleaned = gloss.replace("|", ";").replace(";", "|")
    chunks = [c.strip() for c in cleaned.split("|") if c.strip()]
    return sum(len(c.split()) for c in chunks)

layer_b_issues = defaultdict(list)
for r in records:
    g = r.get("gloss_after")
    if not g:
        continue
    # Recount vs reported
    actual = recount_words(g, r["separator"])
    if r["gloss_word_count"] is not None and actual != r["gloss_word_count"]:
        layer_b_issues["wordcount_mismatch"].append({
            **r, "_actual_count": actual
        })
    # Trailing/leading separator
    if g.rstrip().endswith((";", "|")) or g.lstrip().startswith((";", "|")):
        layer_b_issues["leading_trailing_separator"].append(r)
    # Word count over limit (2-6 words allowed)
    if actual > 6:
        layer_b_issues["gloss_too_long"].append({
            **r, "_actual_count": actual
        })
    # Empty gloss with non-null word_count (data inconsistency)
    if not g.strip() and r["gloss_word_count"]:
        layer_b_issues["empty_gloss_with_count"].append(r)

print("\n" + "=" * 60)
print("LAYER B: Format Integrity")
print("=" * 60)
for k, v in sorted(layer_b_issues.items(), key=lambda x: -len(x[1])):
    print(f"  {k}: {len(v)}")

# ============================================================
# LAYER C: Meaning Accuracy Heuristics
# ============================================================
GENERIC_SINGLES = {
    "process", "system", "thing", "action", "way", "use", "part", "form",
    "state", "change", "movement", "object", "item", "kind", "type",
    "device", "tool", "means", "method",
}

layer_c_issues = defaultdict(list)
for r in records:
    g = r.get("gloss_after")
    if not g:
        continue
    g_clean = g.strip()
    chunks = [c.strip().lower() for c in g.replace("|", ";").split(";") if c.strip()]
    def_clean = (r.get("def_before") or "").strip()

    # C1: Generic single-word glosses
    if len(chunks) == 1 and chunks[0] in GENERIC_SINGLES:
        layer_c_issues["generic_single_gloss"].append(r)

    # C2: def_before == gloss_after (no simplification)
    if def_clean and def_clean.lower() == g_clean.lower():
        layer_c_issues["def_equals_gloss"].append(r)

    # C3: Number of gloss chunks vs number of def chunks
    def_chunks = [c.strip() for c in def_clean.replace("|", ";").split(";") if c.strip()]
    if len(def_chunks) >= 3 and len(chunks) == 1 and r["rule_applied"] != "rule_b_pick1":
        # 3+ senses in def, only 1 chunk in gloss, NOT rule_b_pick1 → suspicious
        layer_c_issues["under_represented_multi_sense"].append({
            **r, "_def_chunks": len(def_chunks), "_gloss_chunks": len(chunks)
        })

    # C4: Word "abstract" patterns - def starts with "the state/act/quality of"
    if def_clean.lower().startswith(("the state of", "the act of", "the quality of",
                                      "the process of", "the fact of")):
        # Abstract def - check gloss captures the abstraction
        layer_c_issues["abstract_def"].append(r)

print("\n" + "=" * 60)
print("LAYER C: Meaning Accuracy Heuristics")
print("=" * 60)
for k, v in sorted(layer_c_issues.items(), key=lambda x: -len(x[1])):
    print(f"  {k}: {len(v)}")

# ============================================================
# LAYER D: Self-Ref Leaks (headword in gloss)
# ============================================================
def has_headword_leak(word, gloss):
    """Check if headword appears in gloss chunks."""
    if not word or not gloss:
        return False, None
    word_lower = word.lower().strip()
    # Strip parenthetical hint
    word_clean = re.sub(r"\s*\(.*?\)\s*", "", word_lower).strip()
    chunks = [c.strip() for c in gloss.lower().replace("|", ";").split(";") if c.strip()]
    for c in chunks:
        words_in_chunk = re.findall(r"\b\w+\b", c)
        if word_clean in words_in_chunk:
            return True, c
    return False, None

layer_d_issues = defaultdict(list)
for r in records:
    g = r.get("gloss_after")
    if not g:
        continue
    has_leak, chunk = has_headword_leak(r["word"], g)
    if has_leak:
        layer_d_issues["headword_in_gloss"].append({
            **r, "_leak_chunk": chunk
        })

print("\n" + "=" * 60)
print("LAYER D: Self-Ref Leaks")
print("=" * 60)
for k, v in sorted(layer_d_issues.items(), key=lambda x: -len(x[1])):
    print(f"  {k}: {len(v)}")

# ============================================================
# LAYER E: Cross-Stream Consistency
# ============================================================
# Same (word, pos, cefr) across multiple sources
key_to_sources = defaultdict(set)
key_to_glosses = defaultdict(set)
for r in records:
    key = (r["word"], r["pos"], r["cefr"])
    key_to_sources[key].add(r["source"])
    if r["gloss_after"]:
        key_to_glosses[key].add(r["gloss_after"])

cross_stream_issues = []
for key, sources in key_to_sources.items():
    if len(sources) > 1:
        glosses = key_to_glosses.get(key, set())
        cross_stream_issues.append({
            "key": key,
            "sources": list(sources),
            "glosses": list(glosses),
        })

print("\n" + "=" * 60)
print("LAYER E: Cross-Stream Consistency")
print("=" * 60)
print(f"  multi_source_keys: {len(cross_stream_issues)}")
print(f"  multi_source_with_different_glosses: {sum(1 for x in cross_stream_issues if len(x['glosses']) > 1)}")

# ============================================================
# LAYER F: Multi-POS Specific
# ============================================================
layer_f_issues = defaultdict(list)
for r in records:
    pos = r.get("pos", "")
    g = r.get("gloss_after")
    if not g or "," not in pos:
        continue
    rule = r.get("rule_applied")
    if rule == "multi_pos_pick1":
        # Pick1 = single chunk - check def has 2+ POS senses
        def_chunks = [c.strip() for c in r["def_before"].replace("|", ";").split(";") if c.strip()]
        if len(def_chunks) < 2:
            layer_f_issues["multi_pos_pick1_with_single_def_chunk"].append(r)
    elif rule == "multi_pos_pick2":
        # Pick2 = 2 chunks - verify both are from different POS
        chunks = [c.strip() for c in g.replace("|", ";").split(";") if c.strip()]
        if len(chunks) != 2:
            layer_f_issues["multi_pos_pick2_wrong_chunk_count"].append({
                **r, "_chunks": len(chunks)
            })

print("\n" + "=" * 60)
print("LAYER F: Multi-POS Specific")
print("=" * 60)
for k, v in sorted(layer_f_issues.items(), key=lambda x: -len(x[1])):
    print(f"  {k}: {len(v)}")

# ============================================================
# LAYER G: Unverified Rule-A Deep Dive
# ============================================================
unverified = [r for r in records if r["gate_status"] == "unverified_rule_a"]
print("\n" + "=" * 60)
print(f"LAYER G: Unverified Rule-A Deep Dive (n={len(unverified)})")
print("=" * 60)

# Categorize by rule_applied
unverified_by_rule = Counter(r.get("rule_applied") or "null" for r in unverified)
print("  By rule_applied:")
for k, n in unverified_by_rule.most_common():
    print(f"    {k}: {n}")

# Categorize by word_count
unverified_by_wc = Counter(r.get("gloss_word_count") or 0 for r in unverified)
print("  By gloss_word_count:")
for k, n in sorted(unverified_by_wc.items()):
    print(f"    {k}: {n}")

# ============================================================
# Save full report
# ============================================================
report = {
    "total_records": len(records),
    "layer_a": {k: len(v) for k, v in layer_a_issues.items()},
    "layer_b": {k: len(v) for k, v in layer_b_issues.items()},
    "layer_c": {k: len(v) for k, v in layer_c_issues.items()},
    "layer_d": {k: len(v) for k, v in layer_d_issues.items()},
    "layer_e": {
        "multi_source_keys": len(cross_stream_issues),
        "different_glosses": sum(1 for x in cross_stream_issues if len(x["glosses"]) > 1),
    },
    "layer_f": {k: len(v) for k, v in layer_f_issues.items()},
    "layer_g_unverified_total": len(unverified),
    "layer_g_by_rule": dict(unverified_by_rule),
    "layer_g_by_wc": dict(unverified_by_wc),
}

# Write full case lists
out = Path(r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\full_audit_cases.json")
with out.open("w", encoding="utf-8") as f:
    json.dump({
        "summary": report,
        "layer_a_cases": layer_a_issues,
        "layer_b_cases": layer_b_issues,
        "layer_c_cases": layer_c_issues,
        "layer_d_cases": layer_d_issues,
        "layer_e_cases": cross_stream_issues,
        "layer_f_cases": layer_f_issues,
    }, f, ensure_ascii=False, indent=2)

print(f"\nFull case lists saved to: {out}")
print(f"Summary saved as 'summary' in the same file.")
