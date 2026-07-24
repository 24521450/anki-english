"""Read-only release validation across canonical, package, and import state."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from src.config import ProjectPaths
from src.deck_builder.anki_import_command import validate_local_inputs
from src.deck_builder.collocation_audit import (
    promote_audit_rows,
    serialize_registry_rows as serialize_collocation_registry,
    validate_current_audit,
    validate_registry_rows as validate_collocation_registry,
)
from src.deck_builder.build_contracts import BuildNotesPaths
from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.build_validation import validate_build_result
from src.deck_builder.canonical_io import load_jsonl_document
from src.deck_builder.package_archive import validate_package_archive
from src.deck_builder.package_command import load_eavm_templates
from src.deck_builder.package_provenance import (
    ValidatedPackageProvenance,
    media_file_map,
    package_provenance_inputs,
    provenance_path_for,
    validate_package_provenance,
    validate_verified_import_receipt,
    verified_receipt_path_for,
)
from src.deck_builder.registry_build import (
    build_notes_from_registry,
    load_registry_build_inputs,
)
from src.deck_builder.semantic_registry import (
    promote_reviewed_semantics,
    serialize_semantic_registry,
)
from src.deck_builder.semantic_policy import validate_built_policy
from src.design_css import design_css_in_sync
from src.design_css import load_production_css
from src.scraper.cambridge_english_vietnamese import (
    build_lookup_plan,
    validate_snapshot_rows,
)


RELEASE_GUARD_SCOPES = ("canonical", "package", "import")


class ReleaseGuardError(ValueError):
    """A release authority is incomplete, stale, or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ReleaseGuardReport:
    scope: str
    checks: tuple[str, ...]
    note_count: int


