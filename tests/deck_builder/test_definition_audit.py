import copy

import pytest

from src.deck_builder.definition_audit import (
    apply_definition_review_overrides,
    build_definition_audit,
    serialize_definition_audit,
    validate_definition_audit,
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
    definition_vi="duy trì/bảo vệ nguyên tắc hoặc luật; xác nhận quyết định là đúng",
    *,
    word="uphold",
    guid="g-uphold",
    examples=None,
):
    return [{
        "schema_version": 1,
        "guid": guid,
        "word": word,
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "verb",
        "audit_sha256": AUDIT_SHA,
        "source_fingerprint": SOURCE_SHA,
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


def _build(registry=None, audit=None, card_registry=None):
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
    review_summary = {"record_type": "review_summary", "schema_version": 1, "inputs": summary["inputs"]}
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
            {"record_type": "review_summary", "schema_version": 1, "inputs": {}},
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
