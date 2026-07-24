import copy
import hashlib

import pytest

from src.deck_builder.definition_audit import (
    DEFINITION_AUDIT_SCHEMA_VERSION,
    apply_definition_review_overrides,
    build_definition_audit,
    scaffold_definition_review,
    serialize_definition_audit,
    serialize_definition_review,
    validate_definition_audit,
    validate_definition_review_for_promotion,
)


AUDIT_SHA = "a" * 64
SOURCE_SHA = "b" * 64


def _card_registry(word="uphold", guid="g-uphold"):
    return [{
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "verb",
        "status": "active",
    }]


def _semantic_registry(
    definition_en="support and keep a principle or law; confirm that a decision is correct",
    definition_vi="duy trì/bảo vệ nguyên tắc / luật; xác nhận quyết định là đúng",
    *,
    word="uphold",
    guid="g-uphold",
    examples=None,
):
    return [{
        "schema_version": 4,
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "verb",
        "audit_sha256": AUDIT_SHA,
        "source_fingerprint": SOURCE_SHA,
        "idiom_audit_sha256": "c" * 64,
        "vietnamese_review_sha256": "f" * 64,
        "semantic_policy_sha256": "1" * 64,
        "definition_review_sha256": "2" * 64,
        "sense_merge_review_sha256": "3" * 64,
        "idioms": [],
        "senses": [{
            "semantic_sense_id": "sem-1",
            "order": 1,
            "definition_en": definition_en,
            "definition_vi": definition_vi,
            "examples": examples or [
                "We have a duty to uphold the law.",
                "The court upheld the conviction.",
            ],
            "source_sense_ids": ["ox-1", "ox-2"],
            "cambridge_match": "exact",
            "translation_provenance": "cambridge_reference",
        }],
    }]


def _notes(registry):
    row = registry[0]
    sense = row["senses"][0]
    definition = f"{sense['definition_en']} ({sense['definition_vi']})"
    example = "<br><br>".join(sense["examples"])
    return [{
        "guid": row["guid"],
        "word": row["word"],
        "cefr": row["cefr"],
        "pos": row["pos"],
        "definition": definition,
        "example": example,
    }]


def _audit(word="uphold", guid="g-uphold", *, source_count=2):
    sources = []
    coverage = []
    definitions = [
        "to support a law or principle and make sure it continues",
        "to agree that a previous decision was correct",
    ]
    examples = [
        "We have a duty to uphold the law.",
        "The court upheld the conviction.",
    ]
    for index in range(source_count):
        source_id = f"ox-{index + 1}"
        sources.append({
            "source_sense_id": source_id,
            "source": "Oxford",
            "pos": "verb",
            "cefr_original": "C1",
            "cefr_resolved": "C1",
            "sensenum_local": str(index + 1),
            "definition": definitions[index],
            "examples": [examples[index]],
            "source_files": ["uphold.html"],
        })
        coverage.append({
            "source_sense_id": source_id,
            "disposition": "mapped",
            "target_semantic_sense_ids": ["sem-1"],
            "reason": "Reviewed mapping.",
        })
    return [{
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "pos": "verb",
        "source_fingerprint": SOURCE_SHA,
        "source_senses": sources,
        "source_coverage": coverage,
        "semantic_senses": [{"semantic_sense_id": "sem-1", "decision": "pass"}],
    }]


def _build(registry=None, audit=None, card_registry=None, *, scope="long"):
    registry = registry or _semantic_registry()
    audit = audit or _audit()
    card_registry = card_registry or _card_registry()
    return build_definition_audit(
        registry,
        _notes(registry),
        audit,
        card_registry,
        input_hashes={
            "bilingual_semantic_audit": AUDIT_SHA,
            "build_notes": "c" * 64,
            "card_registry": "d" * 64,
            "semantic_registry": "e" * 64,
        },
        scope=scope,
    )


def test_uphold_is_a_two_sense_evidence_backed_split():
    summary, candidates = _build()

    assert summary["candidate_senses"] == summary["candidate_cards"] == 1
    candidate = candidates[0]
    assert candidate["recommendation"] == "split"
    assert candidate["proposal"]["definition"] == (
        "keep a law/principle (duy trì luật/nguyên tắc)|"
        "confirm a decision (xác nhận quyết định đúng)"
    )
    assert candidate["proposal"]["example"] == (
        "We have a duty to uphold the law.|The court upheld the conviction."
    )
    assert len(candidate["proposal"]["segments"]) == 2
    assert {row["source_sense_id"] for row in candidate["evidence"]["source_senses"]} == {
        "ox-1", "ox-2"
    }


