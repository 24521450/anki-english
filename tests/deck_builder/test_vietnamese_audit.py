from __future__ import annotations

import copy
import hashlib

import pytest

from src.deck_builder.vietnamese_audit import (
    GLOSS_POLICY_VERSION,
    _candidate_fingerprint,
    _context_fingerprint,
    _context_fingerprint_v4,
    _context_fingerprint_v5,
    apply_vietnamese_review,
    build_vietnamese_audit,
    render_vietnamese_audit_markdown,
    scaffold_vietnamese_review,
    serialize_vietnamese_audit,
    serialize_vietnamese_review,
    validate_vietnamese_review,
    validate_vietnamese_review_for_promotion,
)


def _add_review_evidence(review: dict, candidate: dict) -> None:
    decision = review["decision"]
    final_vi = (
        review["proposed_vi"]
        if decision == "rewrite"
        else review["expected_definition_vi"]
    )
    review["reason_code"] = {
        "keep_natural": "natural_lexical_gloss",
        "keep_explanatory": "necessary_explanation",
        "rewrite": "natural_rewrite",
    }[decision]
    if candidate.get("gloss_policy_version") == GLOSS_POLICY_VERSION:
        review["reason_code"] = {
            "keep_natural": "lexical_core_confirmed",
            "keep_explanatory": "lexical_core_confirmed",
            "rewrite": "lexical_core_rewrite",
        }[decision]
    semantic_notes = {
        "compact": "The wording preserves both small size and practical portability.",
        "compel": "The wording names coercion without importing the separate necessity clause.",
        "contender": "The wording identifies a serious rival instead of narrating competition odds.",
        "venture": "The wording keeps the deliberate risk-taking action lexical and direct.",
        "witness": "The wording identifies a direct observer of the event rather than any participant.",
    }
    review["reason"] = f'{review["reason"]} {semantic_notes[candidate["word"]]}'
    support = (candidate.get("examples") or candidate.get("source_definitions") or [""])[0]
    review["semantic_evidence"] = (
        f'Final VI "{final_vi}" matches exact Definition EN '
        f'"{candidate["definition_en"]}" in the sense-specific evidence "{support}"; '
        f'{review["reason"]}'
    )
    review["lock_id"] = ""


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
        candidate = next(
            candidate
            for candidate in candidates
            if candidate["candidate_id"] == row["candidate_id"]
        )
        row["reason"] = (
            f'Exact EN "{candidate["definition_en"]}" is expressed naturally '
            "and concisely by the reviewed Vietnamese gloss."
        )
        if row["decision"] == "keep_explanatory":
            row["shorter_vi_considered"] = "nhân chứng"
            row["preserved_distinction"] = (
                "The current gloss explicitly limits this sense to directly seeing "
                "the event happen."
            )
        row["reviewer"] = "chatgpt-reviewer"
        row["reviewed_at"] = "2026-07-16"
        row["approval"] = "approved"
        _add_review_evidence(row, candidate)
    return review_summary, review_rows


def test_pending_review_can_carry_non_authoritative_vietnamese_suggestion():
    semantic_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        semantic_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)

    assert reviews[0]["suggested_vi"] == ""
    reviews[0]["suggested_vi"] = "nghĩa tiếng Việt gợi ý"

    assert validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=False,
    ) == []


