from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import src.deck_builder.card_identity_split as card_identity_split_module
from src.deck_builder.card_identity import is_reviewed_identity_variant_allowed
from src.deck_builder.card_identity_split import (
    CardIdentitySplitError,
    prepare_card_identity_splits,
    publish_card_identity_split,
    recover_card_identity_split_transactions,
    row_sha256,
)
from src.deck_builder.semantic_audit import (
    build_audit_rows,
    semantic_sense_id,
)


PRIMARY_GUID = "guid-old"
SECONDARY_GUID = "newGUID123"
SECONDARY_DECK = (
    "English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses"
)


def _registry() -> dict:
    return {
        "word": "denial",
        "cefr": "C1",
        "list": "Oxford_5000",
        "variant": "",
        "pos": "noun",
        "guid": PRIMARY_GUID,
        "status": "active",
        "deck_override": None,
    }


def _card() -> dict:
    return {
        "guid": PRIMARY_GUID,
        "word": "denial",
        "pos": "noun",
        "cefr": "C1",
        "deck": "English Academic Vocabulary::Oxford::Oxford 5000",
        "definition": "statement that something is untrue (sự phủ nhận)|refusal of a right (sự tước quyền)",
        "definition_vi": "sự phủ nhận|sự tước quyền",
        "example": "a denial of the charge|a denial of freedom",
        "collocations": "issue a denial|in denial",
        "collocation_sources": "cambridge|oxford",
        "idioms": "",
        "tags": "Source::Oxford CEFR::C1 Oxford_5000",
    }


def _oxford() -> list[dict]:
    return [{
        "word": "denial",
        "homonym_index": None,
        "source_files": ["oxford_denial_(noun).html"],
        "oxford_badge": "C1",
        "pos_data": [{
            "pos": "noun",
            "definitions": [
                {
                    "sensenum_local": "1",
                    "text": "a statement that something is not true",
                    "cefr": "C1",
                    "examples": [{"text": "a denial of the charge"}],
                    "register_tags": [],
                    "domain": None,
                },
                {
                    "sensenum_local": "2",
                    "text": "the refusal of a legal right",
                    "cefr": "C1",
                    "examples": [{"text": "a denial of freedom"}],
                    "register_tags": [],
                    "domain": None,
                },
            ],
        }],
    }]


def _reviewed_audit() -> dict:
    row = build_audit_rows([_card()], [_registry()], _oxford())[0]
    for source, sense in zip(row["source_coverage"], row["semantic_senses"]):
        source.update({
            "disposition": "mapped",
            "target_semantic_sense_ids": [sense["semantic_sense_id"]],
            "reason": "Reviewed source mapping.",
        })
        sense["source_sense_ids"] = [source["source_sense_id"]]
        sense["checks"] = {key: "pass" for key in sense["checks"]}
        sense["decision"] = "pass"
        sense["reviewer"] = "reviewer"
        sense["reviewed_at"] = "2026-07-22"
        sense["cambridge"].update({
            "match": "exact",
            "translation_provenance": "reviewer_derived",
        })
    row["coverage"]["status"] = "pass"
    return row


def _bundle(
    registry: dict | None = None,
    audit: dict | None = None,
    card: dict | None = None,
) -> dict:
    registry = registry or _registry()
    audit = audit or _reviewed_audit()
    card = card or _card()
    senses = audit["semantic_senses"]
    sources = audit["source_coverage"]
    return {
        "schema_version": 1,
        "source_guid": PRIMARY_GUID,
        "expected_registry_row_sha256": row_sha256(registry),
        "expected_audit_row_sha256": row_sha256(audit),
        "expected_built_card_sha256": row_sha256(card),
        "expected_source_fingerprint": audit["source_fingerprint"],
        "primary": {
            "variant": "primary",
            "senses": [{
                "from_semantic_sense_ids": [senses[0]["semantic_sense_id"]],
                "retain_semantic_sense_id": senses[0]["semantic_sense_id"],
                "effective": copy.deepcopy(senses[0]["current"]),
            }],
            "collocations": ["issue a denial"],
            "idioms": [],
        },
        "secondary": {
            "guid": SECONDARY_GUID,
            "variant": "secondary_entitlement_psychological",
            "deck_override": SECONDARY_DECK,
            "senses": [{
                "from_semantic_sense_ids": [senses[1]["semantic_sense_id"]],
                "effective": copy.deepcopy(senses[1]["current"]),
            }],
            "collocations": ["in denial"],
            "idioms": [],
        },
        "source_ownership": [
            {
                "source_sense_id": sources[0]["source_sense_id"],
                "primary": {
                    "disposition": "mapped",
                    "target_semantic_sense_ids": [senses[0]["semantic_sense_id"]],
                    "reason": "The statement sense remains on the primary card.",
                },
                "secondary": {
                    "disposition": "excluded",
                    "target_semantic_sense_ids": [],
                    "reason": "This source belongs to the primary Card Identity.",
                },
            },
            {
                "source_sense_id": sources[1]["source_sense_id"],
                "primary": {
                    "disposition": "excluded",
                    "target_semantic_sense_ids": [],
                    "reason": "This source belongs to the secondary Card Identity.",
                },
                "secondary": {
                    "disposition": "mapped",
                    "target_semantic_sense_ids": [senses[1]["semantic_sense_id"]],
                    "reason": "The entitlement sense moves to the secondary card.",
                },
            },
        ],
        "review": {
            "reviewer": "reviewer",
            "reviewed_at": "2026-07-22",
            "approval": "approved",
            "reason": "User approved one primary and one secondary Card Identity.",
        },
    }