def test_semicolon_with_one_oxford_sense_is_not_automatically_split():
    registry = _semantic_registry(
        "break without dividing into parts; break something in this way",
        "nứt mà không tách rời; làm vật gì nứt theo cách này",
        word="crack",
        guid="g-crack",
        examples=["The ice cracked."],
    )
    registry[0]["senses"][0]["source_sense_ids"] = ["ox-1"]
    summary, candidates = _build(
        registry,
        _audit("crack", "g-crack", source_count=1),
        _card_registry("crack", "g-crack"),
    )

    assert summary["candidate_senses"] == 1
    assert candidates[0]["recommendation"] == "keep_common"
    assert len(candidates[0]["proposal"]["segments"]) == 1


def test_token_threshold_finds_verbose_definition_below_character_threshold():
    definition_en = "person responsible for arranging every practical detail of a large public event"
    assert len(definition_en) < 80
    assert ";" not in definition_en and "/" not in definition_en
    assert " and " not in definition_en
    registry = _semantic_registry(
        definition_en,
        "ngÆ°á»i phá»¥ trÃ¡ch sáº¯p xáº¿p má»i chi tiáº¿t thá»±c táº¿ cá»§a má»™t sá»± kiá»‡n lá»›n",
        word="organizer",
        guid="g-organizer",
        examples=["The organizer checked the venue."],
    )
    registry[0]["senses"][0]["source_sense_ids"] = ["ox-1"]

    summary, candidates = _build(
        registry,
        _audit("organizer", "g-organizer", source_count=1),
        _card_registry("organizer", "g-organizer"),
    )

    assert summary["thresholds"]["minimum_definition_tokens"] == 12
    assert len(candidates) == 1
    assert candidates[0]["current"]["definition_token_count"] == 12
    assert "token_threshold" in candidates[0]["triggers"]


def test_split_keeps_same_numbered_senses_from_different_pos_and_maps_examples():
    registry = _semantic_registry(
        "warning of danger or a problem; warn sb about danger",
        "lời cảnh báo; cảnh báo ai về nguy hiểm",
        word="alert",
        guid="g-alert",
        examples=["a bomb/fire alert", "Police were alerted to the danger."],
    )
    audit = _audit("alert", "g-alert")
    audit[0]["source_senses"] = [
        {
            **audit[0]["source_senses"][0],
            "source_sense_id": "ox-verb-1",
            "pos": "verb",
            "sensenum_local": "1",
            "definition": "to warn somebody about a dangerous situation",
            "examples": ["Police were alerted to the danger."],
        },
        {
            **audit[0]["source_senses"][1],
            "source_sense_id": "ox-noun-1",
            "pos": "noun",
            "sensenum_local": "1",
            "definition": "a warning of danger or of a problem",
            "examples": ["a bomb/fire alert"],
        },
    ]
    audit[0]["source_coverage"] = [
        {
            "source_sense_id": source["source_sense_id"],
            "disposition": "mapped",
            "target_semantic_sense_ids": ["sem-1"],
            "reason": "Reviewed mapping.",
        }
        for source in audit[0]["source_senses"]
    ]
    registry[0]["senses"][0]["source_sense_ids"] = ["ox-verb-1", "ox-noun-1"]

    _, candidates = _build(
        registry,
        audit,
        _card_registry("alert", "g-alert"),
    )

    segments = candidates[0]["proposal"]["segments"]
    assert candidates[0]["recommendation"] == "split"
    assert segments[0]["source_sense_ids"] == ["ox-noun-1"]
    assert segments[0]["examples"] == ["a bomb/fire alert"]
    assert segments[1]["source_sense_ids"] == ["ox-verb-1"]
    assert segments[1]["examples"] == ["Police were alerted to the danger."]


