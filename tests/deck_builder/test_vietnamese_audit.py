from __future__ import annotations

import copy

import pytest

from src.deck_builder.vietnamese_audit import (
    apply_vietnamese_review,
    build_vietnamese_audit,
    render_vietnamese_audit_markdown,
    scaffold_vietnamese_review,
    serialize_vietnamese_audit,
    serialize_vietnamese_review,
    validate_vietnamese_review,
    validate_vietnamese_review_for_promotion,
)


def _sense(
    guid: str,
    semantic_id: str,
    definition_en: str,
    current_vi: str,
    promoted_vi: str,
    *,
    order: int = 1,
    decision: str = "pass",
) -> tuple[dict, dict]:
    source_id = f"ox_{guid}"
    examples = [f"Example for {guid}."]
    proposed = {"definition_en": "", "definition_vi": "", "examples": []}
    checks = {
        "english_semantics": "pass",
        "vietnamese_semantics": "pass",
        "simplicity": "pass",
        "example_pos_alignment": "pass",
    }
    approval = ""
    if decision == "repair_proposed":
        proposed = {
            "definition_en": definition_en,
            "definition_vi": promoted_vi,
            "examples": list(examples),
        }
        checks["vietnamese_semantics"] = "repair"
        checks["simplicity"] = "repair"
        approval = "approved"
    audit_sense = {
        "semantic_sense_id": semantic_id,
        "order": order,
        "source_sense_ids": [source_id],
        "current": {
            "definition_en": definition_en,
            "definition_vi": current_vi,
            "examples": list(examples),
        },
        "checks": checks,
        "decision": decision,
        "proposed": proposed,
        "cambridge": {
            "url": f"https://dictionary.cambridge.org/dictionary/english-vietnamese/{guid}",
            "match": "exact",
            "summary": f"Cambridge evidence for {guid}",
            "translation_provenance": "cambridge_reference",
            "accessed_at": "2026-07-16",
        },
        "confidence": "high",
        "review_reason": "Reviewed bilingual sense.",
        "reviewer": "fixture-reviewer",
        "reviewed_at": "2026-07-15",
        "approval": approval,
    }
    registry_sense = {
        "semantic_sense_id": semantic_id,
        "order": order,
        "definition_en": definition_en,
        "definition_vi": promoted_vi,
        "examples": list(examples),
        "source_sense_ids": [source_id],
        "cambridge_match": "exact",
        "translation_provenance": "cambridge_reference",
    }
    return audit_sense, registry_sense


def _card(
    word: str,
    semantic_id: str,
    definition_en: str,
    current_vi: str,
    promoted_vi: str,
    *,
    decision: str = "pass",
) -> tuple[dict, dict, dict]:
    guid = f"guid-{word}"
    source_fingerprint = (word[0] * 64)[:64]
    audit_sense, registry_sense = _sense(
        guid,
        semantic_id,
        definition_en,
        current_vi,
        promoted_vi,
        decision=decision,
    )
    source_id = audit_sense["source_sense_ids"][0]
    identity = {
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "verb" if word == "venture" else "noun",
    }
    audit_card = {
        "schema_version": 1,
        **identity,
        "current": {
            "definition": f"{definition_en} ({current_vi})",
            "example": audit_sense["current"]["examples"][0],
            "idioms": "untouched idiom :: untouched explanation",
        },
        "source_fingerprint": source_fingerprint,
        "source_senses": [
            {
                "source_sense_id": source_id,
                "definition": definition_en,
            }
        ],
        "coverage": {
            "status": "repair_proposed" if decision == "repair_proposed" else "pass",
            "reason": "",
            "candidate_source_sense_ids": [source_id],
            "expected_same_cefr_source_sense_ids": [source_id],
        },
        "source_coverage": [
            {
                "source_sense_id": source_id,
                "disposition": "mapped",
                "target_semantic_sense_ids": [semantic_id],
                "reason": "Matches the promoted semantic sense.",
            }
        ],
        "semantic_senses": [audit_sense],
    }
    registry_card = {
        "schema_version": 1,
        **identity,
        "audit_sha256": "a" * 64,
        "source_fingerprint": source_fingerprint,
        "senses": [registry_sense],
    }
    card_registry = {**identity, "status": "active", "deck_override": ""}
    return registry_card, audit_card, card_registry