def _prepare(bundle: dict | None = None):
    return prepare_card_identity_splits(
        [_registry()],
        [_reviewed_audit()],
        [_card()],
        _oxford(),
        [],
        [bundle or _bundle()],
    )


def test_reviewed_takenote_semantic_variants_are_allowlisted():
    for word, pos in (
        ("denial", "noun"),
        ("alien", "adjective"),
        ("sensitivity", "noun"),
    ):
        assert not is_reviewed_identity_variant_allowed(
            word, "C1", "Oxford_5000", pos, ""
        )
    assert is_reviewed_identity_variant_allowed(
        "denial", "C1", "Oxford_5000", "noun", "primary"
    )
    assert is_reviewed_identity_variant_allowed(
        "denial",
        "C1",
        "Oxford_5000",
        "noun",
        "secondary_entitlement_psychological",
    )
    assert is_reviewed_identity_variant_allowed(
        "alien",
        "C1",
        "Oxford_5000",
        "adjective",
        "secondary_disapproving_space",
    )
    assert is_reviewed_identity_variant_allowed(
        "sensitivity",
        "C1",
        "Oxford_5000",
        "noun",
        "secondary_art_physical",
    )


def test_prepare_split_retains_primary_guid_and_builds_exact_projection():
    prepared = _prepare()

    assert prepared.already_applied is False
    assert [row["guid"] for row in prepared.registry_rows] == [
        PRIMARY_GUID,
        SECONDARY_GUID,
    ]
    assert [row["variant"] for row in prepared.registry_rows] == [
        "primary",
        "secondary_entitlement_psychological",
    ]
    assert [row["guid"] for row in prepared.audit_rows] == [
        PRIMARY_GUID,
        SECONDARY_GUID,
    ]

    old_senses = _reviewed_audit()["semantic_senses"]
    primary_sense = prepared.audit_rows[0]["semantic_senses"][0]
    secondary_sense = prepared.audit_rows[1]["semantic_senses"][0]
    assert primary_sense["semantic_sense_id"] == old_senses[0]["semantic_sense_id"]
    assert secondary_sense["semantic_sense_id"] == semantic_sense_id(
        SECONDARY_GUID,
        1,
        old_senses[1]["current"]["definition_en"],
    )
    assert primary_sense["source_sense_ids"] != secondary_sense["source_sense_ids"]

    assert [row["guid"] for row in prepared.projection_rows] == [
        PRIMARY_GUID,
        SECONDARY_GUID,
    ]
    assert prepared.projection_rows[0]["collocations"] == "issue a denial"
    assert prepared.projection_rows[1]["collocations"] == "in denial"
    assert prepared.projection_rows[1]["deck"] == SECONDARY_DECK


@pytest.mark.parametrize(
    "hash_field",
    [
        "expected_registry_row_sha256",
        "expected_audit_row_sha256",
        "expected_built_card_sha256",
    ],
)
def test_prepare_rejects_stale_expected_row_hash(hash_field: str):
    bundle = _bundle()
    bundle[hash_field] = "0" * 64

    with pytest.raises(CardIdentitySplitError, match="stale_"):
        _prepare(bundle)


def test_prepare_rejects_stale_refreshed_source_context():
    oxford = _oxford()
    oxford[0]["pos_data"][0]["definitions"][0]["text"] = "changed upstream sense"

    with pytest.raises(CardIdentitySplitError, match="stale_source_context"):
        prepare_card_identity_splits(
            [_registry()],
            [_reviewed_audit()],
            [_card()],
            oxford,
            [],
            [_bundle()],
        )