@pytest.mark.parametrize(
    ("definition", "is_candidate"),
    [
        ("short and simple", False),
        ("law/principle", False),
        ("x" * 80, True),
        ("a" * 30 + " and " + "b" * 30, True),
        ("a" * 30 + "/" + "b" * 30, True),
        ("two clauses; still short", True),
    ],
)
def test_hybrid_candidate_thresholds(definition, is_candidate):
    registry = _semantic_registry(
        definition,
        "nghĩa tiếng Việt",
        word="sample",
        guid="g-sample",
        examples=["A sample example."],
    )
    registry[0]["senses"][0]["source_sense_ids"] = ["ox-1"]
    summary, _ = _build(
        registry,
        _audit("sample", "g-sample", source_count=1),
        _card_registry("sample", "g-sample"),
    )
    assert bool(summary["candidate_senses"]) is is_candidate


def test_all_scope_covers_short_definition_bearing_senses():
    registry = _semantic_registry(
        "easy to understand",
        "dễ hiểu",
        word="plain",
        guid="g-plain",
        examples=["The meaning is plain."],
    )
    registry[0]["senses"][0]["source_sense_ids"] = ["ox-1"]

    summary, candidates = _build(
        registry,
        _audit("plain", "g-plain", source_count=1),
        _card_registry("plain", "g-plain"),
        scope="all",
    )

    assert summary["scope"] == "all"
    assert summary["candidate_senses"] == summary["senses_scanned"] == 1
    assert candidates[0]["triggers"] == []


def test_report_serialization_is_deterministic_and_valid():
    first = _build()
    second = _build()
    assert serialize_definition_audit(*first) == serialize_definition_audit(*second)
    assert validate_definition_audit(*first) == []


def test_report_validator_rejects_stale_recommendation_counts():
    summary, candidates = _build()
    summary["recommendations"]["split"] = 0
    assert "recommendation_count_mismatch" in validate_definition_audit(
        summary, candidates
    )


def test_review_override_can_keep_a_heuristic_split_without_touching_inputs():
    summary, candidates = _build()
    row = candidates[0]
    review_summary = {
        "record_type": "review_summary",
        "schema_version": DEFINITION_AUDIT_SCHEMA_VERSION,
        "inputs": summary["inputs"],
    }
    reviewed_summary, reviewed = apply_definition_review_overrides(
        summary,
        candidates,
        review_summary,
        [{
            "guid": row["guid"],
            "semantic_sense_id": row["semantic_sense_id"],
            "source_fingerprint": row["source_fingerprint"],
            "recommendation": "keep_common",
            "use_current": True,
            "semantic_reason": "The two forms share one learning unit.",
        }],
        review_sha256="f" * 64,
    )
    assert reviewed_summary["recommendations"] == {
        "keep_common": 1,
        "split": 0,
        "uncertain": 0,
    }
    assert reviewed[0]["proposal"]["definition"] == row["current"]["rendered_definition"]
    assert reviewed[0]["review"]["approval"] == ""


def test_review_override_rejects_stale_inputs():
    summary, candidates = _build()
    with pytest.raises(ValueError, match="definition_review_stale_inputs"):
        apply_definition_review_overrides(
            summary,
            candidates,
            {
                "record_type": "review_summary",
                "schema_version": DEFINITION_AUDIT_SCHEMA_VERSION,
                "inputs": {},
            },
            [],
            review_sha256="f" * 64,
        )


def test_build_definition_example_misalignment_fails_closed():
    registry = _semantic_registry()
    notes = _notes(registry)
    notes[0]["example"] += "|unexpected"
    with pytest.raises(ValueError, match="build_definition_example_alignment"):
        build_definition_audit(
            registry,
            notes,
            _audit(),
            _card_registry(),
            input_hashes={
                "bilingual_semantic_audit": AUDIT_SHA,
                "build_notes": "c" * 64,
                "card_registry": "d" * 64,
                "semantic_registry": "e" * 64,
            },
        )


