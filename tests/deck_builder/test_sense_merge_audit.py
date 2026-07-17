from __future__ import annotations

import json

import pytest

from src.config import ProjectPaths
from src.deck_builder.sense_merge_audit import (
    apply_sense_merge_reviews,
    build_sense_merge_audit,
    build_sense_merge_review_bundle,
    render_sense_merge_markdown,
    scaffold_sense_merge_review,
    serialize_sense_merge_audit,
)


PATHS = ProjectPaths()


def _sense(semantic_id: str, order: int, en: str, vi: str, example: str, source_id: str):
    return {
        "semantic_sense_id": semantic_id,
        "order": order,
        "definition_en": en,
        "definition_vi": vi,
        "examples": [example],
        "source_sense_ids": [source_id],
    }


def _semantic(guid: str, word: str, senses: list[dict]):
    return {
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "verb",
        "senses": senses,
    }


def _audit(semantic: dict):
    source_senses = []
    source_coverage = []
    for sense in semantic["senses"]:
        source_id = sense["source_sense_ids"][0]
        source_senses.append({
            "source_sense_id": source_id,
            "source": "Oxford",
            "pos": "verb",
            "cefr_original": "C1",
            "cefr_resolved": "C1",
            "sensenum_local": str(sense["order"]),
            "definition": sense["definition_en"],
            "examples": sense["examples"],
            "register_tags": [],
            "domain": None,
        })
        source_coverage.append({
            "source_sense_id": source_id,
            "disposition": "mapped",
            "target_semantic_sense_ids": [sense["semantic_sense_id"]],
            "reason": "Mapped source.",
        })
    return {
        "guid": semantic["guid"],
        "source_senses": source_senses,
        "source_coverage": source_coverage,
    }


def _inputs():
    overlap = _semantic("g-overlap", "cooperate", [
        _sense("s1", 1, "work together", "hợp tác", "One.", "ox1"),
        _sense("s2", 2, "help when asked", "hợp tác, làm theo yêu cầu", "Two.", "ox2"),
    ])
    historical = _semantic("g-history", "barrier", [
        _sense("s3", 1, "physical block", "vật chắn", "Three.", "ox3"),
        _sense("s4", 2, "abstract block", "trở ngại", "Four.", "ox4"),
    ])
    deck_audit = [{
        "word": "barrier",
        "cefr": "C1",
        "fix_status": "sense_grouping_review_20260711",
        "gloss_after": "thing that blocks",
    }]
    semantic_rows = [historical, overlap]
    audit_rows = [_audit(row) for row in semantic_rows]
    return semantic_rows, audit_rows, deck_audit, []


def _build():
    return build_sense_merge_audit(
        *_inputs(),
        input_hashes={"semantic_registry": "a", "bilingual_semantic_audit": "b"},
    )


def test_builds_union_of_vi_overlap_and_historical_reexpansion_deterministically():
    summary, candidates = _build()

    assert [row["word"] for row in candidates] == ["barrier", "cooperate"]
    assert candidates[0]["triggers"] == ["historical_grouping_reexpanded"]
    assert candidates[1]["triggers"] == ["vi_prefix_overlap"]
    assert candidates[1]["vi_overlap_groups"] == [["s1", "s2"]]
    assert summary["candidate_cards"] == 2
    assert serialize_sense_merge_audit(summary, candidates) == serialize_sense_merge_audit(
        summary, candidates
    )


def test_complete_merge_review_builds_ordered_examples_and_source_remaps():
    summary, candidates = _build()
    review_summary, review_rows = scaffold_sense_merge_review(summary, candidates)
    for row in review_rows:
        candidate = next(item for item in candidates if item["candidate_id"] == row["candidate_id"])
        ids = [sense["semantic_sense_id"] for sense in candidate["senses"]]
        row.update({
            "decision": "merge_candidate",
            "confidence": "high",
            "reason": "One common learner meaning covers both examples.",
            "merge_groups": [{
                "semantic_sense_ids": ids,
                "definition_en": "one common meaning",
                "definition_vi": "một nghĩa chung",
            }],
        })

    reviewed_summary, reviewed = apply_sense_merge_reviews(
        summary, candidates, review_summary, review_rows
    )

    cooperate = next(row for row in reviewed if row["word"] == "cooperate")
    preview = cooperate["review"]["merge_previews"][0]
    assert preview["retained_semantic_sense_id"] == "s1"
    assert preview["removed_semantic_sense_ids"] == ["s2"]
    assert preview["examples"] == ["One.", "Two."]
    assert preview["source_coverage_remaps"][-1]["new_target_semantic_sense_ids"] == ["s1"]
    assert cooperate["review"]["projected_sense_count"] == 1
    assert reviewed_summary["decision_counts"] == {"merge_candidate": 2}
    assert reviewed_summary["projected_removed_senses"] == 2


def test_review_rejects_stale_or_incomplete_rows():
    summary, candidates = _build()
    review_summary, review_rows = scaffold_sense_merge_review(summary, candidates)
    review_rows[0]["candidate_fingerprint"] = "stale"

    with pytest.raises(ValueError, match="stale_candidate"):
        apply_sense_merge_reviews(summary, candidates, review_summary, review_rows)

    review_summary, review_rows = scaffold_sense_merge_review(summary, candidates)
    review_rows.pop()
    review_rows[0].update({
        "decision": "keep_separate",
        "confidence": "high",
        "reason": "The meanings remain distinct.",
    })
    with pytest.raises(ValueError, match="missing_candidates"):
        apply_sense_merge_reviews(summary, candidates, review_summary, review_rows)

    review_summary, review_rows = scaffold_sense_merge_review(summary, candidates)
    changed_summary = {**summary, "input_hashes": {"semantic_registry": "changed"}}
    with pytest.raises(ValueError, match="stale_inputs"):
        apply_sense_merge_reviews(
            changed_summary,
            candidates,
            review_summary,
            review_rows,
        )


