"""Build, review, validate, and exchange the bilingual semantic audit."""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.definition_audit import (
    apply_definition_review_overrides,
    build_definition_audit,
    load_jsonl_bytes as load_definition_jsonl_bytes,
    render_definition_audit_markdown,
    serialize_definition_audit,
    sha256_bytes as definition_sha256_bytes,
)
from src.deck_builder.semantic_audit import (
    audit_summary,
    apply_review_bundle,
    build_audit_rows,
    export_workbook,
    import_workbook,
    load_jsonl,
    serialize_jsonl,
    validate_audit_rows,
)
from src.deck_builder.semantic_audit_manifests import (
    build_artifacts,
    sha256_bytes,
    utc_now,
    validate_artifacts,
)
from src.deck_builder.semantic_registry import (
    promote_audit_rows,
    serialize_semantic_registry,
    validate_semantic_registry_rows,
)


paths = ProjectPaths()
DEFAULT_AUDIT = paths.bilingual_semantic_audit
DEFAULT_XLSX = paths.root / "scratch" / "bilingual_semantic_audit.xlsx"
DEFAULT_MANIFEST_DIR = paths.root / "scratch" / "parallel" / "manifests"
DEFAULT_DEFINITION_AUDIT = paths.root / "scratch" / "definition_sense_audit.jsonl"
DEFAULT_DEFINITION_AUDIT_MARKDOWN = paths.root / "scratch" / "definition_sense_audit.md"
PARALLEL_LOCK = paths.root / "scratch" / "parallel" / ".canonical_ledger.lock"


def _write_atomic(path: Path, text: str) -> None:
    if PARALLEL_LOCK.exists():
        raise RuntimeError(f"canonical ledger write blocked by parallel snapshot lock: {PARALLEL_LOCK}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


@contextmanager
def _parallel_snapshot_lock():
    PARALLEL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(PARALLEL_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"parallel snapshot lock already exists: {PARALLEL_LOCK}") from exc
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "ledger": str(DEFAULT_AUDIT)}).encode("utf-8"))
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        try:
            PARALLEL_LOCK.unlink()
        except FileNotFoundError:
            pass


def _load_audit_bytes(path: Path) -> tuple[bytes, list[dict]]:
    payload = path.read_bytes()
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    return payload, rows


