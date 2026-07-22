from copy import deepcopy
import json

import pytest

from src.config import ProjectPaths
from src.deck_builder.build_contracts import BuiltCard
from src.deck_builder.semantic_registry import (
    SEMANTIC_REGISTRY_SCHEMA_VERSION,
    apply_semantic_registry,
    _render_promoted_audit_rows,
    promote_reviewed_semantics,
    serialize_semantic_registry,
    validate_semantic_registry_rows,
)
from src.deck_builder.idiom_audit import idiom_source_fingerprint
from src.deck_builder.canonical_io import canonical_json_bytes, canonical_jsonl_bytes


AUDIT_SHA = "a" * 64
SOURCE_SHA = "b" * 64
IDIOM_AUDIT_SHA = "c" * 64
VIETNAMESE_REVIEW_SHA = "d" * 64
SEMANTIC_POLICY_SHA = "e" * 64
DEFINITION_REVIEW_SHA = "f" * 64
SENSE_MERGE_REVIEW_SHA = "0" * 64


def _empty_gate_documents() -> dict:
    empty_set_sha = __import__("hashlib").sha256(canonical_json_bytes([])).hexdigest()
    definition_summary = {
        "record_type": "review_summary",
        "schema_version": 3,
        "candidate_count": 0,
        "candidate_set_sha256": empty_set_sha,
    }
    sense_merge_summary = {
        "schema_version": 1,
        "kind": "semantic_sense_merge_review",
        "candidate_set_sha256": empty_set_sha,
        "candidate_cards": 0,
        "input_hashes": {},
    }
    return {
        "policy_rows": [],
        "definition_review_summary": definition_summary,
        "definition_review_rows": [],
        "sense_merge_review_summary": sense_merge_summary,
        "sense_merge_review_rows": [],
        "deck_audit_rows": [],
        "non_oxford_non_c2_override_rows": [],
        "policy_bytes": b"",
        "definition_review_bytes": canonical_jsonl_bytes([definition_summary]),
        "sense_merge_review_bytes": canonical_jsonl_bytes([sense_merge_summary]),
        "deck_audit_bytes": b"",
        "non_oxford_non_c2_override_bytes": b"",
    }


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
        "idiom_audit_sha256": IDIOM_AUDIT_SHA,
        "vietnamese_review_sha256": VIETNAMESE_REVIEW_SHA,
        "semantic_policy_sha256": SEMANTIC_POLICY_SHA,
        "definition_review_sha256": DEFINITION_REVIEW_SHA,
        "sense_merge_review_sha256": SENSE_MERGE_REVIEW_SHA,
        "idioms": [],
    }
    row.update(overrides)
    return row


def _promoted_idiom(**overrides):
    phrase = overrides.pop("phrase_en", "nothing ventured, nothing gained")
    source_explanation = overrides.pop(
        "source_explanation_en", "you must take risks to achieve something"
    )
    examples = overrides.pop("examples", [])
    idiom = {
        "idiom_id": "idm_" + "1" * 24,
        "order": 1,
        "source_fingerprint": idiom_source_fingerprint(
            phrase, source_explanation, examples
        ),
        "phrase_en": phrase,
        "display_mode": "vi_equivalent",
        "explanation_en": source_explanation,
        "explanation_vi": "Không vào hang cọp, sao bắt được cọp con",
        "examples": examples,
        "translation_provenance": "reviewer_derived",
    }
    idiom.update(overrides)
    return idiom


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
    rows = _render_promoted_audit_rows(
        [_audit()], [_registry()], audit_sha256=AUDIT_SHA,
        idiom_audit_sha256=IDIOM_AUDIT_SHA,
        vietnamese_review_sha256=VIETNAMESE_REVIEW_SHA,
        semantic_policy_sha256=SEMANTIC_POLICY_SHA,
        definition_review_sha256=DEFINITION_REVIEW_SHA,
        sense_merge_review_sha256=SENSE_MERGE_REVIEW_SHA,
        idioms_by_guid={},
    )
    assert rows == _render_promoted_audit_rows(
        [_audit()], [_registry()], audit_sha256=AUDIT_SHA,
        idiom_audit_sha256=IDIOM_AUDIT_SHA,
        vietnamese_review_sha256=VIETNAMESE_REVIEW_SHA,
        semantic_policy_sha256=SEMANTIC_POLICY_SHA,
        definition_review_sha256=DEFINITION_REVIEW_SHA,
        sense_merge_review_sha256=SENSE_MERGE_REVIEW_SHA,
        idioms_by_guid={},
    )
    assert rows[0]["senses"] == [_promoted_sense()]
    assert rows[0]["vietnamese_review_sha256"] == VIETNAMESE_REVIEW_SHA
    assert serialize_semantic_registry(rows) == serialize_semantic_registry(deepcopy(rows))
    assert serialize_semantic_registry(rows).endswith("\n")