def test_prepare_rejects_partial_sense_or_source_partition():
    bundle = _bundle()
    bundle["secondary"]["senses"] = []
    with pytest.raises(CardIdentitySplitError, match="semantic sense partition"):
        _prepare(bundle)

    bundle = _bundle()
    bundle["source_ownership"].pop()
    with pytest.raises(CardIdentitySplitError, match="source ownership partition"):
        _prepare(bundle)


def test_prepare_rejects_source_mapped_to_both_siblings():
    bundle = _bundle()
    item = bundle["source_ownership"][0]
    item["secondary"] = copy.deepcopy(item["primary"])

    with pytest.raises(CardIdentitySplitError, match="exactly one sibling"):
        _prepare(bundle)


def test_prepare_is_idempotent_for_the_exact_applied_state():
    first = _prepare()
    second = prepare_card_identity_splits(
        first.registry_rows,
        first.audit_rows,
        first.projection_rows,
        _oxford(),
        [],
        [_bundle()],
    )

    assert second.already_applied is True
    assert second.registry_rows == first.registry_rows
    assert second.audit_rows == first.audit_rows
    assert second.projection_rows == first.projection_rows


def _contend_registry() -> dict:
    return {
        **_registry(),
        "word": "contend",
        "pos": "verb",
        "guid": "contend-old",
    }


def _contend_card() -> dict:
    return {
        **_card(),
        "guid": "contend-old",
        "word": "contend",
        "pos": "verb",
        "definition": "say that something is true (quả quyết)",
        "definition_vi": "quả quyết",
        "example": "I contend that the policy is flawed.",
        "production_answer": "contend",
    }


def _contend_oxford() -> list[dict]:
    records = _oxford()
    records[0] = copy.deepcopy(records[0])
    records[0].update({
        "word": "contend",
        "source_files": ["oxford_contend_(verb).html"],
    })
    records[0]["pos_data"][0].update({
        "pos": "verb",
        "definitions": [records[0]["pos_data"][0]["definitions"][0]],
    })
    records[0]["pos_data"][0]["definitions"][0].update({
        "text": "to say that something is true",
        "examples": [{"text": "I contend that the policy is flawed."}],
    })
    target = copy.deepcopy(records[0])
    target.update({
        "word": "contend with",
        "source_files": ["oxford_contend-with_(phrasal_verb).html"],
    })
    target["pos_data"][0].update({
        "pos": "phrasal verb",
        "definitions": [{
            **target["pos_data"][0]["definitions"][0],
            "text": "to have to deal with a problem or difficult situation",
            "examples": [{"text": "She had to contend with major delays."}],
        }],
    })
    return [records[0], target]


def _reviewed_contend_audit() -> dict:
    row = build_audit_rows(
        [_contend_card()], [_contend_registry()], _contend_oxford()
    )[0]
    source = row["source_coverage"][0]
    sense = row["semantic_senses"][0]
    source.update({
        "disposition": "mapped",
        "target_semantic_sense_ids": [sense["semantic_sense_id"]],
        "reason": "Reviewed source mapping.",
    })
    sense["source_sense_ids"] = [source["source_sense_id"]]
    sense["checks"] = {key: "pass" for key in sense["checks"]}
    sense.update({
        "decision": "pass",
        "reviewer": "reviewer",
        "reviewed_at": "2026-07-23",
    })
    sense["cambridge"].update({
        "match": "exact",
        "translation_provenance": "reviewer_derived",
    })
    row["coverage"]["status"] = "pass"
    return row


