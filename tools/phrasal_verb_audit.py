"""Scaffold and validate the Phrasal Verb Routing Audit."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.phrasal_verb_audit import (
    build_audit_rows,
    export_workbook,
    import_workbook,
    load_jsonl,
    serialize_rows,
    validate_current_audit,
)


paths = ProjectPaths()
DEFAULT_AUDIT = paths.phrasal_verb_routing_audit
DEFAULT_XLSX = paths.root / "scratch" / "phrasal_verb_routing_audit.xlsx"


def _write_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_optional(path: Path | None) -> list[dict]:
    return load_jsonl(path) if path is not None and path.is_file() else []


def _summary(rows: list[dict]) -> dict:
    return {
        "routes": len(rows),
        "pending": sum(row.get("disposition") == "pending" for row in rows),
        "uncertain": sum(row.get("disposition") == "uncertain" for row in rows),
    }


def _scaffold(args) -> int:
    registry = load_jsonl(args.registry)
    oxford = load_jsonl(args.oxford)
    collocations = _load_optional(args.collocation_audit)
    existing = _load_optional(args.audit)
    rows = build_audit_rows(
        registry,
        oxford,
        existing_rows=existing,
        collocation_audit_rows=collocations,
    )
    errors = validate_current_audit(rows, registry, oxford,
                                    collocation_audit_rows=collocations)
    if errors:
        print("Phrasal Verb Routing Audit scaffold failed:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_rows(rows))
    print(json.dumps({**_summary(rows), "dry_run": args.dry_run}, sort_keys=True))
    return 0


def _validate(args) -> int:
    rows = load_jsonl(args.audit)
    errors = validate_current_audit(
        rows, load_jsonl(args.registry), load_jsonl(args.oxford),
        collocation_audit_rows=_load_optional(args.collocation_audit),
        require_complete=args.require_complete,
    )
    print(json.dumps({**_summary(rows), "errors": len(errors)}, sort_keys=True))
    if errors:
        print("\n".join(errors[:100]), file=sys.stderr)
        return 1
    return 0


def _export(args) -> int:
    rows = load_jsonl(args.audit)
    errors = validate_current_audit(rows, load_jsonl(args.registry), load_jsonl(args.oxford),
                                    collocation_audit_rows=_load_optional(args.collocation_audit))
    if errors:
        print("Phrasal Verb Routing Audit export blocked:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    export_workbook(rows, args.xlsx)
    print(args.xlsx)
    return 0


def _import(args) -> int:
    rows = import_workbook(load_jsonl(args.audit), args.xlsx)
    errors = validate_current_audit(rows, load_jsonl(args.registry), load_jsonl(args.oxford),
                                    collocation_audit_rows=_load_optional(args.collocation_audit))
    if errors:
        print("Phrasal Verb Routing Audit workbook rejected:\n" + "\n".join(errors[:100]), file=sys.stderr)
        return 1
    if not args.dry_run:
        _write_atomic(args.audit, serialize_rows(rows))
    print(json.dumps({**_summary(rows), "dry_run": args.dry_run}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--registry", type=Path, default=paths.card_registry)
    parser.add_argument("--oxford", type=Path, default=paths.oxford_jsonl)
    parser.add_argument("--collocation-audit", type=Path, default=paths.collocation_audit)
    sub = parser.add_subparsers(dest="command", required=True)
    scaffold = sub.add_parser("scaffold")
    scaffold.add_argument("--dry-run", action="store_true")
    scaffold.set_defaults(handler=_scaffold)
    validate = sub.add_parser("validate")
    validate.add_argument("--require-complete", action="store_true")
    validate.set_defaults(handler=_validate)
    export = sub.add_parser("export-xlsx")
    export.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    export.set_defaults(handler=_export)
    import_xlsx = sub.add_parser("import-xlsx")
    import_xlsx.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    import_xlsx.add_argument("--dry-run", action="store_true")
    import_xlsx.set_defaults(handler=_import)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Phrasal Verb Routing Audit {args.command} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