def _inputs() -> tuple[list[dict], list[dict], list[dict]]:
    contender = _card(
        "contender",
        "sem-contender",
        "person or team with a chance of winning a competition",
        "ứng viên có khả năng thắng/đối thủ nặng ký",
        "người hoặc đội có cơ hội thắng trong một cuộc thi",
        decision="repair_proposed",
    )
    venture = _card(
        "venture",
        "sem-venture",
        "risk going somewhere, doing something, or saying something",
        "mạo hiểm đi đâu, làm hoặc nói điều gì",
        "mạo hiểm đi đâu, làm hoặc nói điều gì",
    )
    explanatory = _card(
        "witness",
        "sem-witness",
        "person who sees an event happen",
        "người nhìn thấy một sự việc xảy ra",
        "người nhìn thấy một sự việc xảy ra",
    )
    promoted_short = _card(
        "compact",
        "sem-compact",
        "small and easy to carry",
        "một vật có kích thước nhỏ và dễ mang theo",
        "nhỏ gọn, dễ mang theo",
        decision="repair_proposed",
    )
    triples = [contender, venture, explanatory, promoted_short]
    return (
        [triple[0] for triple in triples],
        [triple[1] for triple in triples],
        [triple[2] for triple in triples],
    )


def _complete_review(
    summary: dict,
    candidates: list[dict],
) -> tuple[dict, list[dict]]:
    review_summary, review_rows = scaffold_vietnamese_review(summary, candidates)
    decisions = {
        "contender": ("rewrite", "đối thủ nặng ký"),
        "venture": ("rewrite", "mạo hiểm, cả gan"),
        "witness": ("keep_explanatory", ""),
    }
    for row in review_rows:
        row["decision"], row["proposed_vi"] = decisions[row["word"]]
        row["reason"] = "Natural, concise Vietnamese reviewed against the sense."
        if row["decision"] == "keep_explanatory":
            row["shorter_vi_considered"] = "nhân chứng"
            row["preserved_distinction"] = (
                "The current gloss explicitly limits this sense to directly seeing "
                "the event happen."
            )
        row["reviewer"] = "chatgpt-reviewer"
        row["reviewed_at"] = "2026-07-16"
        row["approval"] = "approved"
    return review_summary, review_rows


def test_report_selects_all_promoted_senses_at_threshold() -> None:
    registry_rows, audit_rows, card_rows = _inputs()

    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )

    assert summary["min_tokens"] == 8
    assert summary["senses_scanned"] == 4
    assert [row["word"] for row in candidates] == [
        "contender",
        "venture",
        "witness",
    ]
    assert all(row["vi_token_count"] >= 8 for row in candidates)
    assert next(row for row in candidates if row["word"] == "witness")[
        "vi_token_count"
    ] == 8
    contender = candidates[0]
    assert contender["definition_vi"] == (
        "người hoặc đội có cơ hội thắng trong một cuộc thi"
    )
    assert contender["audit_current_vi"] == (
        "ứng viên có khả năng thắng/đối thủ nặng ký"
    )
    assert contender["audit_proposed_vi"] == contender["definition_vi"]
    assert "expanded_from_audit_current" in contender["heuristic_flags"]
    assert contender["cambridge_summary"] == "Cambridge evidence for guid-contender"
    assert contender["translation_provenance"] == "cambridge_reference"

    # Candidate selection follows the promoted payload, not a longer stale
    # ``current`` value retained as pre-proposal evidence in the audit ledger.
    assert "compact" not in {row["word"] for row in candidates}


def test_all_scope_selects_every_promoted_sense() -> None:
    registry_rows, audit_rows, card_rows = _inputs()

    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )

    assert summary["scope"] == "all"
    assert summary["senses_scanned"] == 4
    assert summary["candidate_senses"] == 4
    assert {row["word"] for row in candidates} == {
        "compact",
        "contender",
        "venture",
        "witness",
    }
    assert all(len(row["context_fingerprint"]) == 64 for row in candidates)


def test_all_scope_accepts_approved_naturalness_verdicts() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    for review in reviews:
        candidate = candidates_by_id[review["candidate_id"]]
        review.update(
            {
                "decision": (
                    "keep_explanatory"
                    if candidate["vi_token_count"] >= summary["min_tokens"]
                    else "keep_natural"
                ),
                "reason": "The lexical equivalent is natural and concise.",
                "reviewer": "reviewer",
                "reviewed_at": "2026-07-17",
                "approval": "approved",
            }
        )
        if review["decision"] == "keep_explanatory":
            review["shorter_vi_considered"] = "nhân chứng"
            review["preserved_distinction"] = (
                "The explanatory wording limits this sense to directly seeing "
                "the event happen."
            )

    assert review_summary["scope"] == "all"
    assert all(len(row["context_fingerprint"]) == 64 for row in reviews)
    assert validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    ) == []