def _contend_v2_bundle() -> dict:
    registry = _contend_registry()
    card = _contend_card()
    audit = _reviewed_contend_audit()
    old_sense = audit["semantic_senses"][0]
    primary_source = audit["source_coverage"][0]["source_sense_id"]
    secondary_guid = "contendNew"
    secondary_effective = {
        "definition_en": "deal with a problem or difficult situation",
        "definition_vi": "đối phó với",
        "examples": ["She had to contend with major delays."],
    }
    target_registry = {
        **registry,
        "guid": secondary_guid,
        "word": "contend with",
        "pos": "phrasal verb",
        "variant": "secondary_phrasal_contend_with",
    }
    target_card = {
        **card,
        "guid": secondary_guid,
        "word": "contend with",
        "pos": "phrasal verb",
    }
    target_fresh = build_audit_rows(
        [target_card], [target_registry], _contend_oxford(), []
    )[0]
    target_source = target_fresh["coverage"]["candidate_source_sense_ids"][0]
    new_semantic_id = semantic_sense_id(
        secondary_guid, 1, secondary_effective["definition_en"]
    )
    return {
        "schema_version": 2,
        "operation": "extract_secondary_headword",
        "source_guid": registry["guid"],
        "expected_registry_row_sha256": row_sha256(registry),
        "expected_audit_row_sha256": row_sha256(audit),
        "expected_built_card_sha256": row_sha256(card),
        "expected_source_fingerprint": audit["source_fingerprint"],
        "expected_target_source_fingerprint": target_fresh["source_fingerprint"],
        "primary": {
            "variant": "",
            "senses": [{
                "from_semantic_sense_ids": [old_sense["semantic_sense_id"]],
                "retain_semantic_sense_id": old_sense["semantic_sense_id"],
                "effective": copy.deepcopy(old_sense["current"]),
            }],
            "collocations": ["contend that + clause"],
            "idioms": [],
        },
        "secondary": {
            "guid": secondary_guid,
            "word": "contend with sb/sth",
            "source_word": "contend with",
            "pos": "phrasal verb",
            "cefr": "C1",
            "list": "Oxford_5000",
            "variant": "secondary_phrasal_contend_with",
            "deck_override": SECONDARY_DECK,
            "senses": [{
                "from_semantic_sense_ids": [],
                "source_sense_ids": [target_source],
                "effective": secondary_effective,
                "review_reason": "The Oxford phrasal page supplies a distinct learning unit.",
                "cambridge": {
                    "url": "",
                    "match": "missing",
                    "summary": "No separate Cambridge bilingual match was used.",
                    "translation_provenance": "reviewer_derived",
                    "accessed_at": "2026-07-23",
                },
            }],
            "collocations": ["contend with a problem"],
            "idioms": [],
        },
        "source_ownership": [
            {
                "source_sense_id": primary_source,
                "primary": {
                    "disposition": "mapped",
                    "target_semantic_sense_ids": [old_sense["semantic_sense_id"]],
                    "reason": "The base Oxford page remains primary.",
                },
                "secondary": {
                    "disposition": "excluded",
                    "target_semantic_sense_ids": [],
                    "reason": "The base sense is not the phrasal learning unit.",
                },
            },
            {
                "source_sense_id": target_source,
                "primary": {
                    "disposition": "excluded",
                    "target_semantic_sense_ids": [],
                    "reason": "The phrasal page belongs to the secondary card.",
                },
                "secondary": {
                    "disposition": "mapped",
                    "target_semantic_sense_ids": [new_semantic_id],
                    "reason": "The exact Oxford target sense supports this new sense.",
                },
            },
        ],
        "review": {
            "reviewer": "reviewer",
            "reviewed_at": "2026-07-23",
            "approval": "approved",
            "reason": "Reviewed extraction of the different-headword phrasal card.",
        },
    }


def _prepare_contend_v2(bundle: dict | None = None):
    return prepare_card_identity_splits(
        [_contend_registry()],
        [_reviewed_contend_audit()],
        [_contend_card()],
        _contend_oxford(),
        [],
        [bundle or _contend_v2_bundle()],
    )


def test_v2_extracts_different_headword_from_exact_target_page():
    prepared = _prepare_contend_v2()

    assert prepared.registry_rows[0]["guid"] == "contend-old"
    assert prepared.registry_rows[0]["variant"] == ""
    assert prepared.registry_rows[1]["word"] == "contend with sb/sth"
    assert prepared.registry_rows[1]["variant"] == "secondary_phrasal_contend_with"
    secondary_audit = prepared.audit_rows[1]
    assert secondary_audit["word"] == "contend with sb/sth"
    assert secondary_audit["source_senses"][0]["source_files"] == [
        "oxford_contend-with_(phrasal_verb).html"
    ]
    secondary_card = prepared.projection_rows[1]
    assert secondary_card["word"] == "contend with sb/sth"
    assert secondary_card["pos"] == "phrasal verb"
    assert secondary_card["cefr"] == "C1"
    assert secondary_card["production_answer"] == "contend with sb/sth"
    assert secondary_card["deck"] == SECONDARY_DECK


def test_v2_rejects_stale_target_page_fingerprint():
    bundle = _contend_v2_bundle()
    bundle["expected_target_source_fingerprint"] = "0" * 64

    with pytest.raises(CardIdentitySplitError, match="stale_target_source_context"):
        _prepare_contend_v2(bundle)


