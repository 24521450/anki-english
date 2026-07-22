"""Apply a reviewed, fingerprint-bound semantic Card Identity split."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.card_identity_split import (
    CardIdentitySplitError,
    load_jsonl,
    prepare_card_identity_splits,
    publish_card_identity_split,
    recover_card_identity_split_transactions,
    serialize_rows,
)


def _already_applied_candidate(registry_rows: list[dict], reviews: list[dict]) -> bool:
    by_guid = {str(row.get("guid") or ""): row for row in registry_rows}
    return bool(reviews) and all(
        (by_guid.get(str(review.get("source_guid") or "")) or {}).get("variant")
        == "primary"
        and str((review.get("secondary") or {}).get("guid") or "") in by_guid
        for review in reviews
    )


def _sha256(rows: list[dict]) -> str:
    return hashlib.sha256(serialize_rows(rows)).hexdigest()


def _apply_review(args: argparse.Namespace) -> int:
    # Preparation reads all three authorities.  Recover a journal left by a
    # prior process before loading them; otherwise a crash between registry and
    # audit replacement could make preparation reject an otherwise valid
    # review bundle before the publisher gets a chance to recover it.  Dry-run
    # remains strictly read-only.
    if not args.dry_run:
        recover_card_identity_split_transactions(
            args.registry, args.audit, args.projection_output
        )
    reviews = load_jsonl(args.input)
    registry_rows = load_jsonl(args.registry)
    audit_rows = load_jsonl(args.audit)
    notes_path = args.notes
    if (
        _already_applied_candidate(registry_rows, reviews)
        and args.projection_output.is_file()
    ):
        notes_path = args.projection_output
    prepared = prepare_card_identity_splits(
        registry_rows,
        audit_rows,
        load_jsonl(notes_path),
        load_jsonl(args.oxford),
        load_jsonl(args.cambridge),
        reviews,
    )
    if not args.dry_run:
        publish_card_identity_split(
            prepared,
            args.registry,
            args.audit,
            args.projection_output,
        )
    print(json.dumps({
        "already_applied": prepared.already_applied,
        "audit_sha256": _sha256(prepared.audit_rows),
        "cards": len(prepared.projection_rows),
        "dry_run": args.dry_run,
        "projection": str(args.projection_output),
        "projection_sha256": _sha256(prepared.projection_rows),
        "registry_sha256": _sha256(prepared.registry_rows),
        "splits": len(reviews),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    paths = ProjectPaths()
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply_review = subparsers.add_parser("apply-review")
    apply_review.add_argument("--input", type=Path, required=True)
    apply_review.add_argument("--registry", type=Path, default=paths.card_registry)
    apply_review.add_argument(
        "--audit", type=Path, default=paths.bilingual_semantic_audit
    )
    apply_review.add_argument("--notes", type=Path, default=paths.anki_notes_jsonl)
    apply_review.add_argument("--oxford", type=Path, default=paths.oxford_jsonl)
    apply_review.add_argument(
        "--cambridge", type=Path, default=paths.cambridge_jsonl
    )
    apply_review.add_argument(
        "--projection-output",
        type=Path,
        default=paths.root / "scratch" / "card_identity_split_projection.jsonl",
    )
    apply_review.add_argument("--dry-run", action="store_true")
    apply_review.set_defaults(handler=_apply_review)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (CardIdentitySplitError, OSError, RuntimeError) as exc:
        print(f"Card Identity split {args.command} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