def test_keep_separate_reword_requires_valid_rewrite():
    summary, candidates = _build()
    review_summary, review_rows = scaffold_sense_merge_review(summary, candidates)
    for row in review_rows:
        row.update({
            "decision": "keep_separate",
            "confidence": "high",
            "reason": "Distinct meanings.",
        })
    review_rows[0]["decision"] = "keep_separate_reword"

    with pytest.raises(ValueError, match="missing_vi_rewrite"):
        apply_sense_merge_reviews(summary, candidates, review_summary, review_rows)

    candidate = candidates[0]
    review_rows[0]["vi_rewrites"] = [{
        "semantic_sense_id": candidate["senses"][0]["semantic_sense_id"],
        "definition_vi": "cách diễn đạt rõ hơn",
    }]
    _, reviewed = apply_sense_merge_reviews(
        summary, candidates, review_summary, review_rows
    )
    assert reviewed[0]["review"]["vi_rewrites"][0]["definition_vi"] == "cách diễn đạt rõ hơn"


def test_build_review_bundle_remaps_sources_before_removal_and_preserves_examples():
    summary, candidates = _build()
    review_summary, review_rows = scaffold_sense_merge_review(summary, candidates)
    for row in review_rows:
        candidate = next(item for item in candidates if item["candidate_id"] == row["candidate_id"])
        ids = [sense["semantic_sense_id"] for sense in candidate["senses"]]
        row.update({
            "decision": "merge_candidate",
            "confidence": "high",
            "reason": "One learner meaning covers both source senses.",
            "merge_groups": [{
                "semantic_sense_ids": ids,
                "definition_en": "one common meaning",
                "definition_vi": "một nghĩa chung",
            }],
        })
    _, reviewed = apply_sense_merge_reviews(
        summary, candidates, review_summary, review_rows
    )

    bundle = build_sense_merge_review_bundle(
        reviewed,
        reviewer="merge-reviewer",
        reviewed_at="2026-07-17",
    )

    cooperate = next(row for row in bundle if row["guid"] == "g-overlap")
    assert cooperate["remove_senses"] == ["s2"]
    assert cooperate["source_coverage"] == [{
        "source_sense_id": "ox2",
        "disposition": "mapped",
        "target_semantic_sense_ids": ["s1"],
        "reason": "Remapped after approved semantic merge into s1.",
    }]
    assert cooperate["senses"] == [{
        "semantic_sense_id": "s1",
        "checks": {
            "english_semantics": "repair",
            "vietnamese_semantics": "repair",
            "simplicity": "pass",
            "example_pos_alignment": "pass",
        },
        "decision": "repair_proposed",
        "proposed": {
            "definition_en": "one common meaning",
            "definition_vi": "một nghĩa chung",
            "examples": ["One.", "Two."],
        },
        "confidence": "high",
        "review_reason": "Approved semantic sense merge: One learner meaning covers both source senses.",
        "reviewer": "merge-reviewer",
        "reviewed_at": "2026-07-17",
        "approval": "approved",
    }]


def test_build_review_bundle_applies_vi_rewrite_only_and_skips_non_mutations():
    summary, candidates = _build()
    review_summary, review_rows = scaffold_sense_merge_review(summary, candidates)
    for row in review_rows:
        row.update({
            "decision": "keep_separate",
            "confidence": "high",
            "reason": "Distinct learner meanings.",
        })
    candidate = candidates[0]
    semantic_id = candidate["senses"][0]["semantic_sense_id"]
    review_rows[0].update({
        "decision": "keep_separate_reword",
        "vi_rewrites": [{
            "semantic_sense_id": semantic_id,
            "definition_vi": "cách diễn đạt rõ hơn",
        }],
    })
    _, reviewed = apply_sense_merge_reviews(
        summary, candidates, review_summary, review_rows
    )

    bundle = build_sense_merge_review_bundle(
        reviewed,
        reviewer="merge-reviewer",
        reviewed_at="2026-07-17",
    )

    assert [row["guid"] for row in bundle] == [candidate["guid"]]
    update = bundle[0]["senses"][0]
    original = candidate["senses"][0]
    assert update["proposed"] == {
        "definition_en": original["definition_en"],
        "definition_vi": "cách diễn đạt rõ hơn",
        "examples": original["examples"],
    }
    assert update["checks"]["vietnamese_semantics"] == "repair"
    assert update["checks"]["english_semantics"] == "pass"


def _load(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_current_canonical_focused_queue_has_unique_review_candidates():
    semantic = _load(PATHS.semantic_registry)
    audit = _load(PATHS.bilingual_semantic_audit)
    deck_audit = _load(PATHS.deck_audit_jsonl)
    overrides = _load(PATHS.non_oxford_non_c2_overrides)

    summary, candidates = build_sense_merge_audit(
        semantic,
        audit,
        deck_audit,
        overrides,
        input_hashes={},
    )

    assert summary["candidate_cards"] == len(candidates)
    assert len({row["candidate_id"] for row in candidates}) == len(candidates)
    assert summary["candidate_cards"] > 0


def test_markdown_escapes_guid_that_starts_with_backtick():
    summary, candidates = _build()
    candidates[0]["guid"] = "`leading`tick"

    markdown = render_sense_merge_markdown(summary, candidates)

    assert "GUID: `` `leading`tick ``" in markdown