def test_v2_new_sense_requires_exact_mapped_target_sources():
    bundle = _contend_v2_bundle()
    bundle["secondary"]["senses"][0]["source_sense_ids"] = []

    with pytest.raises(CardIdentitySplitError, match="target_source_sense_ids"):
        _prepare_contend_v2(bundle)


def test_v2_prepare_is_idempotent_for_exact_applied_state():
    first = _prepare_contend_v2()
    second = prepare_card_identity_splits(
        first.registry_rows,
        first.audit_rows,
        first.projection_rows,
        _contend_oxford(),
        [],
        [_contend_v2_bundle()],
    )

    assert second.already_applied is True
    assert second.registry_rows == first.registry_rows
    assert second.audit_rows == first.audit_rows
    assert second.projection_rows == first.projection_rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def test_publish_rolls_back_all_targets_after_injected_failure(tmp_path: Path):
    registry_path = tmp_path / "card_registry.jsonl"
    audit_path = tmp_path / "semantic_audit.jsonl"
    projection_path = tmp_path / "projection.jsonl"
    _write_jsonl(registry_path, [_registry()])
    _write_jsonl(audit_path, [_reviewed_audit()])
    _write_jsonl(projection_path, [_card()])
    before = {
        path: path.read_bytes()
        for path in (registry_path, audit_path, projection_path)
    }

    with pytest.raises(RuntimeError, match="injected fault"):
        publish_card_identity_split(
            _prepare(),
            registry_path,
            audit_path,
            projection_path,
            fault_at="after_audit_replace",
        )

    assert {
        path: path.read_bytes()
        for path in (registry_path, audit_path, projection_path)
    } == before


def test_publish_rejects_document_changed_after_prepare(tmp_path: Path):
    registry_path = tmp_path / "card_registry.jsonl"
    audit_path = tmp_path / "semantic_audit.jsonl"
    projection_path = tmp_path / "projection.jsonl"
    _write_jsonl(registry_path, [_registry()])
    _write_jsonl(audit_path, [_reviewed_audit()])
    prepared = _prepare()

    changed_registry = _registry()
    changed_registry["deck_override"] = "changed concurrently"
    _write_jsonl(registry_path, [changed_registry])
    registry_before = registry_path.read_bytes()
    audit_before = audit_path.read_bytes()

    with pytest.raises(CardIdentitySplitError, match="stale_document_before_publish"):
        publish_card_identity_split(
            prepared,
            registry_path,
            audit_path,
            projection_path,
        )

    assert registry_path.read_bytes() == registry_before
    assert audit_path.read_bytes() == audit_before
    assert not projection_path.exists()


def test_publish_recovers_a_hard_crash_between_replacements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    registry_path = tmp_path / "card_registry.jsonl"
    audit_path = tmp_path / "semantic_audit.jsonl"
    projection_path = tmp_path / "projection.jsonl"
    _write_jsonl(registry_path, [_registry()])
    _write_jsonl(audit_path, [_reviewed_audit()])
    _write_jsonl(projection_path, [_card()])
    before = {
        path: path.read_bytes()
        for path in (registry_path, audit_path, projection_path)
    }

    original_replace = card_identity_split_module.os.replace

    def crash_on_audit(source: str | Path, destination: str | Path):
        if Path(destination).resolve() == audit_path.resolve():
            raise KeyboardInterrupt("simulated process crash")
        return original_replace(source, destination)

    monkeypatch.setattr(card_identity_split_module.os, "replace", crash_on_audit)
    with pytest.raises(KeyboardInterrupt, match="simulated process crash"):
        publish_card_identity_split(
            _prepare(),
            registry_path,
            audit_path,
            projection_path,
        )

    # The process died after the first canonical replacement.  The journal is
    # deliberately left behind for a later invocation to recover.
    assert registry_path.read_bytes() != before[registry_path]
    assert audit_path.read_bytes() == before[audit_path]
    txn_dirs = list(tmp_path.glob(".card_identity_split.txn-*"))
    assert len(txn_dirs) == 1
    assert (txn_dirs[0] / "journal.json").is_file()

    # A fresh process (with no in-memory rollback state) can restore all three
    # authorities and remove the durable transaction.
    recover_card_identity_split_transactions(
        registry_path, audit_path, projection_path
    )
    assert {
        path: path.read_bytes()
        for path in (registry_path, audit_path, projection_path)
    } == before
    assert not list(tmp_path.glob(".card_identity_split.txn-*"))
