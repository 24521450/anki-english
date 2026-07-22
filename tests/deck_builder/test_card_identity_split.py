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
