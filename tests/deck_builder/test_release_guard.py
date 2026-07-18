from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import ProjectPaths
from src.deck_builder import release_guard
from src.deck_builder.package_provenance import (
    media_file_map,
    package_provenance_inputs,
    provenance_path_for,
    verified_receipt_path_for,
    write_package_provenance,
    write_verified_import_receipt,
)
from src.deck_builder.release_guard import ReleaseGuardError, run_release_guard


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


def _canonical_fixture(paths: ProjectPaths) -> tuple[bytes, bytes]:
    _write_jsonl(paths.bilingual_semantic_audit, [{"audit": "row"}])
    _write_jsonl(paths.bilingual_idiom_audit, [{"idiom": "row"}])
    _write_jsonl(
        paths.vietnamese_naturalness_review,
        [{"kind": "summary"}, {"sense": "vi"}],
    )
    _write_jsonl(paths.semantic_policy_locks, [{"lock": "row"}])
    _write_jsonl(
        paths.definition_concision_review,
        [{"kind": "summary"}, {"definition": "row"}],
    )
    _write_jsonl(
        paths.semantic_sense_merge_review,
        [{"kind": "summary"}, {"merge": "row"}],
    )
    _write_jsonl(paths.deck_audit_jsonl, [{"deck": "row"}])
    _write_jsonl(paths.non_oxford_non_c2_overrides, [])
    _write_jsonl(paths.card_registry, [{"guid": "guid-1"}])
    _write_jsonl(paths.semantic_registry, [{"guid": "guid-1"}])

    jsonl_bytes = b'{"guid": "guid-1"}\n'
    txt_bytes = b"header\nrow\n"
    paths.anki_notes_jsonl.parent.mkdir(parents=True, exist_ok=True)
    paths.anki_notes_jsonl.write_bytes(jsonl_bytes)
    paths.anki_notes_txt.write_bytes(txt_bytes)
    return jsonl_bytes, txt_bytes


def test_canonical_scope_reproduces_registry_and_build_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = ProjectPaths(tmp_path)
    jsonl_bytes, txt_bytes = _canonical_fixture(paths)
    calls: list[str] = []

    def fake_promote(*args, **kwargs):
        calls.append("promote")
        assert kwargs["policy_rows"] == [{"lock": "row"}]
        assert kwargs["definition_review_rows"] == [{"definition": "row"}]
        assert kwargs["sense_merge_review_rows"] == [{"merge": "row"}]
        return [{"guid": "guid-1"}]

    result = SimpleNamespace(
        jsonl_text=jsonl_bytes.decode("utf-8"),
        txt_text=txt_bytes.decode("utf-8"),
        built_cards_count=1,
    )
    monkeypatch.setattr(release_guard, "promote_reviewed_semantics", fake_promote)
    monkeypatch.setattr(
        release_guard,
        "build_notes_from_registry",
        lambda paths: calls.append("build") or result,
    )
    monkeypatch.setattr(
        release_guard, "load_registry_build_inputs", lambda *args: object()
    )
    monkeypatch.setattr(
        release_guard,
        "validate_build_result",
        lambda *args, **kwargs: SimpleNamespace(ok=True, error_text=lambda: ""),
    )
    monkeypatch.setattr(release_guard, "validate_built_policy", lambda *args: [])

    report = run_release_guard(paths, "canonical")

    assert calls == ["promote", "build"]
    assert report.note_count == 1
    assert report.checks[-1] == "build-artifact-reproduction"
    assert "built-semantic-policy" in report.checks
    assert paths.semantic_registry.read_bytes() == b'{"guid":"guid-1"}\n'


def test_canonical_scope_rejects_stale_registry_before_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = ProjectPaths(tmp_path)
    _canonical_fixture(paths)
    paths.semantic_registry.write_text("{}\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(
        release_guard,
        "promote_reviewed_semantics",
        lambda *args, **kwargs: [{"guid": "guid-1"}],
    )
    monkeypatch.setattr(
        release_guard,
        "build_notes_from_registry",
        lambda paths: pytest.fail("stale registry must stop before build"),
    )

    with pytest.raises(ReleaseGuardError, match="stale Semantic Registry"):
        run_release_guard(paths, "canonical")


