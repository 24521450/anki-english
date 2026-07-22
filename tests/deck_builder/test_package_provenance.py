from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from src.config import ProjectPaths
from src.deck_builder.package_provenance import (
    invalidate_verified_import_receipt,
    media_file_map,
    package_provenance_inputs,
    provenance_path_for,
    validate_package_provenance,
    validate_verified_import_receipt,
    verified_receipt_path_for,
    write_package_provenance,
    write_verified_import_receipt,
)


CANONICAL_AUTHORITY_LABELS = (
    "bilingual_semantic_audit",
    "bilingual_idiom_audit",
    "collocation_audit",
    "collocation_registry",
    "vietnamese_naturalness_review",
    "semantic_policy_locks",
    "pronunciation_selection_locks",
    "headword_audio_manifest",
    "definition_concision_review",
    "semantic_sense_merge_review",
)


def _guid_proof(note_count: int, card_count: int | None = None) -> dict[str, object]:
    return {
        "phase": "post_import_export",
        "archive_name": "live_guid_proof_fixture.apkg",
        "archive_sha256": "a" * 64,
        "guid_map_sha256": "b" * 64,
        "collection_format": "collection.anki2",
        "note_count": note_count,
        "card_count": card_count if card_count is not None else note_count,
    }


def _canonical_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs = package_provenance_inputs(ProjectPaths(tmp_path))
    for path in inputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    return inputs


def _release_files(tmp_path: Path):
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    input_file = tmp_path / "notes.jsonl"
    input_file.write_bytes(b'{"guid":"one"}\n')
    media = tmp_path / "clip.mp3"
    media.write_bytes(b"ID3")
    return package, {"notes_jsonl": input_file}, media_file_map([media])


def test_package_provenance_is_canonical_and_validates_current_bytes(tmp_path: Path):
    package, inputs, media = _release_files(tmp_path)
    sidecar = provenance_path_for(package)

    written = write_package_provenance(sidecar, package, inputs, media)
    validated = validate_package_provenance(sidecar, package, inputs, media)

    assert validated == written
    assert sidecar.read_bytes().endswith(b"\n")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert payload["package"]["name"] == "deck.apkg"
    assert payload["media"]["count"] == 1


def test_package_input_hashes_are_stable_across_checkout_newlines(tmp_path: Path):
    package, inputs, media = _release_files(tmp_path)
    sidecar = provenance_path_for(package)
    inputs["notes_jsonl"].write_bytes(b'{"guid":"one"}\r\n')
    write_package_provenance(sidecar, package, inputs, media)

    inputs["notes_jsonl"].write_bytes(b'{"guid":"one"}\n')

    validate_package_provenance(sidecar, package, inputs, media)


def test_shared_input_mapping_binds_every_release_authority(tmp_path: Path):
    paths = ProjectPaths(tmp_path)

    assert package_provenance_inputs(paths) == {
        "notes_jsonl": paths.anki_notes_jsonl,
        "notes_txt": paths.anki_notes_txt,
        "card_registry": paths.card_registry,
        "semantic_registry": paths.semantic_registry,
        "collocation_registry": paths.collocation_registry,
        "headword_audio_manifest": paths.headword_audio_manifest,
        "bilingual_semantic_audit": paths.bilingual_semantic_audit,
        "bilingual_idiom_audit": paths.bilingual_idiom_audit,
        "collocation_audit": paths.collocation_audit,
        "vietnamese_naturalness_review": paths.vietnamese_naturalness_review,
        "semantic_policy_locks": paths.semantic_policy_locks,
        "pronunciation_selection_locks": paths.pronunciation_selection_locks,
        "definition_concision_review": paths.definition_concision_review,
        "semantic_sense_merge_review": paths.semantic_sense_merge_review,
        "recognition_front": paths.root / "design/EAVM/front_template.txt",
        "recognition_back": paths.root / "design/EAVM/back_template.txt",
        "production_front": paths.root / "design/EAVM/production_front_template.txt",
        "production_answer_prefix": paths.root / "design/EAVM/production_answer_prefix.txt",
        "styling": paths.root / "design/EAVM/styling.txt",
        "design_index": paths.root / "design/index.html",
        "packager_contract_source": (
            paths.root / "src/deck_builder/package_contract.py"
        ),
        "packager_implementation": (
            paths.root / "src/deck_builder/package_command.py"
        ),
    }


