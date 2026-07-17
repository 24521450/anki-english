"""Build, review, validate, and exchange the bilingual Idiom Audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.idiom_audit import (
    apply_review_bundle,
    audit_summary,
    build_audit_rows,
    export_workbook,
    import_workbook,
    load_jsonl,
    serialize_jsonl,
    validate_audit_rows,
)


paths = ProjectPaths()
DEFAULT_AUDIT = paths.bilingual_idiom_audit
DEFAULT_XLSX = paths.root / "scratch" / "bilingual_idiom_audit.xlsx"


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
    rows = build_audit_rows(cards, registry)
    errors = validate_audit_rows(rows, registry)
    if errors:
        print("Idiom Audit scaffold validation failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(rows))
    print(json.dumps({**audit_summary(rows), "dry_run": args.dry_run}, ensure_ascii=False, sort_keys=True))
    return 0


def _validate(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(
        rows,
        registry,
        require_complete=args.require_complete,
    )
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
        print("Idiom Audit workbook validation failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(updated))
    print(json.dumps({**audit_summary(updated), "dry_run": args.dry_run}, ensure_ascii=False, sort_keys=True))
    return 0


def _apply_review(args) -> int:
    rows = load_jsonl(args.audit)
    decisions = load_jsonl(args.input)
    updated = apply_review_bundle(rows, decisions)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(updated, registry)
    if errors:
        print("Idiom Audit review-bundle validation failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_jsonl(updated))
    print(json.dumps({**audit_summary(updated), "dry_run": args.dry_run}, ensure_ascii=False, sort_keys=True))
    return 0


def _report(args) -> int:
    rows = load_jsonl(args.audit)
    registry = load_jsonl(args.registry)
    errors = validate_audit_rows(rows, registry)
    summary = {**audit_summary(rows), "errors": len(errors)}
    lines = [
        "# Bilingual Idiom Audit",
        "",
        *[f"- {key}: {value}" for key, value in summary.items()],
    ]
    exceptions = [
        row for row in rows
        if row.get("decision") == "uncertain"
        or row.get("confidence") in {"medium", "low"}
    ]
    if exceptions:
        lines.extend([
            "",
            "## Review exceptions",
            "",
            "| ID | Idiom | Source meaning | Mode | Proposed EN | Proposed VI | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for row in exceptions:
            values = (
                row.get("idiom_id") or "",
                row.get("phrase_en") or "",
                row.get("source_explanation_en") or "",
                row.get("display_mode") or "",
                row.get("explanation_en_simple") or "—",
                row.get("explanation_vi") or "",
                row.get("review_reason") or "",
            )
            escaped = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
            lines.append("| " + " | ".join(escaped) + " |")

    if args.sample_size < 0:
        raise ValueError("sample-size must be non-negative")
    sample_candidates = [
        row for row in rows
        if row.get("decision") == "pass" and row.get("confidence") == "high"
    ]
    sample_candidates.sort(
        key=lambda row: hashlib.sha256(
            str(row.get("idiom_id") or "").encode("utf-8")
        ).hexdigest()
    )
    sample = sample_candidates[:args.sample_size]
    if sample:
        lines.extend([
            "",
            f"## Deterministic high-confidence sample ({len(sample)})",
            "",
            "| ID | Idiom | Source meaning | Mode | Display EN | Display VI |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for row in sample:
            english = (
                "—" if row.get("display_mode") == "vi_equivalent"
                else row.get("explanation_en_simple") or ""
            )
            values = (
                row.get("idiom_id") or "",
                row.get("phrase_en") or "",
                row.get("source_explanation_en") or "",
                row.get("display_mode") or "",
                english,
                row.get("explanation_vi") or "",
            )
            escaped = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
            lines.append("| " + " | ".join(escaped) + " |")
    if errors:
        lines.extend(["", "## Validation errors", "", *[f"- {error}" for error in errors]])
    text = "\n".join(lines) + "\n"
    if args.output and not args.dry_run:
        _write_atomic(args.output, text)
    elif not args.output:
        print(text, end="")
    print(json.dumps({**summary, "dry_run": args.dry_run}, ensure_ascii=False, sort_keys=True))
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--registry", type=Path, default=paths.card_registry)
    sub = parser.add_subparsers(dest="command", required=True)

    scaffold = sub.add_parser("scaffold")
    scaffold.add_argument("--notes", type=Path, default=paths.anki_notes_jsonl)
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

    apply_review = sub.add_parser("apply-review")
    apply_review.add_argument("--input", type=Path, required=True)
    apply_review.add_argument("--dry-run", action="store_true")
    apply_review.set_defaults(handler=_apply_review)

    report = sub.add_parser("report")
    report.add_argument("--output", type=Path)
    report.add_argument("--sample-size", type=int, default=30)
    report.add_argument("--dry-run", action="store_true")
    report.set_defaults(handler=_report)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Idiom Audit {args.command} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