def test_canonical_scope_rejects_a_built_user_lock_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = ProjectPaths(tmp_path)
    jsonl_bytes, txt_bytes = _canonical_fixture(paths)
    monkeypatch.setattr(
        release_guard,
        "promote_reviewed_semantics",
        lambda *args, **kwargs: [{"guid": "guid-1"}],
    )
    monkeypatch.setattr(
        release_guard,
        "build_notes_from_registry",
        lambda paths: SimpleNamespace(
            jsonl_text=jsonl_bytes.decode("utf-8"),
            txt_text=txt_bytes.decode("utf-8"),
            built_cards_count=1,
        ),
    )
    monkeypatch.setattr(
        release_guard, "load_registry_build_inputs", lambda *args: object()
    )
    monkeypatch.setattr(
        release_guard,
        "validate_build_result",
        lambda *args, **kwargs: SimpleNamespace(ok=True, error_text=lambda: ""),
    )
    monkeypatch.setattr(
        release_guard,
        "validate_built_policy",
        lambda *args: ["policy_built_vi_mismatch:exact-vi"],
    )

    with pytest.raises(ReleaseGuardError, match="violates semantic policy"):
        run_release_guard(paths, "canonical")


def _package_fixture(paths: ProjectPaths, note_count: int = 2):
    inputs = package_provenance_inputs(paths)
    for path in inputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8", newline="\n")
    _write_jsonl(
        paths.anki_notes_jsonl,
        [{"guid": f"guid-{index}"} for index in range(note_count)],
    )
    paths.audio_dir.mkdir(parents=True, exist_ok=True)
    package = paths.root / "ielts_deck.apkg"
    package.write_bytes(b"package bytes")
    provenance_path = provenance_path_for(package)
    provenance = write_package_provenance(
        provenance_path,
        package,
        inputs,
        media_file_map([]),
    )
    return package, provenance_path, provenance


def test_package_scope_reuses_current_provenance_and_rejects_stale_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = ProjectPaths(tmp_path)
    package, provenance_path, _ = _package_fixture(paths)
    monkeypatch.setattr(release_guard, "design_css_in_sync", lambda *args: True)
    monkeypatch.setattr(release_guard, "load_eavm_templates", lambda *args: ())
    monkeypatch.setattr(release_guard, "load_production_css", lambda *args: "fixture")
    monkeypatch.setattr(
        release_guard,
        "validate_package_archive",
        lambda *args, **kwargs: SimpleNamespace(note_count=2),
    )

    report = run_release_guard(paths, "package", package_path=package)

    assert report.note_count == 2
    assert report.checks == (
        "design-sync",
        "local-package-inputs",
        "package-archive",
        "package-provenance",
    )

    paths.semantic_policy_locks.write_text(
        "changed\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(ReleaseGuardError, match="canonical input digest changed"):
        run_release_guard(
            paths,
            "package",
            package_path=package,
            provenance_path=provenance_path,
        )


def test_import_scope_requires_receipt_for_current_package_and_note_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = ProjectPaths(tmp_path)
    package, _, provenance = _package_fixture(paths)
    receipt = verified_receipt_path_for(package)
    write_verified_import_receipt(
        receipt, provenance, 2, guid_proof=_guid_proof(2)
    )
    monkeypatch.setattr(release_guard, "design_css_in_sync", lambda *args: True)
    monkeypatch.setattr(release_guard, "load_eavm_templates", lambda *args: ())
    monkeypatch.setattr(release_guard, "load_production_css", lambda *args: "fixture")
    monkeypatch.setattr(
        release_guard,
        "validate_package_archive",
        lambda *args, **kwargs: SimpleNamespace(note_count=2),
    )

    report = run_release_guard(paths, "import", package_path=package)

    assert report.note_count == 2
    assert report.checks[-1] == "verified-import-receipt"

    write_verified_import_receipt(
        receipt, provenance, 1, guid_proof=_guid_proof(1)
    )
    with pytest.raises(ReleaseGuardError, match="receipt count"):
        run_release_guard(paths, "import", package_path=package)


def test_package_scope_rejects_non_apkg_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = ProjectPaths(tmp_path)
    package, _, _ = _package_fixture(paths)
    _write_jsonl(
        paths.anki_notes_jsonl,
        [
            {
                "guid": "guid-1",
                "deck": "English Academic Vocabulary::C1",
                "word": "conquer",
                "tags": "",
            }
        ],
    )
    monkeypatch.setattr(release_guard, "design_css_in_sync", lambda *args: True)
    monkeypatch.setattr(release_guard, "load_eavm_templates", lambda *args: ())
    monkeypatch.setattr(release_guard, "load_production_css", lambda *args: "fixture")

    with pytest.raises(ReleaseGuardError, match="invalid APKG archive"):
        run_release_guard(paths, "package", package_path=package)


def test_release_guard_rejects_unknown_scope(tmp_path: Path) -> None:
    with pytest.raises(ReleaseGuardError, match="unknown release-guard scope"):
        run_release_guard(ProjectPaths(tmp_path), "all")