def _complete_matching_review(
    summary: dict,
    candidates: list[dict],
) -> tuple[dict, list[dict]]:
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    distinctions = {
        "compact": "The wording retains both small size and easy portability.",
        "contender": "The wording keeps the competition participant and realistic winning chance.",
        "venture": "The wording retains going, doing, and speaking as forms of deliberate risk.",
        "witness": "The wording restricts the person to directly seeing the event happen.",
    }
    for review in reviews:
        candidate = candidates_by_id[review["candidate_id"]]
        review.update({
            "decision": (
                "keep_explanatory"
                if candidate["vi_token_count"] >= summary["min_tokens"]
                else "keep_natural"
            ),
            "reason": "The promoted wording was checked against its exact learner sense.",
            "reviewer": "reviewer",
            "reviewed_at": "2026-07-18",
            "approval": "approved",
        })
        if review["decision"] == "keep_explanatory":
            review["shorter_vi_considered"] = "nghĩa ngắn"
            review["preserved_distinction"] = distinctions[review["word"]]
        _add_review_evidence(review, candidate)
    return review_summary, reviews


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
                    "reason": (
                        f'Exact EN "{candidate["definition_en"]}" is expressed '
                        "naturally and concisely by this Vietnamese wording."
                    ),
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

        _add_review_evidence(review, candidate)

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

    witness_candidate = next(row for row in candidates if row["word"] == "witness")
    _add_review_evidence(witness, witness_candidate)

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
                    "reason": (
                        f'Reviewed against exact EN "{candidate["definition_en"]}" '
                        "and its sense-specific learner condition."
                    ),
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
        _add_review_evidence(review, candidate)
    compact = next(row for row in reviews if row["word"] == "compact")
    compact_candidate = candidates_by_id[compact["candidate_id"]]
    compact["decision"] = "rewrite"
    compact["proposed_vi"] = "gọn nhẹ, dễ đem theo"

    _add_review_evidence(compact, compact_candidate)

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
    _add_review_evidence(compact, compact_candidate)

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        [compact],
        require_complete=True,
    )

    assert any("review_rewrite_without_substantive_change" in error for error in errors)


def test_scaffold_resets_review_when_nonverb_current_vi_changes_to_old_rewrite() -> None:
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
    exact_reviews = copy.deepcopy(old_reviews)
    exact_review = exact_reviews[0]
    exact_review.update(
        {
            "decision": "keep_natural",
            "reason": "The existing wording preserves coercion and necessity explicitly.",
            "reviewer": "reviewer",
            "reviewed_at": "2026-07-17",
            "approval": "approved",
        }
    )
    _add_review_evidence(exact_review, old_candidates[0])
    unchanged_review_summary, unchanged = scaffold_vietnamese_review(
        old_summary,
        old_candidates,
        existing_review_rows=exact_reviews,
    )
    assert unchanged == exact_reviews
    assert validate_vietnamese_review(
        old_summary,
        old_candidates,
        unchanged_review_summary,
        unchanged,
        require_complete=True,
    ) == []

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
    _add_review_evidence(old_review, old_candidates[0])

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

    assert retained[0]["decision"] == "pending"
    assert retained[0]["approval"] == ""
    assert retained[0]["expected_definition_vi"] == new_candidates[0]["definition_vi"]
    assert validate_vietnamese_review(
        new_summary,
        new_candidates,
        new_review_summary,
        retained,
        require_complete=True,
    )

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


def test_all_scope_marks_every_verb_for_lexical_core_review() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )

    venture = next(row for row in candidates if row["word"] == "venture")
    compact = next(row for row in candidates if row["word"] == "compact")

    assert summary["gloss_policy_version"] == GLOSS_POLICY_VERSION
    assert venture["gloss_policy_version"] == GLOSS_POLICY_VERSION
    assert venture["style_findings"][0] == "verb_lexical_core_review"
    assert compact["gloss_policy_version"] == ""
    assert compact["style_findings"] == []


def test_source_evidence_order_does_not_stale_vietnamese_fingerprints() -> None:
    candidate = {
        "candidate_id": "guid::sense",
        "source_fingerprint": "old-card-source",
        "source_sense_ids": ["ox_2", "cam_1"],
        "source_definitions": ["Oxford definition", "Cambridge definition"],
    }
    reordered = copy.deepcopy(candidate)
    reordered["source_fingerprint"] = "new-card-source"
    reordered["source_sense_ids"].reverse()
    reordered["source_definitions"].reverse()

    assert _context_fingerprint(candidate) == _context_fingerprint(reordered)
    assert _candidate_fingerprint(candidate) == _candidate_fingerprint(reordered)