def test_validator_requires_vietnamese_review_provenance_hash():
    errors = validate_semantic_registry_rows(
        [_promoted(vietnamese_review_sha256="not-a-sha")],
        [_registry()],
    )

    assert "invalid_vietnamese_review_sha256:guid-1" in errors


def test_production_validator_and_apply_reject_legacy_registry_schema():
    legacy = _promoted(schema_version=2)

    assert "invalid_schema_version:guid-1" in validate_semantic_registry_rows(
        [legacy], [_registry()]
    )
    with pytest.raises(ValueError, match="Invalid Semantic Registry"):
        apply_semantic_registry([_card()], [legacy])


def test_public_promotion_requires_the_complete_vietnamese_review_document():
    audit_rows = [_audit()]
    gate_documents = _empty_gate_documents()

    with pytest.raises(ValueError, match="Vietnamese review is not promotion-ready"):
        promote_reviewed_semantics(
            audit_rows,
            [_registry()],
            [],
            {},
            [],
            **gate_documents,
            audit_bytes=canonical_jsonl_bytes(audit_rows),
            idiom_audit_bytes=b"",
            vietnamese_review_bytes=b"{}\n",
        )


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
    rows = _render_promoted_audit_rows(
        [_audit(semantic_senses=[repaired])], [_registry()], audit_sha256=AUDIT_SHA,
        idiom_audit_sha256=IDIOM_AUDIT_SHA,
        vietnamese_review_sha256=VIETNAMESE_REVIEW_SHA,
        semantic_policy_sha256=SEMANTIC_POLICY_SHA,
        definition_review_sha256=DEFINITION_REVIEW_SHA,
        sense_merge_review_sha256=SENSE_MERGE_REVIEW_SHA,
        idioms_by_guid={},
    )
    assert rows[0]["senses"][0]["definition_en"] == "treat as equal"
    assert rows[0]["senses"][0]["definition_vi"] == "coi là ngang nhau"
    assert rows[0]["senses"][0]["examples"] == ["They equated money with success."]


