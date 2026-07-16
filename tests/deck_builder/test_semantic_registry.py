from copy import deepcopy
import hashlib
import json

import pytest

from src.config import ProjectPaths
from src.deck_builder.build_contracts import BuiltCard
from src.deck_builder.semantic_registry import (
    SEMANTIC_REGISTRY_SCHEMA_VERSION,
    apply_semantic_registry,
    promote_audit_rows,
    serialize_semantic_registry,
    validate_semantic_registry_rows,
)


AUDIT_SHA = "a" * 64
SOURCE_SHA = "b" * 64


def _registry(**overrides):
    row = {
        "guid": "guid-1", "word": "equate", "cefr": "C1",
        "list": "Oxford_5000", "variant": "", "pos": "verb", "status": "active",
    }
    row.update(overrides)
    return row


def _sense(**overrides):
    sense = {
        "semantic_sense_id": "sem-1", "order": 1, "source_sense_ids": [],
        "current": {
            "definition_en": "consider equal", "definition_vi": "đánh đồng",
            "examples": ["Do not equate wealth with happiness."],
        },
        "checks": {
            "english_semantics": "pass", "vietnamese_semantics": "pass",
            "simplicity": "pass", "example_pos_alignment": "pass",
        },
        "decision": "pass",
        "proposed": {"definition_en": "", "definition_vi": "", "examples": []},
        "cambridge": {
            "url": "https://dictionary.cambridge.org/dictionary/english-vietnamese/equate",
            "match": "exact", "summary": "", "translation_provenance": "cambridge_reference",
            "accessed_at": "2026-07-15",
        },
        "confidence": "high", "review_reason": "reviewed", "reviewer": "reviewer",
        "reviewed_at": "2026-07-15", "approval": "",
    }
    sense.update(overrides)
    return sense


def _audit(**overrides):
    row = {
        "schema_version": 1, "guid": "guid-1", "word": "equate", "cefr": "C1",
        "list": "Oxford_5000", "variant": "", "pos": "verb",
        "current": {
            "definition": "consider equal (đánh đồng)",
            "example": "Do not equate wealth with happiness.", "idioms": "",
        },
        "semantic_senses": [_sense()], "source_senses": [], "source_coverage": [],
        "coverage": {
            "status": "pass", "reason": "", "candidate_source_sense_ids": [],
            "expected_same_cefr_source_sense_ids": [],
        },
        "source_fingerprint": SOURCE_SHA,
    }
    row.update(overrides)
    return row


def _promoted_sense(**overrides):
    sense = {
        "semantic_sense_id": "sem-1", "order": 1,
        "definition_en": "consider equal", "definition_vi": "đánh đồng",
        "examples": ["Do not equate wealth with happiness."],
        "source_sense_ids": [], "cambridge_match": "exact",
        "translation_provenance": "cambridge_reference",
    }
    sense.update(overrides)
    return sense


def _promoted(**overrides):
    row = {
        "schema_version": SEMANTIC_REGISTRY_SCHEMA_VERSION,
        "guid": "guid-1", "word": "equate", "cefr": "C1",
        "list": "Oxford_5000", "variant": "", "pos": "verb",
        "audit_sha256": AUDIT_SHA, "source_fingerprint": SOURCE_SHA,
        "senses": [_promoted_sense()],
    }
    row.update(overrides)
    return row


def _card(**overrides):
    values = {
        "guid": "guid-1", "notetype": "English Academic Vocabulary Model",
        "deck": "Deck", "word": "equate", "pos": "verb", "ipa": "/ɪˈkweɪt/",
        "definition": "old", "example": "old example", "collocations": "equate A with B",
        "wordfamily": "equation", "uk_audio": "uk", "us_audio": "us",
        "source1": "Oxford", "source2": "Oxford", "cefr": "C1", "idioms": "",
        "tags": "CEFR::C1", "synonyms": "", "antonyms": "",
        "example_audio_uk": "old uk", "example_audio_us": "old us",
        "idiom_example_audio_uk": "", "idiom_example_audio_us": "",
        "definition_vi": "old vi",
    }
    values.update(overrides)
    return BuiltCard(**values)


def test_promotion_is_deterministic_and_selects_pass_current_content():
    rows = promote_audit_rows([_audit()], [_registry()], audit_sha256=AUDIT_SHA)
    assert rows == promote_audit_rows([_audit()], [_registry()], audit_sha256=AUDIT_SHA)
    assert rows[0]["senses"] == [_promoted_sense()]
    assert serialize_semantic_registry(rows) == serialize_semantic_registry(deepcopy(rows))
    assert serialize_semantic_registry(rows).endswith("\n")