def test_v5_migration_reopens_verbs_but_reuses_unchanged_non_verbs() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
        scope="all",
    )
    _, reviews = _complete_matching_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    legacy = copy.deepcopy(reviews)
    for review in legacy:
        candidate = candidates_by_id[review["candidate_id"]]
        review["schema_version"] = 5
        review["candidate_fingerprint"] = "legacy"
        review["context_fingerprint"] = _context_fingerprint_v5(candidate)
        review.pop("gloss_policy_version", None)
        review.pop("style_findings", None)

    _, migrated = scaffold_vietnamese_review(
        summary,
        candidates,
        existing_review_rows=legacy,
    )
    by_word = {row["word"]: row for row in migrated}

    assert by_word["venture"]["decision"] == "pending"
    assert by_word["venture"]["approval"] == ""
    assert by_word["compact"]["decision"] != "pending"
    assert by_word["compact"]["schema_version"] == 6


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
                    "reason": (
                        f'Exact EN "{candidate["definition_en"]}" confirms this '
                        "natural lexical equivalent in its learner context."
                    ),
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

        _add_review_evidence(review, candidate)

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
        _add_review_evidence(review, candidate)
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
        witness_candidate = next(
            candidate for candidate in candidates if candidate["word"] == "witness"
        )
        _add_review_evidence(witness, witness_candidate)
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


def test_vietnamese_generic_evidence_is_not_row_specific() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    contender = next(row for row in reviews if row["word"] == "contender")
    final_vi = (
        contender["proposed_vi"]
        if contender["decision"] == "rewrite"
        else contender["expected_definition_vi"]
    )
    contender["semantic_evidence"] = (
        f'Final VI "{final_vi}": tự nhiên và rõ nghĩa'
    )

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )

    assert any("generic_semantic_evidence" in error for error in errors)


def test_interpolated_boilerplate_is_duplicate_across_different_words_and_vi() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    first, second = reviews[:2]
    assert first["word"] != second["word"]

    for review in (first, second):
        final_vi = (
            review["proposed_vi"]
            if review["decision"] == "rewrite"
            else review["expected_definition_vi"]
        )
        review["reason"] = (
            f'“{final_vi}” is already a concise, idiomatic lexical gloss '
            f'for this sense of “{review["word"]}”.'
        )
        review["semantic_evidence"] = f'Final VI "{final_vi}": {review["reason"]}'

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )

    assert any("reason_generic_template" in error for error in errors)
    assert any("evidence_generic_template" in error for error in errors)
    assert any("reason_duplicate_template" in error for error in errors)
    assert any("evidence_duplicate_template" in error for error in errors)


def test_exact_source_interpolation_and_unique_hash_tokens_do_not_close_review() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}

    for review in reviews:
        candidate = candidates_by_id[review["candidate_id"]]
        final_vi = (
            review["proposed_vi"]
            if review["decision"] == "rewrite"
            else review["expected_definition_vi"]
        )
        support = candidate["examples"][0]
        review["reason"] = (
            f'Definition EN "{candidate["definition_en"]}" and example '
            f'"{support}" approve "{final_vi}".'
        )
        review["semantic_evidence"] = (
            f'Final VI "{final_vi}"; Definition EN "{candidate["definition_en"]}"; '
            f'example "{support}"; approved for this sense.'
        )

    duplicate_errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )
    assert any("duplicate_template" in error for error in duplicate_errors)

    for review in reviews:
        token = hashlib.sha256(review["candidate_id"].encode()).hexdigest()[:12]
        review["reason"] += f" {token}"
        review["semantic_evidence"] += f" {token}"

    token_errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )
    assert any("suspicious_token" in error for error in token_errors)


def test_ordinary_evidence_requires_exact_english_and_example_grounding() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    review_summary, reviews = _complete_review(summary, candidates)
    contender = next(row for row in reviews if row["word"] == "contender")
    contender["semantic_evidence"] = (
        f'Final VI "{contender["proposed_vi"]}": reviewed without exact source text.'
    )

    errors = validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    )

    assert any("evidence_missing_definition_en" in error for error in errors)
    assert any("evidence_missing_support" in error for error in errors)


