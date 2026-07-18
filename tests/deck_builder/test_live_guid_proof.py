from __future__ import annotations

from pathlib import Path
import zipfile

import genanki
import pytest

from src.deck_builder.live_guid_proof import (
    LiveGuidProofError,
    export_and_verify_live_guid_map,
    verify_exported_live_guid_map,
)
from src.deck_builder.package_contract import (
    EAVM_FIELD_NAMES,
    EAVM_MODEL_ID,
    EAVM_MODEL_NAME,
)


def _fixture(tmp_path: Path, *, guid: str = "canonical-guid") -> tuple[Path, dict]:
    fields = {name: f"value-{index}" for index, name in enumerate(EAVM_FIELD_NAMES)}
    fields["Word"] = "conquer"
    fields["PartOfSpeech"] = "verb"
    fields["CEFRLevel"] = "C1"
    fields["ProductionAnswer"] = ""
    model = genanki.Model(
        EAVM_MODEL_ID,
        EAVM_MODEL_NAME,
        fields=[{"name": name} for name in EAVM_FIELD_NAMES],
        templates=[{"name": "Recognition", "qfmt": "{{Word}}", "afmt": "{{Back}}"}],
    )
    deck = genanki.Deck(123, "English Academic Vocabulary")
    note = genanki.Note(model=model, fields=[fields[name] for name in EAVM_FIELD_NAMES], guid=guid)
    note.tags = ["Source::Oxford", "CEFR::C1"]
    deck.add_note(note)
    package = tmp_path / "export.apkg"
    genanki.Package(deck).write_to_file(package)
    target = {
        "guid": guid,
        "deck": "English Academic Vocabulary",
        "fields": fields,
        "tags": list(note.tags),
        "production_eligible": False,
    }
    return package, {("conquer", "verb", "C1"): target}


def test_exported_live_guid_map_proves_guid_identity_and_cards(tmp_path: Path) -> None:
    package, expected = _fixture(tmp_path)

    proof = verify_exported_live_guid_map(package, expected)

    assert proof.note_count == 1
    assert proof.card_count == 1
    assert proof.collection_format == "collection.anki2"
    assert len(proof.archive_sha256) == 64
    assert len(proof.guid_map_sha256) == 64
    assert proof.as_receipt_payload()["phase"] == "post_import_export"


def test_exported_live_guid_map_rejects_field_or_guid_mismatch(tmp_path: Path) -> None:
    package, expected = _fixture(tmp_path)
    # Changing the expected GUID without changing the archive must fail closed;
    # this models a swapped/missing live GUID rather than trusting card count.
    expected[ ("conquer", "verb", "C1") ]["guid"] = "different-guid"

    with pytest.raises(LiveGuidProofError, match="unexpected/duplicate GUID"):
        verify_exported_live_guid_map(package, expected)


def test_exported_live_guid_map_rejects_anki21b_without_fallback(tmp_path: Path) -> None:
    package, expected = _fixture(tmp_path)
    replacement = tmp_path / "unsupported.apkg"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(replacement, "w") as target:
        for entry in source.namelist():
            target.writestr(entry, source.read(entry))
        target.writestr("collection.anki21b", b"unsupported")

    with pytest.raises(LiveGuidProofError, match="anki21b"):
        verify_exported_live_guid_map(replacement, expected)


def test_exported_live_guid_map_prefers_anki21_over_compatibility_anki2(
    tmp_path: Path,
) -> None:
    package, expected = _fixture(tmp_path)
    replacement = tmp_path / "modern-export.apkg"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(replacement, "w") as target:
        collection = source.read("collection.anki2")
        for entry in source.namelist():
            target.writestr(entry, source.read(entry))
        target.writestr("collection.anki21", collection)

    proof = verify_exported_live_guid_map(replacement, expected)

    assert proof.collection_format == "collection.anki21"


def test_export_and_verify_uses_post_import_export_boundary(tmp_path: Path) -> None:
    package, expected = _fixture(tmp_path)
    calls: list[tuple[str, dict]] = []

    class Client:
        def call(self, action: str, **params):
            calls.append((action, params))
            Path(params["path"]).write_bytes(package.read_bytes())
            return True

    proof = export_and_verify_live_guid_map(
        Client(), tmp_path, expected,
    )

    assert proof.note_count == 1
    assert calls[0][0] == "exportPackage"
    assert calls[0][1]["deck"] == "English Academic Vocabulary"
    assert calls[0][1]["includeSched"] is True