def test_stale_audit_hash_fails_closed():
    registry = copy.deepcopy(_semantic_registry())
    registry[0]["audit_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="semantic_registry_stale_audit_sha256"):
        _build(registry)


def _approved_definition_review(summary, candidates):
    review_summary, reviews = scaffold_definition_review(summary, candidates)
    review = reviews[0]
    current = review["expected_definition_en"]
    alternative = "support a law or principle"
    distinction = (
        "the separate legal-review sense in which a court confirms an earlier decision"
    )
    support = candidates[0]["current"]["examples"][1]
    review.update({
        "decision": "keep_explanatory",
        "shorter_en_considered": alternative,
        "preserved_distinction": distinction,
        "reason": "Both mapped Oxford senses remain material to this learner unit.",
        "semantic_evidence": (
            f'Final EN "{current}"; shorter "{alternative}" omits {distinction}; '
            f'exact learner example "{support}" verifies the legal-review use.'
        ),
        "reviewer": "reviewer@example",
        "reviewed_at": "2026-07-18",
        "approval": "approved",
    })
    return review_summary, reviews


def _approved_concise_definition_review(summary, candidates):
    review_summary, reviews = scaffold_definition_review(summary, candidates)
    review = reviews[0]
    current = review["expected_definition_en"]
    support = candidates[0]["current"]["examples"][0]
    review.update({
        "decision": "keep_concise",
        "reason": "The definition states this learner meaning directly in three words.",
        "semantic_evidence": (
            f'Current EN "{current}" directly matches the learner example "{support}".'
        ),
        "reviewer": "reviewer@example",
        "reviewed_at": "2026-07-24",
        "approval": "approved",
    })
    return review_summary, reviews


def test_definition_review_scaffold_is_deterministic_and_exact_coverage():
    summary, candidates = _build()
    first = scaffold_definition_review(summary, candidates)
    second = scaffold_definition_review(summary, candidates)

    assert serialize_definition_review(*first) == serialize_definition_review(*second)
    assert first[0]["candidate_set_sha256"] == summary["candidate_set_sha256"]
    assert first[0]["candidate_count"] == len(first[1]) == len(candidates)
    assert first[1][0]["candidate_id"] == candidates[0]["candidate_id"]
    assert len(first[1][0]["candidate_fingerprint"]) == 64

    missing_errors = validate_definition_review_for_promotion(
        summary, candidates, first[0], []
    )
    assert any(error.startswith("definition_review_missing_candidate:") for error in missing_errors)

    extra = copy.deepcopy(first[1][0])
    extra["candidate_id"] = "unknown::sense"
    extra_errors = validate_definition_review_for_promotion(
        summary, candidates, first[0], [*first[1], extra]
    )
    assert "definition_review_extra_candidate:unknown::sense" in extra_errors
    assert serialize_definition_review(
        first[0],
        [
            {"candidate_id": "b", "value": 2},
            {"candidate_id": "a", "value": 1},
        ],
    ) == serialize_definition_review(
        first[0],
        [
            {"candidate_id": "a", "value": 1},
            {"candidate_id": "b", "value": 2},
        ],
    )


def test_definition_review_scaffold_reuses_only_unchanged_fingerprints():
    summary, candidates = _build()
    _, reviews = _approved_definition_review(summary, candidates)

    _, reused = scaffold_definition_review(
        summary, candidates, existing_review_rows=reviews
    )
    assert reused == reviews

    stale = copy.deepcopy(reviews)
    stale[0]["candidate_fingerprint"] = "0" * 64
    _, reset = scaffold_definition_review(
        summary, candidates, existing_review_rows=stale
    )
    assert reset[0]["decision"] == "pending"
    assert reset[0]["candidate_fingerprint"] == candidates[0][
        "candidate_fingerprint"
    ]


def test_definition_review_rejects_stale_candidate_fingerprint_and_set():
    summary, candidates = _build()
    review_summary, reviews = _approved_definition_review(summary, candidates)
    reviews[0]["candidate_fingerprint"] = "0" * 64
    review_summary["candidate_set_sha256"] = "1" * 64

    errors = validate_definition_review_for_promotion(
        summary, candidates, review_summary, reviews
    )

    assert "definition_review_stale_candidate_set" in errors
    assert any(error.startswith("definition_review_stale_candidate:") for error in errors)


def test_definition_review_does_not_bind_downstream_artifact_hashes():
    summary, candidates = _build(scope="all")
    review_summary, reviews = _approved_definition_review(summary, candidates)
    rebuilt_summary = copy.deepcopy(summary)
    rebuilt_summary["inputs"]["semantic_registry"] = "9" * 64
    rebuilt_summary["inputs"]["build_notes"] = "8" * 64

    assert "inputs" not in review_summary
    assert validate_definition_review_for_promotion(
        rebuilt_summary, candidates, review_summary, reviews
    ) == []


def test_definition_review_rejects_generic_evidence():
    summary, candidates = _build()
    review_summary, reviews = _approved_definition_review(summary, candidates)
    reviews[0]["preserved_distinction"] = "loses meaning"
    reviews[0]["semantic_evidence"] = "looks good"

    errors = validate_definition_review_for_promotion(
        summary, candidates, review_summary, reviews
    )

    assert any(
        error.startswith("definition_review_generic_preserved_distinction:")
        for error in errors
    )
    assert any(
        error.startswith("definition_review_generic_semantic_evidence:")
        for error in errors
    )


@pytest.mark.parametrize(
    "decision",
    ["pending", "rewrite_required", "split_required", "uncertain"],
)
def test_non_final_definition_review_decisions_block_promotion(decision):
    summary, candidates = _build()
    review_summary, reviews = scaffold_definition_review(summary, candidates)
    reviews[0].update({
        "decision": decision,
        "reason": "The learner payload still needs an applied semantic change.",
        "reviewer": "reviewer@example",
        "reviewed_at": "2026-07-18",
        "approval": "approved",
    })

    errors = validate_definition_review_for_promotion(
        summary, candidates, review_summary, reviews
    )

    assert any(
        error.endswith(f":{decision}")
        and error.startswith("definition_promotion_open_decision:")
        for error in errors
    )


def test_approved_keep_with_shorter_alternative_and_exact_loss_passes_gate():
    summary, candidates = _build(scope="all")
    review_summary, reviews = _approved_definition_review(summary, candidates)

    assert validate_definition_review_for_promotion(
        summary, candidates, review_summary, reviews
    ) == []


def test_approved_keep_concise_with_row_specific_evidence_passes_all_scope_gate():
    registry = _semantic_registry(
        "easy to understand",
        "dễ hiểu",
        word="plain",
        guid="g-plain",
        examples=["The meaning is plain."],
    )
    registry[0]["senses"][0]["source_sense_ids"] = ["ox-1"]
    summary, candidates = _build(
        registry,
        _audit("plain", "g-plain", source_count=1),
        _card_registry("plain", "g-plain"),
        scope="all",
    )
    review_summary, reviews = _approved_concise_definition_review(
        summary, candidates
    )

    assert validate_definition_review_for_promotion(
        summary, candidates, review_summary, reviews
    ) == []


def test_keep_concise_rejects_triggered_wording_and_long_scope_promotion():
    long_summary, long_candidates = _build(scope="long")
    review_summary, reviews = scaffold_definition_review(
        long_summary, long_candidates
    )
    review = reviews[0]
    review.update({
        "decision": "keep_concise",
        "reason": "The definition already states the learner meaning directly.",
        "semantic_evidence": (
            f'Current EN "{review["expected_definition_en"]}" matches exact learner '
            f'example "{long_candidates[0]["current"]["examples"][0]}".'
        ),
        "reviewer": "reviewer@example",
        "reviewed_at": "2026-07-24",
        "approval": "approved",
    })

    errors = validate_definition_review_for_promotion(
        long_summary, long_candidates, review_summary, reviews
    )

    assert any("keep_concise_not_short" in error for error in errors)
    assert "definition_review_scope_must_be_all" in errors


def test_definition_gate_rejects_placeholder_and_identifier_filler():
    summary, candidates = _build()
    review_summary, reviews = scaffold_definition_review(summary, candidates)
    review = reviews[0]
    current = review["expected_definition_en"]
    token = hashlib.sha256(review["candidate_id"].encode()).hexdigest()[:12]
    distinction = f"unique token {token}"
    review.update({
        "decision": "keep_explanatory",
        "shorter_en_considered": "x",
        "preserved_distinction": distinction,
        "reason": "approved",
        "semantic_evidence": f"{current}; x; {distinction}",
        "reviewer": "r",
        "reviewed_at": "x",
        "approval": "approved",
    })

    errors = validate_definition_review_for_promotion(
        summary,
        candidates,
        review_summary,
        reviews,
    )

    assert any("non_substantive_alternative" in error for error in errors)
    assert any("invalid_reviewer" in error for error in errors)
    assert any("invalid_reviewed_at" in error for error in errors)
    assert any("generic_reason" in error for error in errors)
    assert any("missing_grounding" in error for error in errors)
    assert any("suspicious_token" in error for error in errors)