def test_source_definition_grounds_a_sense_without_examples() -> None:
    registry, audit, card = _card(
        "compel",
        "sem-compel",
        "force somebody to act",
        "ép buộc",
        "ép buộc",
    )
    registry["senses"][0]["examples"] = []
    audit["semantic_senses"][0]["current"]["examples"] = []
    summary, candidates = build_vietnamese_audit(
        [registry],
        [audit],
        [card],
        scope="all",
    )
    review_summary, reviews = scaffold_vietnamese_review(summary, candidates)
    review = reviews[0]
    candidate = candidates[0]
    review.update({
        "decision": "keep_natural",
        "reason": "The direct lexical equivalent preserves the force relation.",
        "reviewer": "reviewer",
        "reviewed_at": "2026-07-18",
        "approval": "approved",
    })
    _add_review_evidence(review, candidate)

    assert candidate["examples"] == []
    assert candidate["source_definitions"] == ["force somebody to act"]
    assert validate_vietnamese_review(
        summary,
        candidates,
        review_summary,
        reviews,
        require_complete=True,
    ) == []


def test_v4_migration_enriches_and_reuses_unique_reviews() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    _, reviews = _complete_matching_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    legacy = copy.deepcopy(reviews)
    for review in legacy:
        candidate = candidates_by_id[review["candidate_id"]]
        final_vi = (
            review["proposed_vi"]
            if review["decision"] == "rewrite"
            else review["expected_definition_vi"]
        )
        review["semantic_evidence"] = (
            f'Final VI "{final_vi}": {review["reason"]}'
        )
        review["schema_version"] = 4
        review["candidate_fingerprint"] = "legacy"
        review["context_fingerprint"] = _context_fingerprint_v4(candidate)

    migrated_summary, migrated = scaffold_vietnamese_review(
        summary,
        candidates,
        existing_review_rows=legacy,
    )

    assert migrated_summary["schema_version"] == 6
    assert all(row["schema_version"] == 6 for row in migrated)
    assert next(row for row in migrated if row["word"] == "venture")[
        "decision"
    ] == "pending"
    assert all(
        row["decision"] != "pending"
        for row in migrated
        if row["word"] != "venture"
    )
    assert [row["candidate_fingerprint"] for row in migrated] == [
        row["candidate_fingerprint"] for row in candidates
    ]
    for review in migrated:
        if review["decision"] == "pending":
            continue
        candidate = candidates_by_id[review["candidate_id"]]
        support = (candidate["examples"] or candidate["source_definitions"])[0]
        assert f'Definition EN "{candidate["definition_en"]}".' in review[
            "semantic_evidence"
        ]
        assert f'Support "{support}".' in review["semantic_evidence"]


def test_v4_migration_resets_every_member_of_duplicate_template_group() -> None:
    registry_rows, audit_rows, card_rows = _inputs()
    summary, candidates = build_vietnamese_audit(
        registry_rows,
        audit_rows,
        card_rows,
    )
    _, reviews = _complete_matching_review(summary, candidates)
    candidates_by_id = {row["candidate_id"]: row for row in candidates}
    for review in reviews:
        candidate = candidates_by_id[review["candidate_id"]]
        final_vi = (
            review["proposed_vi"]
            if review["decision"] == "rewrite"
            else review["expected_definition_vi"]
        )
        review["reason"] = (
            f'Final VI "{final_vi}" is approved for this lexical wording.'
        )
        review["semantic_evidence"] = (
            f'Final VI "{final_vi}": approved for this lexical wording.'
        )
        review["schema_version"] = 4
        review["candidate_fingerprint"] = "legacy"
        review["context_fingerprint"] = _context_fingerprint_v4(candidate)

    _, migrated = scaffold_vietnamese_review(
        summary,
        candidates,
        existing_review_rows=reviews,
    )

    assert all(row["decision"] == "pending" for row in migrated)
    assert all(row["approval"] == "" for row in migrated)
