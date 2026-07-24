"""Fail-closed provenance for one packaged and verified Anki release."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from src.config import ProjectPaths
from src.deck_builder.canonical_io import canonical_text_sha256
from src.deck_builder.package_contract import packager_contract_payload


PROVENANCE_SCHEMA_VERSION = 3
VERIFIED_IMPORT_RECEIPT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ValidatedPackageProvenance:
    """Canonical package evidence validated against every current input."""

    sha256: str
    package_sha256: str


def package_provenance_inputs(
    project_paths: ProjectPaths | None = None,
    *,
    notes_jsonl: Path | None = None,
    recognition_front: Path | None = None,
    recognition_back: Path | None = None,
    production_front: Path | None = None,
    production_answer_prefix: Path | None = None,
    styling: Path | None = None,
    design_index: Path | None = None,
    packager_contract_source: Path | None = None,
    packager_implementation: Path | None = None,
) -> dict[str, Path]:
    """Return every canonical file whose bytes one APKG release binds."""

    project_paths = project_paths or ProjectPaths()
    design_dir = project_paths.root / "design"
    eavm_dir = design_dir / "EAVM"
    return {
        "notes_jsonl": notes_jsonl or project_paths.anki_notes_jsonl,
        "notes_txt": project_paths.anki_notes_txt,
        "card_registry": project_paths.card_registry,
        "semantic_registry": project_paths.semantic_registry,
        "collocation_registry": project_paths.collocation_registry,
        "cambridge_english_vietnamese_source": (
            project_paths.cambridge_english_vietnamese_jsonl
        ),
        "headword_audio_manifest": project_paths.headword_audio_manifest,
        "bilingual_semantic_audit": project_paths.bilingual_semantic_audit,
        "bilingual_idiom_audit": project_paths.bilingual_idiom_audit,
        "collocation_audit": project_paths.collocation_audit,
        "vietnamese_naturalness_review": (
            project_paths.vietnamese_naturalness_review
        ),
        "semantic_policy_locks": project_paths.semantic_policy_locks,
        "pronunciation_selection_locks": (
            project_paths.pronunciation_selection_locks
        ),
        "definition_concision_review": project_paths.definition_concision_review,
        "semantic_sense_merge_review": (
            project_paths.semantic_sense_merge_review
        ),
        "recognition_front": recognition_front or eavm_dir / "front_template.txt",
        "recognition_back": recognition_back or eavm_dir / "back_template.txt",
        "production_front": (
            production_front or eavm_dir / "production_front_template.txt"
        ),
        "production_answer_prefix": (
            production_answer_prefix
            or eavm_dir / "production_answer_prefix.txt"
        ),
        "styling": styling or eavm_dir / "styling.txt",
        "design_index": design_index or design_dir / "index.html",
        "packager_contract_source": (
            packager_contract_source
            or project_paths.root / "src" / "deck_builder" / "package_contract.py"
        ),
        "packager_implementation": (
            packager_implementation
            or project_paths.root / "src" / "deck_builder" / "package_command.py"
        ),
    }


def provenance_path_for(package_path: Path) -> Path:
    return package_path.parent / "scratch" / "release" / (
        f"{package_path.stem}.provenance.json"
    )


def verified_receipt_path_for(package_path: Path) -> Path:
    return package_path.parent / "scratch" / "release" / (
        f"{package_path.stem}.verified-import.json"
    )


def _sha256_file(path: Path, description: str) -> str:
    if not path.is_file():
        raise ValueError(f"{description} not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_canonical_input(path: Path, description: str) -> str:
    if not path.is_file():
        raise ValueError(f"{description} not found: {path}")
    return canonical_text_sha256(path.read_bytes())


def _canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _media_digest(media_files: Mapping[str, Path]) -> tuple[int, str]:
    digest = hashlib.sha256()
    for filename in sorted(media_files):
        if Path(filename).name != filename:
            raise ValueError(f"invalid provenance media filename: {filename!r}")
        file_sha256 = _sha256_file(
            media_files[filename], f"provenance media {filename!r}"
        )
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha256.encode("ascii"))
        digest.update(b"\n")
    return len(media_files), digest.hexdigest()


def media_file_map(paths: Iterable[Path]) -> dict[str, Path]:
    """Index media by packaged basename and reject ambiguous duplicates."""

    result: dict[str, Path] = {}
    for path in paths:
        path = Path(path)
        filename = path.name
        previous = result.get(filename)
        if previous is not None and previous.resolve() != path.resolve():
            raise ValueError(f"duplicate provenance media filename: {filename!r}")
        result[filename] = path
    return result


def build_package_provenance(
    package_path: Path,
    input_files: Mapping[str, Path],
    media_files: Mapping[str, Path],
) -> dict[str, object]:
    """Build the deterministic evidence payload for one APKG."""

    if not input_files:
        raise ValueError("package provenance requires canonical input files")
    input_hashes = {
        label: _sha256_canonical_input(
            Path(path), f"provenance input {label!r}"
        )
        for label, path in sorted(input_files.items())
    }
    media_count, media_sha256 = _media_digest(media_files)
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "package": {
            "name": package_path.name,
            "sha256": _sha256_file(package_path, "APKG"),
        },
        "packager_contract": packager_contract_payload(),
        "inputs": input_hashes,
        "media": {
            "count": media_count,
            "set_sha256": media_sha256,
        },
    }


def write_package_provenance(
    provenance_path: Path,
    package_path: Path,
    input_files: Mapping[str, Path],
    media_files: Mapping[str, Path],
) -> ValidatedPackageProvenance:
    payload = build_package_provenance(package_path, input_files, media_files)
    raw = _canonical_json_bytes(payload)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = provenance_path.with_suffix(provenance_path.suffix + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(provenance_path)
    package = payload["package"]
    assert isinstance(package, dict)
    return ValidatedPackageProvenance(
        sha256=hashlib.sha256(raw).hexdigest(),
        package_sha256=str(package["sha256"]),
    )


def validate_package_provenance(
    provenance_path: Path,
    package_path: Path,
    input_files: Mapping[str, Path],
    media_files: Mapping[str, Path],
) -> ValidatedPackageProvenance:
    """Recompute every digest and reject missing, stale, or edited evidence."""

    if not provenance_path.is_file():
        raise ValueError(f"package provenance not found: {provenance_path}")
    raw = provenance_path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid package provenance: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid package provenance: expected a JSON object")
    if raw != _canonical_json_bytes(payload):
        raise ValueError("package provenance is not canonical UTF-8 JSON")

    expected = build_package_provenance(package_path, input_files, media_files)
    if payload != expected:
        package = payload.get("package")
        expected_package = expected["package"]
        if package != expected_package:
            raise ValueError("stale package provenance: APKG digest does not match")
        if payload.get("inputs") != expected["inputs"]:
            raise ValueError("stale package provenance: canonical input digest changed")
        if payload.get("packager_contract") != expected["packager_contract"]:
            raise ValueError("stale package provenance: packager contract changed")
        if payload.get("media") != expected["media"]:
            raise ValueError("stale package provenance: media-set digest changed")
        raise ValueError("stale package provenance: unsupported schema or fields")
    package = expected["package"]
    assert isinstance(package, dict)
    return ValidatedPackageProvenance(
        sha256=hashlib.sha256(raw).hexdigest(),
        package_sha256=str(package["sha256"]),
    )


def invalidate_verified_import_receipt(receipt_path: Path) -> None:
    receipt_path.unlink(missing_ok=True)


def write_verified_import_receipt(
    receipt_path: Path,
    provenance: ValidatedPackageProvenance,
    verified_count: int,
    *,
    guid_proof: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> None:
    if verified_count < 0:
        raise ValueError("verified import count cannot be negative")
    if guid_proof is None:
        raise ValueError("verified import receipt requires post-import GUID proof")
    _validate_guid_proof_payload(guid_proof, expected_count=verified_count)
    verified_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payload = {
        "schema_version": VERIFIED_IMPORT_RECEIPT_SCHEMA_VERSION,
        "provenance_sha256": provenance.sha256,
        "package_sha256": provenance.package_sha256,
        "verified_count": verified_count,
        "guid_proof": dict(guid_proof),
        "verified_at": verified_at.isoformat().replace("+00:00", "Z"),
    }
    raw = _canonical_json_bytes(payload)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(receipt_path)


def validate_verified_import_receipt(
    receipt_path: Path,
    provenance: ValidatedPackageProvenance,
    *,
    expected_count: int | None = None,
) -> dict[str, object]:
    """Validate that a canonical receipt belongs to the current package."""

    if not receipt_path.is_file():
        raise ValueError(f"verified-import receipt not found: {receipt_path}")
    raw = receipt_path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid verified-import receipt: {exc}") from exc
    if not isinstance(payload, dict) or raw != _canonical_json_bytes(payload):
        raise ValueError("verified-import receipt is not canonical UTF-8 JSON")
    if set(payload) != {
        "schema_version",
        "provenance_sha256",
        "package_sha256",
        "verified_count",
        "guid_proof",
        "verified_at",
    }:
        raise ValueError("invalid verified-import receipt fields")
    if payload["schema_version"] != VERIFIED_IMPORT_RECEIPT_SCHEMA_VERSION:
        raise ValueError("unsupported verified-import receipt schema")
    if (
        payload["provenance_sha256"] != provenance.sha256
        or payload["package_sha256"] != provenance.package_sha256
    ):
        raise ValueError("stale verified-import receipt")
    verified_count = payload["verified_count"]
    if (
        isinstance(verified_count, bool)
        or not isinstance(verified_count, int)
        or verified_count < 0
        or (expected_count is not None and verified_count != expected_count)
    ):
        raise ValueError("invalid verified-import receipt count")
    _validate_guid_proof_payload(
        payload.get("guid_proof"), expected_count=verified_count
    )
    verified_at = payload["verified_at"]
    if not isinstance(verified_at, str):
        raise ValueError("invalid verified-import receipt timestamp")
    try:
        datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid verified-import receipt timestamp") from exc
    return payload


def _validate_guid_proof_payload(
    proof: object,
    *,
    expected_count: int,
) -> None:
    """Validate the receipt's immutable post-import export evidence."""

    if not isinstance(proof, Mapping):
        raise ValueError("verified-import receipt is missing GUID proof")
    required = {
        "phase",
        "archive_name",
        "archive_sha256",
        "guid_map_sha256",
        "collection_format",
        "note_count",
        "card_count",
    }
    if set(proof) != required:
        raise ValueError("invalid verified-import GUID proof fields")
    if proof.get("phase") != "post_import_export":
        raise ValueError("verified-import GUID proof has an invalid phase")
    archive_name = proof.get("archive_name")
    if (
        not isinstance(archive_name, str)
        or not archive_name
        or Path(archive_name).name != archive_name
    ):
        raise ValueError("verified-import GUID proof archive name is invalid")
    for field in ("archive_sha256", "guid_map_sha256"):
        value = proof.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise ValueError(f"verified-import GUID proof {field} is invalid")
    if proof.get("collection_format") not in {"collection.anki2", "collection.anki21"}:
        raise ValueError("verified-import GUID proof collection format is invalid")
    note_count = proof.get("note_count")
    card_count = proof.get("card_count")
    if (
        isinstance(note_count, bool)
        or not isinstance(note_count, int)
        or note_count != expected_count
        or isinstance(card_count, bool)
        or not isinstance(card_count, int)
        or card_count < note_count
        or card_count > note_count * 2
    ):
        raise ValueError("verified-import GUID proof counts are invalid")