def test_all_scope_rejects_keep_natural_for_long_gloss() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    witness = next(row for row in reviews if row["word"] == "witness")
    witness.update(
        {
            "decision": "keep_natural",
            "reason": "The wording was reviewed.",
            "reviewer": "reviewer",
            "reviewed_at": "2026-07-17",
            "approval": "approved",
        }
    )

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        [witness],
        require_complete=True,
    )

    assert any(
        "review_long_gloss_requires_explanatory_evidence" in error
        for error in errors
    )


def test_all_scope_allows_substantive_same_token_rewrite_for_short_gloss() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    for review in reviews:
        candidate = candidates_by_id[review["candidate_id"]]
        review.update(
            {
                "decision": (
                    "keep_explanatory"
                    if candidate["vi_token_count"] >= summary["min_tokens"]
                    else "keep_natural"
                ),
                "reason": "Reviewed against the promoted English sense.",
                "reviewer": "reviewer",
                "reviewed_at": "2026-07-17",
                "approval": "approved",
            }
        )
        if review["decision"] == "keep_explanatory":
            review["shorter_vi_considered"] = "nghĩa ngắn hơn"
            review["preserved_distinction"] = (
                "The current explanatory wording preserves a material restriction."
            )
    compact = next(row for row in reviews if row["word"] == "compact")
    compact["decision"] = "rewrite"
    compact["proposed_vi"] = "gọn nhẹ, dễ đem theo"

    assert len(compact["proposed_vi"].split()) == next(
        row["vi_token_count"] for row in candidates if row["word"] == "compact"
    )
    assert validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    ) == []

    updated = apply_vietnamese_review(
        registry_rows,
        audit_rows,
        card_rows,
        review_summary,
        reviews,
    )
    compact_card = next(card for card in updated if card["word"] == "compact")
    assert compact_card["semantic_senses"][0]["proposed"]["definition_vi"] == (
        compact["proposed_vi"]
    )


def test_all_scope_rejects_punctuation_only_rewrite_for_short_gloss() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    compact_candidate = next(row for row in candidates if row["word"] == "compact")
    compact = next(row for row in reviews if row["word"] == "compact")
    compact.update(
        {
            "decision": "rewrite",
            "proposed_vi": compact_candidate["definition_vi"].replace(",", ";"),
            "reason": "Punctuation is not a lexical rewrite.",
            "reviewer": "reviewer",
            "reviewed_at": "2026-07-17",
            "approval": "approved",
        }
    )

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        [compact],
        require_complete=True,
    )

    assert any("review_rewrite_without_substantive_change" in error for error in errors)


def test_scaffold_reuses_approved_verdict_only_when_context_and_final_vi_match() -> None:
    old_registry, old_audit, old_card = _card(
        "compel",
        "sem-compel",
        "force somebody to do something; make something necessary",
        "ép buộc; khiến trở nên cần thiết",
        "ép buộc; khiến trở nên cần thiết",
    )
    old_summary, old_candidates = build_vietnamese_audit(
        [old_registry],
        [old_audit],
        [old_card],
        scope="all",
    )
    _, old_reviews = scaffold_vietnamese_review(old_summary, old_candidates)
    old_review = old_reviews[0]
    old_review.update(
        {
            "decision": "rewrite",
            "proposed_vi": "ép buộc",
            "reason": "Use the natural lexical equivalent instead of clause translation.",
            "reviewer": "reviewer",
            "reviewed_at": "2026-07-17",
            "approval": "approved",
        }
    )

    new_registry, new_audit, new_card = _card(
        "compel",
        "sem-compel",
        "force somebody to do something; make something necessary",
        "ép buộc",
        "ép buộc",
    )
    new_summary, new_candidates = build_vietnamese_audit(
        [new_registry],
        [new_audit],
        [new_card],
        scope="all",
    )
    new_review_summary, retained = scaffold_vietnamese_review(
        new_summary,
        new_candidates,
        existing_review_rows=old_reviews,
    )

    assert retained == old_reviews
    assert validate_vietnamese_review(
        new_summary,
        new_candidates,
        new_review_summary,
        retained,
        require_complete=True,
    ) == []

    changed_registry, changed_audit, changed_card = _card(
        "compel",
        "sem-compel",
        "force somebody to act",
        "ép buộc",
        "ép buộc",
    )
    changed_summary, changed_candidates = build_vietnamese_audit(
        [changed_registry],
        [changed_audit],
        [changed_card],
        scope="all",
    )
    _, invalidated = scaffold_vietnamese_review(
        changed_summary,
        changed_candidates,
        existing_review_rows=old_reviews,
    )

    assert invalidated[0]["decision"] == "pending"
    assert invalidated[0]["approval"] == ""


