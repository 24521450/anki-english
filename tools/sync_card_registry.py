#!/usr/bin/env python3
"""Bootstrap, validate, or sync the canonical card registry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.card_registry import (
    bootstrap_registry_rows,
    load_jsonl as load_registry_jsonl,
    serialize_registry_rows,
    validate_registry_or_raise,
)
from src.deck_builder.card_identity import normalize_cefr, normalize_word, normalize_list_name
from src.deck_builder.build_issues import BuildIssue, BuildValidationError
from src.deck_builder.build_support import parse_vocab_list


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_vocab_identities(paths: ProjectPaths) -> set[tuple[str, str, str]]:
    identities: set[tuple[str, str, str]] = set()
    for path, list_name in (
        (paths.oxford_3000_md, "Oxford_3000"),
        (paths.oxford_5000_md, "Oxford_5000"),
        (paths.awl_md, "AWL"),
    ):
        for word, pos, cefr in parse_vocab_list(path):
            identities.add((normalize_word(word).lower(), normalize_cefr(cefr), list_name))
    return identities


def _load_registry_base_identities(registry_path: Path) -> set[tuple[str, str, str]]:
    rows = load_registry_jsonl(registry_path)
    validate_registry_or_raise(rows)
    return {
        (
            normalize_word(row.get("word")).lower(),
            normalize_cefr(row.get("cefr")),
            normalize_list_name(row.get("list"), canonical=True),
        )
        for row in rows
        if row.get("status") == "active"
    }


def _print_issues(prefix: str, issues: list[BuildIssue]) -> None:
    print(prefix, file=sys.stderr)
    for issue in issues[:20]:
        print(f"  - {issue.format()}", file=sys.stderr)
    if len(issues) > 20:
        print(f"  - ... and {len(issues) - 20} more", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="Validate existing registry file only")
    ap.add_argument("--bootstrap-from-build", action="store_true", help="One-shot migration from current build output")
    ap.add_argument("--sync", action="store_true", help="Compare registry identities with corpus vocab identities")
    ap.add_argument("--force", action="store_true", help="Allow overwriting an existing registry during bootstrap")
    defaults = ProjectPaths()
    ap.add_argument("--notes-jsonl", type=Path, default=defaults.anki_notes_jsonl)
    ap.add_argument("--registry", type=Path, default=defaults.card_registry)
    args = ap.parse_args(argv)

    modes = [args.check, args.bootstrap_from_build, args.sync]
    if sum(bool(m) for m in modes) != 1:
        ap.error("choose exactly one of --check, --bootstrap-from-build, or --sync")

    if args.bootstrap_from_build:
        if args.registry.exists() and not args.force:
            print(f"Refusing to overwrite existing registry: {args.registry}", file=sys.stderr)
            return 1
        rows = bootstrap_registry_rows(args.notes_jsonl)
        validate_registry_or_raise(rows)
        canonical_text = serialize_registry_rows(rows)
        args.registry.parent.mkdir(parents=True, exist_ok=True)
        args.registry.write_text(canonical_text, encoding="utf-8")
        print(f"Wrote registry: {args.registry}", file=sys.stderr)
        return 0

    if args.check:
        if not args.registry.exists():
            print(f"Registry file not found: {args.registry}", file=sys.stderr)
            return 1
        rows = load_registry_jsonl(args.registry)
        validate_registry_or_raise(rows)
        print(f"Registry OK: {args.registry}", file=sys.stderr)
        return 0

    if args.sync:
        if not args.registry.exists():
            print(f"Registry file not found: {args.registry}", file=sys.stderr)
            return 1
        registry_identities = _load_registry_base_identities(args.registry)
        vocab_identities = _load_vocab_identities(defaults)
        missing = sorted(vocab_identities - registry_identities)
        orphan = sorted(
            identity for identity in registry_identities - vocab_identities
            if identity[2] != "NO_LIST"
        )
        if missing:
            print(
                f"Registry sync informational: {len(missing)} vocab identities are not in registry",
                file=sys.stderr,
            )
            for identity in missing[:10]:
                print(f"  - missing: {identity}", file=sys.stderr)
            if len(missing) > 10:
                print(f"  - ... and {len(missing) - 10} more", file=sys.stderr)
        if orphan:
            issues: list[BuildIssue] = []
            for word, cefr, list_name in orphan:
                issues.append(BuildIssue(
                    severity="warn",
                    code="orphan_registry_identity",
                    message=f"orphan registry identity {(word, cefr, list_name)} is not in vocab",
                ))
            _print_issues("Registry/vocab sync issues:", issues)
        else:
            print(
                f"Registry sync OK: {len(registry_identities)} registry identities "
                f"vs {len(vocab_identities)} vocab identities",
                file=sys.stderr,
            )
        return 0

    raise AssertionError("unreachable")

if __name__ == "__main__":
    raise SystemExit(main())