def test_promotion_selects_complete_approved_repair_content():
    repaired = _sense(
        decision="repair_proposed", approval="approved",
        checks={
            "english_semantics": "repair", "vietnamese_semantics": "pass",
            "simplicity": "pass", "example_pos_alignment": "repair",
        },
        proposed={
            "definition_en": "treat as equal", "definition_vi": "coi là ngang nhau",
            "examples": ["They equated money with success."],
        },
    )
    rows = promote_audit_rows(
        [_audit(semantic_senses=[repaired])], [_registry()], audit_sha256=AUDIT_SHA
    )
    assert rows[0]["senses"][0]["definition_en"] == "treat as equal"
    assert rows[0]["senses"][0]["definition_vi"] == "coi là ngang nhau"
    assert rows[0]["senses"][0]["examples"] == ["They equated money with success."]


def test_promotion_rejects_pending_or_unapproved_audit():
    pending = _sense(decision="pending")
    with pytest.raises(ValueError, match="not promotion-ready"):
        promote_audit_rows(
            [_audit(semantic_senses=[pending])], [_registry()], audit_sha256=AUDIT_SHA
        )

    repair = _sense(
        decision="repair_proposed", approval="",
        checks={
            "english_semantics": "repair", "vietnamese_semantics": "pass",
            "simplicity": "pass", "example_pos_alignment": "pass",
        },
        proposed={
            "definition_en": "treat as equal", "definition_vi": "coi là ngang nhau",
            "examples": ["They equated money with success."],
        },
    )
    with pytest.raises(ValueError, match="not promotion-ready"):
        promote_audit_rows(
            [_audit(semantic_senses=[repair])], [_registry()], audit_sha256=AUDIT_SHA
        )


def test_validator_requires_exact_active_coverage_and_identity():
    second_registry = _registry(
        guid="guid-2", word="other", cefr="B2", list="Oxford_3000", pos="noun"
    )
    errors = validate_semantic_registry_rows([_promoted()], [_registry(), second_registry])
    assert "missing_active_guid:guid-2" in errors

    wrong = _promoted(pos="noun")
    assert "identity_mismatch:guid-1:pos" in validate_semantic_registry_rows(
        [wrong], [_registry()]
    )

    assert "unknown_registry_guid:guid-1" in validate_semantic_registry_rows(
        [_promoted()], [_registry(status="retired")]
    )


def test_validator_allows_anki_guid_pipe_character():
    guid = "valid|anki-guid"
    assert validate_semantic_registry_rows(
        [_promoted(guid=guid)], [_registry(guid=guid)]
    ) == []


def test_validator_reports_non_object_rows_without_crashing():
    errors = validate_semantic_registry_rows(
        [["not", "an", "object"]],
        [_registry()],
    )

    assert "invalid_row_type" in errors
    assert "missing_active_guid:guid-1" in errors


@pytest.mark.parametrize(
    ("field", "value", "error_prefix"),
    [
        ("definition_en", "bad|split", "invalid_scalar"),
        ("definition_vi", "bad\nline", "invalid_scalar"),
        ("translation_provenance", "source<br>note", "invalid_scalar"),
        ("examples", ["already<br><br>joined"], "invalid_example"),
    ],
)
def test_validator_rejects_embedded_render_separators(field, value, error_prefix):
    sense = _promoted_sense(**{field: value})
    errors = validate_semantic_registry_rows(
        [_promoted(senses=[sense])], [_registry()]
    )
    assert any(error.startswith(error_prefix) for error in errors)


def test_apply_formats_senses_and_preserves_every_other_card_field():
    row = _promoted(senses=[
        _promoted_sense(examples=["First.", "Second."]),
        _promoted_sense(
            semantic_sense_id="sem-2", order=2, definition_en="match",
            definition_vi="tương đương", examples=[],
        ),
    ])
    card = _card()
    updated = apply_semantic_registry([card], [row])[0]
    assert updated.definition == "consider equal (đánh đồng)|match (tương đương)"
    assert updated.definition_vi == "đánh đồng|tương đương"
    assert updated.example == "First.<br><br>Second.|"
    assert updated._replace(
        definition=card.definition,
        definition_vi=card.definition_vi,
        example=card.example,
    ) == card


def test_apply_clears_semantic_fields_for_zero_sense_card():
    updated = apply_semantic_registry([_card()], [_promoted(senses=[])])[0]
    assert updated.definition == ""
    assert updated.definition_vi == ""
    assert updated.example == ""


def test_canonical_semantic_registry_is_the_current_deterministic_promotion():
    paths = ProjectPaths()
    audit_bytes = paths.bilingual_semantic_audit.read_bytes()
    audit_rows = [
        json.loads(line)
        for line in audit_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    card_registry_rows = [
        json.loads(line)
        for line in paths.card_registry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    promoted = promote_audit_rows(
        audit_rows,
        card_registry_rows,
        audit_sha256=hashlib.sha256(audit_bytes).hexdigest(),
    )

    assert paths.semantic_registry.read_text(encoding="utf-8") == (
        serialize_semantic_registry(promoted)
    )