def test_promotion_gate_accepts_complete_all_sense_review() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    for review in reviews:
        candidate = candidates_by_id[review["candidate_id"]]
        review.update(
            {
                "decision": (
                    "keep_explanatory"
                    if candidate["vi_token_count"] >= summary["min_tokens"]
                    else "keep_natural"
                ),
                "reason": "Natural lexical equivalent confirmed in context.",
                "reviewer": "reviewer",
                "reviewed_at": "2026-07-17",
                "approval": "approved",
            }
        )
        if review["decision"] == "keep_explanatory":
            review["shorter_vi_considered"] = "nhân chứng"
            review["preserved_distinction"] = (
                "The explanatory wording limits this sense to directly seeing "
                "the event happen."
            )

    assert validate_vietnamese_review_for_promotion(
        audit_rows,
        review_summary,
        reviews,
    ) == []


@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        ("long_scope", "promotion_review_scope_must_be_all"),
        ("missing", "promotion_review_missing_candidate"),
        ("pending", "promotion_review_open_or_invalid_decision"),
        ("stale_context", "promotion_review_stale_context"),
        ("final_vi", "promotion_review_final_vi_mismatch"),
        (
            "long_keep_natural",
            "promotion_review_long_gloss_requires_explanatory_evidence",
        ),
    ],
)
def test_promotion_gate_rejects_incomplete_or_stale_all_sense_review(
    problem: str,
    expected: str,
) -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    for review in reviews:
        candidate = candidates_by_id[review["candidate_id"]]
        review.update(
            {
                "decision": (
                    "keep_explanatory"
                    if candidate["vi_token_count"] >= summary["min_tokens"]
                    else "keep_natural"
                ),
                "reason": "Natural lexical equivalent confirmed in context.",
                "reviewer": "reviewer",
                "reviewed_at": "2026-07-17",
                "approval": "approved",
            }
        )
        if review["decision"] == "keep_explanatory":
            review["shorter_vi_considered"] = "nhân chứng"
            review["preserved_distinction"] = (
                "The explanatory wording limits this sense to directly seeing "
                "the event happen."
            )
    if problem == "long_scope":
        review_summary["scope"] = "long"
    elif problem == "missing":
        reviews.pop()
    elif problem == "pending":
        reviews[0]["decision"] = "pending"
        reviews[0]["approval"] = ""
    elif problem == "stale_context":
        audit_rows[0]["semantic_senses"][0]["proposed"]["definition_en"] = (
            "a materially changed English sense"
        )
    elif problem == "long_keep_natural":
        witness = next(row for row in reviews if row["word"] == "witness")
        witness["decision"] = "keep_natural"
        witness["shorter_vi_considered"] = ""
        witness["preserved_distinction"] = ""
    else:
        audit_rows[1]["semantic_senses"][0]["current"]["definition_vi"] = (
            "một nghĩa Việt khác"
        )

    errors = validate_vietnamese_review_for_promotion(
        audit_rows,
        review_summary,
        reviews,
    )

    assert errors == sorted(errors)
    assert any(expected in error for error in errors)


def test_report_and_review_serialization_are_deterministic() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    first = build_vietnamese_audit(registry_rows, audit_rows, card_rows)
    second = build_vietnamese_audit(
        copy.deepcopy(registry_rows),
        copy.deepcopy(audit_rows),
        copy.deepcopy(card_rows),
    )

    assert first == second
    assert serialize_vietnamese_audit(*first) == serialize_vietnamese_audit(*second)
    assert render_vietnamese_audit_markdown(*first) == (
        render_vietnamese_audit_markdown(*second)
    )
    assert serialize_vietnamese_review(*scaffold_vietnamese_review(*first)) == (
        serialize_vietnamese_review(*scaffold_vietnamese_review(*second))
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("definition_en", "mutated English"),
        ("definition_vi", "một nghĩa tiếng Việt đã bị sửa trong registry"),
        ("examples", ["Mutated example."]),
        ("source_sense_ids", ["ox_wrong"]),
        ("order", 2),
    ],
)
def test_report_rejects_registry_that_differs_from_effective_audit_payload(
    field: str,
    replacement: object,
) -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    registry_rows[0]["senses"][0][field] = replacement

    with pytest.raises(ValueError, match=f"promoted_sense_mismatch:.*:{field}"):
        build_vietnamese_audit(registry_rows, audit_rows, card_rows)