def _load_document(path: Path, label: str) -> tuple[bytes, list[dict]]:
    try:
        payload, rows = load_jsonl_document(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseGuardError(f"could not load {label}: {exc}") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise ReleaseGuardError(f"invalid {label}: every JSONL row must be an object")
    return payload, rows


def _split_summary_document(
    path: Path, label: str
) -> tuple[bytes, dict, list[dict]]:
    payload, rows = _load_document(path, label)
    if not rows:
        raise ReleaseGuardError(f"invalid {label}: missing summary row")
    return payload, rows[0], rows[1:]


def _require_exact_bytes(path: Path, expected: bytes, label: str) -> None:
    try:
        actual = path.read_bytes()
    except OSError as exc:
        raise ReleaseGuardError(f"could not read {label}: {exc}") from exc
    if actual != expected:
        raise ReleaseGuardError(
            f"stale {label}: rerun its canonical writer before release"
        )


def _validate_cambridge_english_vietnamese_source(
    paths: ProjectPaths,
    rows: list[dict],
    card_registry_rows: list[dict],
) -> None:
    schema_path = (
        paths.root
        / "data"
        / "schema"
        / "cambridge_english_vietnamese_record.schema.json"
    )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseGuardError(
            f"could not load Cambridge English–Vietnamese source schema: {exc}"
        ) from exc
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ReleaseGuardError(
            f"invalid Cambridge English–Vietnamese source schema: {exc.message}"
        ) from exc

    validator = Draft202012Validator(schema)
    for row_number, row in enumerate(rows, start=1):
        error = next(validator.iter_errors(row), None)
        if error is not None:
            lookup = row.get("lookup_headword", "<missing>")
            raise ReleaseGuardError(
                "invalid Cambridge English–Vietnamese source "
                f"row {row_number} ({lookup!r}) at {error.json_path}: "
                f"{error.message}"
            )

    try:
        validate_snapshot_rows(
            rows,
            expected_plan=build_lookup_plan(card_registry_rows),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReleaseGuardError(
            f"invalid Cambridge English–Vietnamese source: {exc}"
        ) from exc


def _build_paths(paths: ProjectPaths) -> BuildNotesPaths:
    return BuildNotesPaths(
        oxford_jsonl_path=paths.oxford_jsonl,
        deck_audit_jsonl_path=paths.deck_audit_jsonl,
        gamma_verdicts_path=paths.gamma_verdicts,
        oxford_3000_md=paths.oxford_3000_md,
        oxford_5000_md=paths.oxford_5000_md,
        awl_md=paths.awl_md,
        audio_dir=paths.audio_dir,
        card_registry_path=paths.card_registry,
        manual_cards_path=paths.manual_cards,
        review_overrides_path=paths.non_oxford_non_c2_overrides,
        synonym_example_overrides_path=paths.synonym_example_overrides,
        antonym_example_overrides_path=paths.antonym_example_overrides,
        sense_label_overrides_path=paths.sense_label_overrides,
        semantic_registry_path=paths.semantic_registry,
        collocation_registry_path=paths.collocation_registry,
        cambridge_jsonl_path=paths.cambridge_jsonl,
        pronunciation_selection_locks_path=paths.pronunciation_selection_locks,
        headword_audio_manifest_path=paths.headword_audio_manifest,
    )


def _validate_canonical(paths: ProjectPaths) -> ReleaseGuardReport:
    audit_bytes, audit_rows = _load_document(
        paths.bilingual_semantic_audit, "bilingual semantic audit"
    )
    idiom_bytes, idiom_rows = _load_document(
        paths.bilingual_idiom_audit, "bilingual idiom audit"
    )
    vietnamese_bytes, vietnamese_summary, vietnamese_rows = (
        _split_summary_document(
            paths.vietnamese_naturalness_review,
            "Vietnamese Naturalness Review",
        )
    )
    policy_bytes, policy_rows = _load_document(
        paths.semantic_policy_locks, "semantic policy locks"
    )
    definition_bytes, definition_summary, definition_rows = (
        _split_summary_document(
            paths.definition_concision_review, "Definition review"
        )
    )
    sense_merge_bytes, sense_merge_summary, sense_merge_rows = (
        _split_summary_document(
            paths.semantic_sense_merge_review, "Sense Merge review"
        )
    )
    deck_audit_bytes, deck_audit_rows = _load_document(
        paths.deck_audit_jsonl, "deck audit"
    )
    override_bytes, override_rows = _load_document(
        paths.non_oxford_non_c2_overrides, "non-Oxford/non-C2 overrides"
    )
    _, card_registry_rows = _load_document(paths.card_registry, "Card Registry")
    _, cambridge_english_vietnamese_rows = _load_document(
        paths.cambridge_english_vietnamese_jsonl,
        "Cambridge English–Vietnamese source",
    )
    _validate_cambridge_english_vietnamese_source(
        paths,
        cambridge_english_vietnamese_rows,
        card_registry_rows,
    )
    collocation_audit_bytes, collocation_audit_rows = _load_document(
        paths.collocation_audit, "Collocation Audit"
    )
    _, collocation_registry_rows = _load_document(
        paths.collocation_registry, "Collocation Registry"
    )
    _, oxford_rows = _load_document(paths.oxford_jsonl, "Oxford source")
    _, cambridge_rows = _load_document(paths.cambridge_jsonl, "Cambridge source")

    try:
        promoted = promote_reviewed_semantics(
            audit_rows,
            card_registry_rows,
            idiom_rows,
            vietnamese_summary,
            vietnamese_rows,
            policy_rows=policy_rows,
            definition_review_summary=definition_summary,
            definition_review_rows=definition_rows,
            sense_merge_review_summary=sense_merge_summary,
            sense_merge_review_rows=sense_merge_rows,
            deck_audit_rows=deck_audit_rows,
            non_oxford_non_c2_override_rows=override_rows,
            audit_bytes=audit_bytes,
            idiom_audit_bytes=idiom_bytes,
            vietnamese_review_bytes=vietnamese_bytes,
            policy_bytes=policy_bytes,
            definition_review_bytes=definition_bytes,
            sense_merge_review_bytes=sense_merge_bytes,
            deck_audit_bytes=deck_audit_bytes,
            non_oxford_non_c2_override_bytes=override_bytes,
        )
    except ValueError as exc:
        raise ReleaseGuardError(str(exc)) from exc

    expected_registry = serialize_semantic_registry(promoted).encode("utf-8")
    _require_exact_bytes(
        paths.semantic_registry, expected_registry, "Semantic Registry"
    )

    # The collocation ledger is a separate, fingerprint-bound authority.  It
    # must be checked against the live notes, semantic mappings, and both raw
    # dictionary projections before its deterministic production projection is
    # accepted.  This keeps a stale review from silently surviving a source
    # rebuild.
    try:
        current_note_rows = [
            json.loads(line)
            for line in paths.anki_notes_jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        collocation_errors = validate_current_audit(
            collocation_audit_rows,
            current_note_rows,
            card_registry_rows,
            promoted,
            oxford_rows,
            cambridge_rows,
            require_complete=True,
        )
        if collocation_errors:
            raise ReleaseGuardError(
                "Collocation Audit is stale or incomplete:\n"
                + "\n".join(collocation_errors)
            )
        promoted_collocations = promote_audit_rows(
            collocation_audit_rows, card_registry_rows
        )
        collocation_registry_errors = validate_collocation_registry(
            promoted_collocations,
            card_registry_rows,
            audit_rows=collocation_audit_rows,
        )
        if collocation_registry_errors:
            raise ReleaseGuardError(
                "Collocation Registry promotion is invalid:\n"
                + "\n".join(collocation_registry_errors)
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ReleaseGuardError):
            raise
        raise ReleaseGuardError(str(exc)) from exc
    _require_exact_bytes(
        paths.collocation_registry,
        serialize_collocation_registry(promoted_collocations).encode("utf-8"),
        "Collocation Registry",
    )

    build_paths = _build_paths(paths)
    try:
        result = build_notes_from_registry(build_paths)
        registry_inputs = load_registry_build_inputs(
            paths.card_registry, paths.manual_cards
        )
        validation = validate_build_result(
            result, registry_inputs, paths.audio_dir, validate_audio=True
        )
    except BuildValidationError as exc:
        raise ReleaseGuardError(str(exc)) from exc
    if not validation.ok:
        raise ReleaseGuardError(
            "fresh canonical build is invalid:\n" + validation.error_text()
        )
    built_rows = [
        json.loads(line)
        for line in result.jsonl_text.splitlines()
        if line.strip()
    ]
    policy_errors = validate_built_policy(built_rows, promoted, policy_rows)
    if policy_errors:
        raise ReleaseGuardError(
            "fresh build violates semantic policy:\n"
            + "\n".join(policy_errors)
        )

    _require_exact_bytes(
        paths.anki_notes_jsonl,
        result.jsonl_text.encode("utf-8"),
        "Anki JSONL build artifact",
    )
    _require_exact_bytes(
        paths.anki_notes_txt,
        result.txt_text.encode("utf-8"),
        "Anki TXT build artifact",
    )
    return ReleaseGuardReport(
        scope="canonical",
        checks=(
            "promotion-inputs",
            "cambridge-english-vietnamese-source",
            "semantic-registry-reproduction",
            "collocation-audit-freshness",
            "collocation-registry-reproduction",
            "fresh-build-validation",
            "built-semantic-policy",
            "build-artifact-reproduction",
        ),
        note_count=result.built_cards_count,
    )


def _validate_package(
    paths: ProjectPaths,
    package_path: Path,
    provenance_path: Path,
) -> tuple[ValidatedPackageProvenance, int]:
    design_index = paths.root / "design" / "index.html"
    styling = paths.root / "design" / "EAVM" / "styling.txt"
    try:
        if not design_css_in_sync(design_index, styling):
            raise ReleaseGuardError(
                "design/index.html and packaged EAVM styling are out of sync"
            )
        expected, media = validate_local_inputs(
            package_path, paths.anki_notes_jsonl, paths.audio_dir
        )
        templates = load_eavm_templates(
            paths.root / "design" / "EAVM" / "front_template.txt",
            paths.root / "design" / "EAVM" / "back_template.txt",
            paths.root / "design" / "EAVM" / "production_front_template.txt",
            paths.root / "design" / "EAVM" / "production_answer_prefix.txt",
        )
        archive = validate_package_archive(
            package_path,
            paths.anki_notes_jsonl,
            media_file_map(paths.audio_dir / name for name in media),
            expected_templates=templates,
            expected_css=load_production_css(styling),
        )
        provenance = validate_package_provenance(
            provenance_path,
            package_path,
            package_provenance_inputs(paths),
            media_file_map(paths.audio_dir / name for name in media),
        )
    except ReleaseGuardError:
        raise
    except (OSError, ValueError) as exc:
        raise ReleaseGuardError(str(exc)) from exc
    expected_count = sum(expected.values())
    if archive.note_count != expected_count:
        raise ReleaseGuardError(
            "APKG archive/canonical note count mismatch after validation"
        )
    return provenance, archive.note_count


def run_release_guard(
    paths: ProjectPaths,
    scope: str,
    *,
    package_path: Path | None = None,
    provenance_path: Path | None = None,
    receipt_path: Path | None = None,
) -> ReleaseGuardReport:
    """Validate one release boundary without writing files or contacting Anki."""

    if scope not in RELEASE_GUARD_SCOPES:
        raise ReleaseGuardError(
            f"unknown release-guard scope {scope!r}; expected one of "
            + ", ".join(RELEASE_GUARD_SCOPES)
        )
    if scope == "canonical":
        return _validate_canonical(paths)

    package_path = (package_path or paths.root / "ielts_deck.apkg").resolve()
    provenance_path = (
        provenance_path or provenance_path_for(package_path)
    ).resolve()
    provenance, note_count = _validate_package(
        paths, package_path, provenance_path
    )
    if scope == "package":
        return ReleaseGuardReport(
            scope="package",
            checks=(
                "design-sync",
                "local-package-inputs",
                "package-archive",
                "package-provenance",
            ),
            note_count=note_count,
        )

    receipt_path = (receipt_path or verified_receipt_path_for(package_path)).resolve()
    try:
        validate_verified_import_receipt(
            receipt_path, provenance, expected_count=note_count
        )
    except (OSError, ValueError) as exc:
        raise ReleaseGuardError(str(exc)) from exc
    return ReleaseGuardReport(
        scope="import",
        checks=(
            "design-sync",
            "local-package-inputs",
            "package-archive",
            "package-provenance",
            "verified-import-receipt",
        ),
        note_count=note_count,
    )