def test_promotion_rejects_pending_or_unapproved_audit():
    pending = _sense(decision="pending")
    with pytest.raises(ValueError, match="not promotion-ready"):
        _render_promoted_audit_rows(
            [_audit(semantic_senses=[pending])], [_registry()], audit_sha256=AUDIT_SHA,
            idiom_audit_sha256=IDIOM_AUDIT_SHA,
            vietnamese_review_sha256=VIETNAMESE_REVIEW_SHA,
            semantic_policy_sha256=SEMANTIC_POLICY_SHA,
            definition_review_sha256=DEFINITION_REVIEW_SHA,
            sense_merge_review_sha256=SENSE_MERGE_REVIEW_SHA,
            idioms_by_guid={},
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
        _render_promoted_audit_rows(
            [_audit(semantic_senses=[repair])], [_registry()], audit_sha256=AUDIT_SHA,
            idiom_audit_sha256=IDIOM_AUDIT_SHA,
            vietnamese_review_sha256=VIETNAMESE_REVIEW_SHA,
            semantic_policy_sha256=SEMANTIC_POLICY_SHA,
            definition_review_sha256=DEFINITION_REVIEW_SHA,
            sense_merge_review_sha256=SENSE_MERGE_REVIEW_SHA,
            idioms_by_guid={},
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


def test_validator_requires_one_main_example_per_distinct_card_pos():
    row = _promoted(
        pos="noun, verb",
        senses=[_promoted_sense(examples=["Only one example."])],
    )

    errors = validate_semantic_registry_rows(
        [row], [_registry(pos="noun, verb")]
    )

    assert "main_example_pos_shortfall:guid-1:1<2" in errors


def test_validator_counts_multiple_examples_in_one_merged_sense():
    row = _promoted(
        pos="noun, verb",
        senses=[_promoted_sense(examples=["First example.", "Second example."])],
    )

    assert validate_semantic_registry_rows(
        [row], [_registry(pos="noun, verb")]
    ) == []


def test_validator_exempts_true_idiom_only_registry_row():
    row = _promoted(
        pos="noun, verb",
        senses=[],
        idioms=[_promoted_idiom()],
    )

    assert validate_semantic_registry_rows(
        [row], [_registry(pos="noun, verb")]
    ) == []


@pytest.mark.parametrize(
    ("field", "value", "location"),
    [
        ("definition_vi", "ngh?a bị lỗi", "sem-1:definition_vi"),
        ("definition_vi", "nghĩa bị \ufffd lỗi", "sem-1:definition_vi"),
        ("explanation_vi", "ho?n toàn", "idm_" + "1" * 24 + ":explanation_vi"),
    ],
)
def test_validator_rejects_suspected_lossy_unicode(field, value, location):
    if field == "explanation_vi":
        row = _promoted(idioms=[_promoted_idiom(**{field: value})])
    else:
        row = _promoted(senses=[_promoted_sense(**{field: value})])

    errors = validate_semantic_registry_rows([row], [_registry()])

    assert f"suspected_lossy_unicode:guid-1:{location}" in errors


def test_validator_allows_terminal_question_punctuation_in_vietnamese():
    row = _promoted(
        senses=[_promoted_sense(definition_vi="Tại sao?")],
        idioms=[_promoted_idiom(explanation_vi="Ai biết?")],
    )

    errors = validate_semantic_registry_rows([row], [_registry()])

    assert not any(error.startswith("suspected_lossy_unicode:") for error in errors)


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
    assert updated.sense_pos == "verb|verb"
    assert updated._replace(
        definition=card.definition,
        definition_vi=card.definition_vi,
        example=card.example,
        sense_pos=card.sense_pos,
    ) == card


def test_apply_derives_each_sense_pos_from_source_ids_in_card_order():
    row = _promoted(
        pos="noun, verb",
        senses=[
            _promoted_sense(source_sense_ids=["cam-verb"]),
            _promoted_sense(
                semantic_sense_id="sem-2",
                order=2,
                source_sense_ids=["cam-verb", "ox-noun"],
            ),
            _promoted_sense(
                semantic_sense_id="sem-3",
                order=3,
                source_sense_ids=["unknown"],
            ),
        ],
    )
    card = _card(pos="noun, verb")

    updated = apply_semantic_registry(
        [card],
        [row],
        {"cam-verb": ("verb",), "ox-noun": ("noun",)},
    )[0]

    assert updated.sense_pos == "verb|noun, verb|noun, verb"


def test_apply_clears_semantic_fields_for_zero_sense_card():
    updated = apply_semantic_registry([_card()], [_promoted(senses=[])])[0]
    assert updated.definition == ""
    assert updated.definition_vi == ""
    assert updated.example == ""
    assert updated.sense_pos == ""


def test_apply_vi_equivalent_keeps_english_fallback_and_emits_only_vi_metadata():
    source_explanation = "you must take risks to achieve something"
    card = _card(
        idioms=f"nothing ventured, nothing gained :: {source_explanation}",
    )
    row = _promoted(idioms=[_promoted_idiom()])

    updated = apply_semantic_registry([card], [row])[0]

    assert updated.idioms == card.idioms
    assert updated.idiom_meaning_vi == (
        "vi_equivalent :: Không vào hang cọp, sao bắt được cọp con"
    )


def test_apply_supports_idiom_only_card():
    source_explanation = "you must take risks to achieve something"
    card = _card(
        definition="",
        definition_vi="",
        example="",
        sense_pos="",
        idioms=f"nothing ventured, nothing gained :: {source_explanation}",
    )

    updated = apply_semantic_registry(
        [card], [_promoted(senses=[], idioms=[_promoted_idiom()])]
    )[0]

    assert updated.definition == updated.definition_vi == updated.example == ""
    assert updated.idioms == card.idioms
    assert updated.idiom_meaning_vi.startswith("vi_equivalent :: ")


def test_apply_bilingual_gloss_preserves_phrase_pipe_examples_and_audio():
    phrase = (
        "shake/rock the foundations of something | "
        "shake/rock something to its foundations"
    )
    source_explanation = "to damage or weaken something very seriously"
    example = "The scandal rocked the institution to its foundations."
    idiom = _promoted_idiom(
        phrase_en=phrase,
        source_explanation_en=source_explanation,
        examples=[example],
        display_mode="bilingual_gloss",
        explanation_en="seriously weaken something at its core",
        explanation_vi="làm lung lay tận gốc",
    )
    card = _card(
        idioms=f"{phrase} :: {source_explanation} :: {example}",
        idiom_example_audio_uk="uk-audio",
        idiom_example_audio_us="us-audio",
    )

    updated = apply_semantic_registry([card], [_promoted(idioms=[idiom])])[0]

    assert updated.idioms == (
        f"{phrase} :: seriously weaken something at its core :: {example}"
    )
    assert updated.idiom_meaning_vi == "bilingual_gloss :: làm lung lay tận gốc"
    assert updated.idiom_example_audio_uk == "uk-audio"
    assert updated.idiom_example_audio_us == "us-audio"


def test_apply_fails_closed_on_stale_or_missing_idiom_payload():
    source = "source explanation"
    card = _card(idioms=f"phrase :: {source}")
    stale = _promoted_idiom(
        phrase_en="phrase",
        source_explanation_en=source,
        source_fingerprint="d" * 64,
        display_mode="bilingual_gloss",
        explanation_en="simple explanation",
        explanation_vi="nghĩa",
    )

    with pytest.raises(ValueError, match="source fingerprint mismatch"):
        apply_semantic_registry([card], [_promoted(idioms=[stale])])
    with pytest.raises(ValueError, match="idiom count mismatch"):
        apply_semantic_registry([card], [_promoted(idioms=[])])


def test_canonical_semantic_registry_is_the_current_deterministic_promotion():
    paths = ProjectPaths()
    audit_bytes = paths.bilingual_semantic_audit.read_bytes()
    idiom_audit_bytes = paths.bilingual_idiom_audit.read_bytes()
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
    idiom_audit_rows = [
        json.loads(line)
        for line in idiom_audit_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    vietnamese_review_bytes = paths.vietnamese_naturalness_review.read_bytes()
    vietnamese_review_rows = [
        json.loads(line)
        for line in vietnamese_review_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    policy_bytes = paths.semantic_policy_locks.read_bytes()
    policy_rows = [
        json.loads(line)
        for line in policy_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    definition_review_bytes = paths.definition_concision_review.read_bytes()
    definition_review_records = [
        json.loads(line)
        for line in definition_review_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    sense_merge_review_bytes = paths.semantic_sense_merge_review.read_bytes()
    sense_merge_review_records = [
        json.loads(line)
        for line in sense_merge_review_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    deck_audit_bytes = paths.deck_audit_jsonl.read_bytes()
    deck_audit_rows = [
        json.loads(line)
        for line in deck_audit_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    override_bytes = paths.non_oxford_non_c2_overrides.read_bytes()
    override_rows = [
        json.loads(line)
        for line in override_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    promoted = promote_reviewed_semantics(
        audit_rows,
        card_registry_rows,
        idiom_audit_rows,
        vietnamese_review_rows[0],
        vietnamese_review_rows[1:],
        policy_rows=policy_rows,
        definition_review_summary=definition_review_records[0],
        definition_review_rows=definition_review_records[1:],
        sense_merge_review_summary=sense_merge_review_records[0],
        sense_merge_review_rows=sense_merge_review_records[1:],
        deck_audit_rows=deck_audit_rows,
        non_oxford_non_c2_override_rows=override_rows,
        audit_bytes=audit_bytes,
        idiom_audit_bytes=idiom_audit_bytes,
        vietnamese_review_bytes=vietnamese_review_bytes,
        policy_bytes=policy_bytes,
        definition_review_bytes=definition_review_bytes,
        sense_merge_review_bytes=sense_merge_review_bytes,
        deck_audit_bytes=deck_audit_bytes,
        non_oxford_non_c2_override_bytes=override_bytes,
    )

    assert paths.semantic_registry.read_text(encoding="utf-8") == (
        serialize_semantic_registry(promoted)
    )