def test_apply_exact_rewrites_preserves_non_vietnamese_semantics() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    original = copy.deepcopy(audit_rows)
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)

    updated = apply_vietnamese_review(
        registry_rows,
        audit_rows,
        card_rows,
        review_summary,
        reviews,
    )

    assert audit_rows == original
    by_word = {card["word"]: card for card in updated}
    contender_before = original[0]["semantic_senses"][0]
    contender_after = by_word["contender"]["semantic_senses"][0]
    assert contender_after["proposed"]["definition_vi"] == "đối thủ nặng ký"
    assert contender_after["proposed"]["definition_en"] == (
        contender_before["proposed"]["definition_en"]
    )
    assert contender_after["proposed"]["examples"] == (
        contender_before["proposed"]["examples"]
    )
    assert contender_after["source_sense_ids"] == contender_before["source_sense_ids"]
    assert contender_after["cambridge"] == contender_before["cambridge"]
    assert contender_after["current"] == contender_before["current"]

    venture_before = original[1]["semantic_senses"][0]
    venture_after = by_word["venture"]["semantic_senses"][0]
    assert venture_after["proposed"] == {
        "definition_en": (
            "risk going somewhere, doing something, or saying something"
        ),
        "definition_vi": "mạo hiểm, cả gan",
        "examples": venture_before["current"]["examples"],
    }
    assert venture_after["source_sense_ids"] == venture_before["source_sense_ids"]
    assert venture_after["cambridge"] == venture_before["cambridge"]

    # An approved long explanation remains untouched; length is not a verdict.
    assert by_word["witness"] == original[2]
    assert by_word["compact"] == original[3]
    assert all(
        card["current"]["idioms"] == "untouched idiom :: untouched explanation"
        for card in updated
    )


@pytest.mark.parametrize("stale_part", ["inputs", "fingerprint", "definition"])
def test_apply_rejects_stale_review(stale_part: str) -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    if stale_part == "inputs":
        review_summary["inputs"]["semantic_registry"] = "0" * 64
    elif stale_part == "fingerprint":
        reviews[0]["candidate_fingerprint"] = "0" * 64
    else:
        reviews[0]["expected_definition_vi"] = "nội dung cũ"

    with pytest.raises(ValueError, match="stale"):
        apply_vietnamese_review(
            registry_rows,
            audit_rows,
            card_rows,
            review_summary,
            reviews,
        )


@pytest.mark.parametrize(
    "invalid_vi",
    [
        "",
        "   ",
        "nghĩa một|nghĩa hai",
        "xuống\ndòng",
        "xuống\rdòng",
        "có\ttab",
        "có<br>ngắt",
    ],
)
def test_rewrite_rejects_invalid_vietnamese(invalid_vi: str) -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    reviews[0]["proposed_vi"] = invalid_vi

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )

    assert any("invalid_proposed_vi" in error for error in errors)


def test_long_gloss_rewrite_must_compress_not_only_repunctuate() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    venture = next(row for row in reviews if row["word"] == "venture")
    venture["proposed_vi"] = (
        "máº¡o hiá»ƒm Ä‘i Ä‘Ã¢u, lÃ m hoáº·c nÃ³i má»™t Ä‘iá»u gÃ¬"
    )

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )

    assert any("review_rewrite_without_compression" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("shorter_vi_considered", "", "review_missing_shorter_vi_considered"),
        ("preserved_distinction", "", "review_missing_preserved_distinction"),
        (
            "shorter_vi_considered",
            "ngÆ°á»i nhÃ¬n tháº¥y má»™t sá»± viá»‡c xáº£y ra",
            "review_non_shorter_vi_considered",
        ),
    ],
)
def test_keep_explanatory_requires_a_shorter_counterfactual_and_exact_loss(
    field: str,
    value: str,
    expected: str,
) -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    witness = next(row for row in reviews if row["word"] == "witness")
    witness[field] = value

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )

    assert any(expected in error for error in errors)


@pytest.mark.parametrize("problem", ["missing", "extra", "duplicate", "uncertain"])
def test_complete_review_rejects_candidate_coverage_and_open_decisions(
    problem: str,
) -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    if problem == "missing":
        reviews.pop()
    elif problem == "extra":
        extra = copy.deepcopy(reviews[0])
        extra["candidate_id"] = "unknown::candidate"
        reviews.append(extra)
    elif problem == "duplicate":
        reviews.append(copy.deepcopy(reviews[0]))
    else:
        reviews[0]["decision"] = "uncertain"
        reviews[0]["proposed_vi"] = ""

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )

    expected = {
        "missing": "review_missing_candidate",
        "extra": "review_extra_candidate",
        "duplicate": "review_duplicate_or_empty_candidate",
        "uncertain": "review_open_decision",
    }[problem]
    assert any(expected in error for error in errors)
