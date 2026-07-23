"""Scaffold, review, validate, and promote the Collocation Audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.collocation_audit import (
    audit_summary,
    build_audit_rows,
    export_workbook,
    import_workbook,
    load_jsonl,
    promote_audit_rows,
    serialize_audit_rows,
    serialize_registry_rows,
    validate_audit_rows,
    validate_current_audit,
    validate_registry_rows,
)
from src.deck_builder.collocation_audit_manifests import (
    build_artifacts as build_manifest_artifacts,
    validate_artifacts as validate_manifest_artifacts,
)


paths = ProjectPaths()
DEFAULT_AUDIT = paths.collocation_audit
DEFAULT_XLSX = paths.root / "scratch" / "collocation_audit.xlsx"
DEFAULT_MANIFEST_DIR = paths.root / "scratch" / "parallel" / "collocation_manifests"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _scaffold(args) -> int:
    cards = load_jsonl(args.notes)
    registry = load_jsonl(args.registry)
    semantic = load_jsonl(args.semantic_registry)
    oxford = load_jsonl(args.oxford)
    cambridge = load_jsonl(args.cambridge)
    existing = load_jsonl(args.audit) if args.audit.is_file() else []
    rows = build_audit_rows(
        cards,
        registry,
        semantic,
        oxford,
        cambridge,
        existing_rows=existing,
    )
    errors = validate_audit_rows(rows, registry)
    if errors:
        print(
            "Collocation Audit scaffold validation failed:\n"
            + "\n".join(errors[:100]),
            file=sys.stderr,
        )
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_audit_rows(rows))
    print(json.dumps(
        {**audit_summary(rows), "dry_run": args.dry_run},
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


def _validate(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    cards, semantic, oxford, cambridge = _load_current_inputs(args)
    errors = validate_current_audit(
        rows,
        cards,
        registry,
        semantic,
        oxford,
        cambridge,
        require_complete=args.require_complete,
    )
    print(json.dumps(
        {**audit_summary(rows), "errors": len(errors)},
        ensure_ascii=False,
        sort_keys=True,
    ))
    if errors:
        print("\n".join(errors[:100]), file=sys.stderr)
        return 1
    return 0


def _export_xlsx(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    cards, semantic, oxford, cambridge = _load_current_inputs(args)
    errors = validate_current_audit(
        rows, cards, registry, semantic, oxford, cambridge
    )
    if errors:
        print(
            "Collocation Audit export blocked by invalid ledger:\n"
            + "\n".join(errors[:100]),
            file=sys.stderr,
        )
        return 1
    export_workbook(rows, args.xlsx)
    print(args.xlsx)
    return 0


def _import_xlsx(args) -> int:
    rows = load_jsonl(args.audit)
    updated = import_workbook(rows, args.xlsx)
    registry = load_jsonl(args.registry)
    cards, semantic, oxford, cambridge = _load_current_inputs(args)
    errors = validate_current_audit(
        updated, cards, registry, semantic, oxford, cambridge
    )
    if errors:
        print(
            "Collocation Audit workbook validation failed:\n"
            + "\n".join(errors[:100]),
            file=sys.stderr,
        )
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_audit_rows(updated))
    print(json.dumps(
        {**audit_summary(updated), "dry_run": args.dry_run},
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


def _report(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    cards, semantic, oxford, cambridge = _load_current_inputs(args)
    errors = validate_current_audit(
        rows, cards, registry, semantic, oxford, cambridge
    )
    summary = {**audit_summary(rows), "errors": len(errors)}
    lines = [
        "# Collocation Audit",
        "",
        *[f"- {key}: {value}" for key, value in summary.items()],
    ]
    open_rows = [
        row
        for row in rows
        if any(
            item.get("decision") in {"pending", "uncertain"}
            for item in [
                *(row.get("current_items") or []),
                *(row.get("mandatory_candidates") or []),
            ]
        )
    ]
    if open_rows:
        lines.extend([
            "",
            "## Open cards",
            "",
            "| GUID | Word | Current open | Candidate open | Final |",
            "| --- | --- | ---: | ---: | ---: |",
        ])
        for row in open_rows:
            current_open = sum(
                item.get("decision") in {"pending", "uncertain"}
                for item in row.get("current_items") or []
            )
            candidate_open = sum(
                item.get("decision") in {"pending", "uncertain"}
                for item in row.get("mandatory_candidates") or []
            )
            values = (
                row.get("guid") or "",
                row.get("word") or "",
                current_open,
                candidate_open,
                len(row.get("final_items") or []),
            )
            escaped = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
            lines.append("| " + " | ".join(escaped) + " |")
    deltas = []
    exclusions = []
    for row in sorted(rows, key=lambda item: str(item.get("guid") or "")):
        current = {str(item.get("text") or "") for item in row.get("current_items") or []}
        final = {str(item.get("text") or "") for item in row.get("final_items") or []}
        if current != final:
            deltas.append((row.get("guid", ""), row.get("word", ""), sorted(final - current), sorted(current - final)))
        for item in row.get("mandatory_candidates") or []:
            if item.get("decision") == "excluded":
                exclusions.append((row.get("guid", ""), row.get("word", ""), item.get("text", ""), item.get("reason", "")))
    if deltas:
        lines.extend(["", "## Final deltas", "", "| GUID | Word | Added | Removed |", "| --- | --- | --- | --- |"])
        for values in deltas:
            lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in values) + " |")
    if exclusions:
        lines.extend(["", "## Candidate exclusions", "", "| GUID | Word | Candidate | Reason |", "| --- | --- | --- | --- |"])
        for values in exclusions:
            lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in values) + " |")
    qa_rows = sorted(rows, key=lambda item: (str(item.get("word") or "").casefold(), str(item.get("guid") or "")))[:30]
    lines.extend(["", "## Deterministic QA sample", "", "| GUID | Word | Current | Candidates | Final |", "| --- | --- | ---: | ---: | ---: |"])
    for row in qa_rows:
        lines.append(
            f"| {row.get('guid', '')} | {str(row.get('word', '')).replace('|', chr(92) + '|')} | "
            f"{len(row.get('current_items') or [])} | {len(row.get('mandatory_candidates') or [])} | {len(row.get('final_items') or [])} |"
        )
    if errors:
        lines.extend([
            "",
            "## Validation errors",
            "",
            *[f"- {error}" for error in errors],
        ])
    text = "\n".join(lines) + "\n"
    if args.output and not args.dry_run:
        _write_atomic(args.output, text)
    elif not args.output:
        print(text, end="")
    print(json.dumps(
        {**summary, "dry_run": args.dry_run},
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 1 if errors else 0


def _create_manifests(args) -> int:
    audit_bytes = args.audit.read_bytes()
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    created_at = args.created_at or datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    outputs, summary, _ = build_manifest_artifacts(
        audit_bytes, rows, registry, created_at=created_at
    )
    if args.output.exists() and not args.replace:
        summary_path = args.output / "manifest_summary.json"
        if not summary_path.is_file():
            raise RuntimeError("manifest output already exists; use --replace")
        old = json.loads(summary_path.read_text(encoding="utf-8"))
        if old.get("ledger", {}).get("sha256") != summary["ledger"]["sha256"]:
            raise RuntimeError("manifest output belongs to a different ledger; use --replace")
    if not args.dry_run:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, payload in outputs.items():
            _write_atomic(args.output / name, payload.decode("utf-8"))
    print(json.dumps({**summary["queue"], "dry_run": args.dry_run}, sort_keys=True))
    return 0


def _validate_manifests(args) -> int:
    audit_bytes = args.audit.read_bytes()
    errors = validate_manifest_artifacts(
        audit_bytes, load_jsonl(args.audit), load_jsonl(args.registry), args.input
    )
    print(json.dumps({"errors": len(errors), "manifest_dir": str(args.input)}, sort_keys=True))
    if errors:
        print("\n".join(errors[:100]), file=sys.stderr)
        return 1
    return 0


def _promote(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    cards, semantic, oxford, cambridge = _load_current_inputs(args)
    current_errors = validate_current_audit(
        rows,
        cards,
        registry,
        semantic,
        oxford,
        cambridge,
        require_complete=True,
    )
    if current_errors:
        print(
            "Collocation Registry promotion blocked by stale or incomplete audit:\n"
            + "\n".join(current_errors[:100]),
            file=sys.stderr,
        )
        return 1
    promoted = promote_audit_rows(rows, registry)
    errors = validate_registry_rows(promoted, registry, audit_rows=rows)
    if errors:
        print(
            "Collocation Registry promotion validation failed:\n"
            + "\n".join(errors[:100]),
            file=sys.stderr,
        )
        return 1
    serialized = serialize_registry_rows(promoted)
    if not args.dry_run:
        _write_atomic(args.output, serialized)
    print(json.dumps({
        "audit_sha256": hashlib.sha256(
            serialize_audit_rows(rows).encode("utf-8")
        ).hexdigest(),
        "cards": len(promoted),
        "collocation_registry_sha256": hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest(),
        "dry_run": args.dry_run,
        "items": sum(len(row.get("items") or []) for row in promoted),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _load_current_inputs(args) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    return (
        load_jsonl(args.notes),
        load_jsonl(args.semantic_registry),
        load_jsonl(args.oxford),
        load_jsonl(args.cambridge),
    )


def _add_current_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--notes", type=Path, default=paths.anki_notes_jsonl)
    parser.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    parser.add_argument("--oxford", type=Path, default=paths.oxford_jsonl)
    parser.add_argument("--cambridge", type=Path, default=paths.cambridge_jsonl)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--registry", type=Path, default=paths.card_registry)
    sub = parser.add_subparsers(dest="command", required=True)

    scaffold = sub.add_parser("scaffold")
    scaffold.add_argument("--notes", type=Path, default=paths.anki_notes_jsonl)
    scaffold.add_argument(
        "--semantic-registry", type=Path, default=paths.semantic_registry
    )
    scaffold.add_argument("--oxford", type=Path, default=paths.oxford_jsonl)
    scaffold.add_argument("--cambridge", type=Path, default=paths.cambridge_jsonl)
    scaffold.add_argument("--dry-run", action="store_true")
    scaffold.set_defaults(handler=_scaffold)

    validate = sub.add_parser("validate")
    _add_current_input_arguments(validate)
    validate.add_argument("--require-complete", action="store_true")
    validate.set_defaults(handler=_validate)

    export = sub.add_parser("export-xlsx")
    _add_current_input_arguments(export)
    export.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    export.set_defaults(handler=_export_xlsx)

    import_xlsx = sub.add_parser("import-xlsx")
    _add_current_input_arguments(import_xlsx)
    import_xlsx.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    import_xlsx.add_argument("--dry-run", action="store_true")
    import_xlsx.set_defaults(handler=_import_xlsx)

    report = sub.add_parser("report")
    _add_current_input_arguments(report)
    report.add_argument("--output", type=Path)
    report.add_argument("--dry-run", action="store_true")
    report.set_defaults(handler=_report)

    promote = sub.add_parser("promote")
    _add_current_input_arguments(promote)
    promote.add_argument("--output", type=Path, default=paths.collocation_registry)
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

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Collocation Audit {args.command} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