def _write_manifest_outputs(output_dir: Path, outputs: dict[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        target = output_dir / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, target)


def _write_report_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _reject_canonical_report_output(path: Path) -> None:
    target = path.resolve()
    forbidden = (
        (paths.root / "data" / "review").resolve(),
        (paths.root / "data" / "curated").resolve(),
    )
    if any(target == root or target.is_relative_to(root) for root in forbidden):
        raise ValueError(
            f"definition-audit output must stay outside canonical data directories: {target}"
        )


def _scaffold(args) -> int:
    cards = load_jsonl(args.notes)
    registry = load_jsonl(args.registry)
    oxford = load_jsonl(args.oxford)
    cambridge = load_jsonl(args.cambridge)
    rows = build_audit_rows(cards, registry, oxford, cambridge)
    errors = validate_audit_rows(rows, registry)
    if errors:
        print("Scaffold validation failed:\n" + "\n".join(errors[:30]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(rows))
    print(json.dumps(audit_summary(rows), ensure_ascii=False, sort_keys=True))
    return 0


def _validate(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(rows, registry, require_complete=args.require_complete)
    print(json.dumps({**audit_summary(rows), "errors": len(errors)}, ensure_ascii=False, sort_keys=True))
    if errors:
        print("\n".join(errors[:100]), file=sys.stderr)
        return 1
    return 0


def _export_xlsx(args) -> int:
    rows = load_jsonl(args.audit)
    export_workbook(rows, args.xlsx)
    print(args.xlsx)
    return 0


def _import_xlsx(args) -> int:
    rows = load_jsonl(args.audit)
    updated = import_workbook(rows, args.xlsx)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(updated, registry)
    if errors:
        print("Workbook import validation failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(updated))
    print(json.dumps(audit_summary(updated), ensure_ascii=False, sort_keys=True))
    return 0


def _report(args) -> int:
    rows = load_jsonl(args.audit)
    summary = audit_summary(rows)
    lines = ["# Bilingual Semantic Audit", "", *[f"- {key}: {value}" for key, value in summary.items()]]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    else:
        print("\n".join(lines))
    return 0


def _apply_review(args) -> int:
    rows = load_jsonl(args.audit)
    decisions = load_jsonl(args.input)
    updated = apply_review_bundle(rows, decisions)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(updated, registry)
    if errors:
        print("Review bundle validation failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(updated))
    print(json.dumps(audit_summary(updated), ensure_ascii=False, sort_keys=True))
    return 0


def _promote(args) -> int:
    audit_bytes, rows = _load_audit_bytes(args.audit)
    card_registry_rows = load_jsonl(args.registry)
    audit_errors = validate_audit_rows(
        rows,
        card_registry_rows,
        require_complete=True,
    )
    if audit_errors:
        print(
            "Semantic registry promotion blocked by incomplete audit:\n"
            + "\n".join(audit_errors[:100]),
            file=sys.stderr,
        )
        return 1

    audit_sha256 = sha256_bytes(audit_bytes)
    try:
        promoted = promote_audit_rows(
            rows,
            card_registry_rows,
            audit_sha256=audit_sha256,
        )
    except ValueError as exc:
        print(f"Semantic registry promotion failed: {exc}", file=sys.stderr)
        return 1

    registry_errors = validate_semantic_registry_rows(promoted, card_registry_rows)
    if registry_errors:
        print(
            "Semantic registry validation failed:\n"
            + "\n".join(registry_errors[:100]),
            file=sys.stderr,
        )
        return 1

    serialized = serialize_semantic_registry(promoted)
    summary = {
        "audit_sha256": audit_sha256,
        "cards": len(promoted),
        "semantic_registry_sha256": sha256_bytes(serialized.encode("utf-8")),
        "senses": sum(len(row.get("senses") or []) for row in promoted),
    }
    if not args.dry_run:
        _write_atomic(args.output, serialized)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _create_manifests(args) -> int:
    output_dir = args.output
    audit_before = args.audit.read_bytes()
    registry_rows = load_jsonl(args.registry)
    with _parallel_snapshot_lock():
        audit_bytes, rows = _load_audit_bytes(args.audit)
        if audit_bytes != audit_before:
            raise RuntimeError("canonical ledger changed while taking snapshot")
        old_summary_path = output_dir / "manifest_summary.json"
        old_created_at = ""
        if old_summary_path.exists():
            try:
                old_summary = json.loads(old_summary_path.read_text(encoding="utf-8"))
                if old_summary.get("ledger", {}).get("sha256") == sha256_bytes(audit_bytes):
                    old_created_at = str(old_summary.get("created_at") or "")
                elif not args.replace:
                    raise RuntimeError("manifest output belongs to a different ledger; use --replace")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid existing manifest summary: {exc}") from exc
        created_at = args.created_at or old_created_at or utc_now()
        outputs, summary, _ = build_artifacts(
            audit_bytes,
            rows,
            registry_rows,
            scratch_root=paths.root / "scratch",
            created_at=created_at,
        )
        if args.audit.read_bytes() != audit_bytes:
            raise RuntimeError("canonical ledger changed during manifest build")
        if not args.dry_run:
            _write_manifest_outputs(output_dir, outputs)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _validate_manifests(args) -> int:
    audit_bytes, rows = _load_audit_bytes(args.audit)
    registry_rows = load_jsonl(args.registry)
    errors = validate_artifacts(
        audit_bytes,
        rows,
        registry_rows,
        args.input,
        scratch_root=paths.root / "scratch",
    )
    print(json.dumps({"errors": len(errors), "manifest_dir": str(args.input)}, ensure_ascii=False, sort_keys=True))
    if errors:
        print("\n".join(errors[:100]), file=sys.stderr)
        return 1
    return 0


def _definition_audit(args) -> int:
    try:
        _reject_canonical_report_output(args.output)
        _reject_canonical_report_output(args.markdown)
        semantic_bytes, semantic_rows = load_definition_jsonl_bytes(
            args.semantic_registry
        )
        notes_bytes, notes_rows = load_definition_jsonl_bytes(args.notes)
        audit_bytes, audit_rows = load_definition_jsonl_bytes(args.audit)
        card_registry_bytes, card_registry_rows = load_definition_jsonl_bytes(
            args.registry
        )
        summary, candidates = build_definition_audit(
            semantic_rows,
            notes_rows,
            audit_rows,
            card_registry_rows,
            input_hashes={
                "bilingual_semantic_audit": definition_sha256_bytes(audit_bytes),
                "build_notes": definition_sha256_bytes(notes_bytes),
                "card_registry": definition_sha256_bytes(card_registry_bytes),
                "semantic_registry": definition_sha256_bytes(semantic_bytes),
            },
        )
        if args.reviews:
            review_bytes, review_rows = load_definition_jsonl_bytes(args.reviews)
            if not review_rows:
                raise ValueError("definition_review_empty")
            review_summary, review_decisions = review_rows[0], review_rows[1:]
            summary, candidates = apply_definition_review_overrides(
                summary,
                candidates,
                review_summary,
                review_decisions,
                review_sha256=definition_sha256_bytes(review_bytes),
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Definition audit failed: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        _write_report_atomic(
            args.output,
            serialize_definition_audit(summary, candidates),
        )
        _write_report_atomic(
            args.markdown,
            render_definition_audit_markdown(summary, candidates),
        )
    print(json.dumps({
        **summary,
        "output": str(args.output),
        "markdown": str(args.markdown),
        "dry_run": args.dry_run,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--registry", type=Path, default=paths.card_registry)
    sub = parser.add_subparsers(dest="command", required=True)

    scaffold = sub.add_parser("scaffold")
    scaffold.add_argument("--notes", type=Path, default=paths.anki_notes_jsonl)
    scaffold.add_argument("--oxford", type=Path, default=paths.oxford_jsonl)
    scaffold.add_argument("--cambridge", type=Path, default=paths.cambridge_jsonl)
    scaffold.add_argument("--dry-run", action="store_true")
    scaffold.set_defaults(handler=_scaffold)

    validate = sub.add_parser("validate")
    validate.add_argument("--require-complete", action="store_true")
    validate.set_defaults(handler=_validate)

    export = sub.add_parser("export-xlsx")
    export.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    export.set_defaults(handler=_export_xlsx)

    import_xlsx = sub.add_parser("import-xlsx")
    import_xlsx.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    import_xlsx.add_argument("--dry-run", action="store_true")
    import_xlsx.set_defaults(handler=_import_xlsx)

    report = sub.add_parser("report")
    report.add_argument("--output", type=Path)
    report.set_defaults(handler=_report)

    apply_review = sub.add_parser("apply-review")
    apply_review.add_argument("--input", type=Path, required=True)
    apply_review.add_argument("--dry-run", action="store_true")
    apply_review.set_defaults(handler=_apply_review)

    promote = sub.add_parser("promote")
    promote.add_argument("--output", type=Path, default=paths.semantic_registry)
    promote.add_argument("--dry-run", action="store_true")
    promote.set_defaults(handler=_promote)

    create_manifests = sub.add_parser("create-manifests")
    create_manifests.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_DIR)
    create_manifests.add_argument("--created-at")
    create_manifests.add_argument("--replace", action="store_true")
    create_manifests.add_argument("--dry-run", action="store_true")
    create_manifests.set_defaults(handler=_create_manifests)

    validate_manifests = sub.add_parser("validate-manifests")
    validate_manifests.add_argument("--input", type=Path, default=DEFAULT_MANIFEST_DIR)
    validate_manifests.set_defaults(handler=_validate_manifests)

    definition_audit = sub.add_parser("definition-audit")
    definition_audit.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    definition_audit.add_argument(
        "--notes", type=Path, default=paths.anki_notes_jsonl
    )
    definition_audit.add_argument(
        "--output", type=Path, default=DEFAULT_DEFINITION_AUDIT
    )
    definition_audit.add_argument(
        "--markdown", type=Path, default=DEFAULT_DEFINITION_AUDIT_MARKDOWN
    )
    definition_audit.add_argument("--reviews", type=Path)
    definition_audit.add_argument("--dry-run", action="store_true")
    definition_audit.set_defaults(handler=_definition_audit)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