def test_packager_contract_change_invalidates_an_existing_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package, inputs, media = _release_files(tmp_path)
    sidecar = provenance_path_for(package)
    write_package_provenance(sidecar, package, inputs, media)

    monkeypatch.setattr(
        "src.deck_builder.package_provenance.packager_contract_payload",
        lambda: {"schema_version": 999},
    )

    with pytest.raises(ValueError, match="packager contract changed"):
        validate_package_provenance(sidecar, package, inputs, media)


@pytest.mark.parametrize("ledger_label", CANONICAL_AUTHORITY_LABELS)
def test_changing_any_canonical_authority_invalidates_provenance(
    tmp_path: Path,
    ledger_label: str,
):
    package = tmp_path / "deck.apkg"
    package.write_bytes(b"package")
    media = tmp_path / "clip.mp3"
    media.write_bytes(b"ID3")
    inputs = _canonical_inputs(tmp_path)
    sidecar = provenance_path_for(package)
    write_package_provenance(sidecar, package, inputs, media_file_map([media]))

    inputs[ledger_label].write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical input digest changed"):
        validate_package_provenance(
            sidecar, package, inputs, media_file_map([media])
        )


@pytest.mark.parametrize("changed", ["package", "input", "media"])
def test_package_provenance_rejects_every_stale_digest(
    tmp_path: Path, changed: str,
):
    package, inputs, media = _release_files(tmp_path)
    sidecar = provenance_path_for(package)
    write_package_provenance(sidecar, package, inputs, media)

    if changed == "package":
        package.write_bytes(b"new package")
    elif changed == "input":
        inputs["notes_jsonl"].write_bytes(b'{"guid":"two"}\n')
    else:
        media["clip.mp3"].write_bytes(b"changed ID3")

    with pytest.raises(ValueError, match="stale package provenance"):
        validate_package_provenance(sidecar, package, inputs, media)


def test_verified_receipt_binds_successful_provenance_and_can_be_invalidated(
    tmp_path: Path,
):
    package, inputs, media = _release_files(tmp_path)
    sidecar = provenance_path_for(package)
    provenance = write_package_provenance(sidecar, package, inputs, media)
    receipt = verified_receipt_path_for(package)

    write_verified_import_receipt(
        receipt,
        provenance,
        12,
        guid_proof=_guid_proof(12),
        now=datetime(2026, 7, 18, 1, 2, 3, tzinfo=timezone.utc),
    )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 2,
        "provenance_sha256": provenance.sha256,
        "package_sha256": provenance.package_sha256,
        "verified_count": 12,
        "guid_proof": _guid_proof(12),
        "verified_at": "2026-07-18T01:02:03Z",
    }
    assert validate_verified_import_receipt(
        receipt, provenance, expected_count=12
    ) == payload
    invalidate_verified_import_receipt(receipt)
    assert not receipt.exists()


def test_verified_receipt_rejects_a_different_package_provenance(tmp_path: Path):
    package, inputs, media = _release_files(tmp_path)
    sidecar = provenance_path_for(package)
    provenance = write_package_provenance(sidecar, package, inputs, media)
    receipt = verified_receipt_path_for(package)
    write_verified_import_receipt(
        receipt, provenance, 1, guid_proof=_guid_proof(1)
    )

    package.write_bytes(b"new package")
    new_provenance = write_package_provenance(sidecar, package, inputs, media)

    with pytest.raises(ValueError, match="stale verified-import receipt"):
        validate_verified_import_receipt(receipt, new_provenance)


def test_verified_receipt_requires_post_import_guid_proof(tmp_path: Path):
    package, inputs, media = _release_files(tmp_path)
    sidecar = provenance_path_for(package)
    provenance = write_package_provenance(sidecar, package, inputs, media)
    receipt = verified_receipt_path_for(package)

    with pytest.raises(ValueError, match="requires post-import GUID proof"):
        write_verified_import_receipt(receipt, provenance, 1)

    invalid = _guid_proof(1)
    invalid["phase"] = "pre_import"
    with pytest.raises(ValueError, match="invalid phase"):
        write_verified_import_receipt(
            receipt, provenance, 1, guid_proof=invalid
        )
