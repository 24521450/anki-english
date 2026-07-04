"""CLI adapter for the registry-driven Anki notes build."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.build_contracts import BuildNotesPaths
from src.deck_builder.build_issues import BuildValidationError
from src.deck_builder.build_publisher import publish_build_result_transactional
from src.deck_builder.build_validation import validate_build_result
from src.deck_builder.registry_build import build_notes_from_registry, load_registry_build_inputs


paths_registry = ProjectPaths()
PROJECT_ROOT = paths_registry.root

JSONL_PATH = paths_registry.oxford_jsonl
GAMMA_VERDICTS_PATH = paths_registry.gamma_verdicts
OUT_JSONL = paths_registry.anki_notes_jsonl
OUT_TXT = paths_registry.anki_notes_txt
OXFORD_3000_MD = paths_registry.oxford_3000_md
OXFORD_5000_MD = paths_registry.oxford_5000_md
AWL_MD = paths_registry.awl_md
AUDIT_JSONL_PATH = paths_registry.deck_audit_jsonl
AUDIO_DIR = paths_registry.audio_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Compute but do not write")
    ap.add_argument("--jsonl", type=Path, default=JSONL_PATH)
    ap.add_argument("--out-jsonl", type=Path, default=OUT_JSONL)
    ap.add_argument("--out-txt", type=Path, default=OUT_TXT)
    ap.add_argument(
        "--txt",
        type=Path,
        default=None,
        help="Deprecated alias for --out-txt; never read as build input",
    )
    ap.add_argument("--gamma", type=Path, default=GAMMA_VERDICTS_PATH)
    ap.add_argument("--card-registry", type=Path, default=paths_registry.card_registry)
    ap.add_argument("--manual-cards", type=Path, default=paths_registry.manual_cards)
    ap.add_argument("--review-overrides", type=Path, default=paths_registry.non_oxford_non_c2_overrides)
    ap.add_argument("--synonym-overrides", type=Path, default=paths_registry.synonym_example_overrides)
    ap.add_argument("--antonym-overrides", type=Path, default=paths_registry.antonym_example_overrides)
    ap.add_argument("--sense-label-overrides", type=Path, default=paths_registry.sense_label_overrides)
    args = ap.parse_args(argv)

    out_txt = args.txt if args.txt is not None else args.out_txt
    if args.txt is not None:
        print(
            "Warning: --txt is deprecated; use --out-txt. It is treated only as an output path.",
            file=sys.stderr,
        )

    if not args.review_overrides.exists():
        print(f"Error: Review overrides file missing: {args.review_overrides}", file=sys.stderr)
        return 1

    paths = BuildNotesPaths(
        oxford_jsonl_path=args.jsonl,
        deck_audit_jsonl_path=AUDIT_JSONL_PATH,
        gamma_verdicts_path=args.gamma,
        oxford_3000_md=OXFORD_3000_MD,
        oxford_5000_md=OXFORD_5000_MD,
        awl_md=AWL_MD,
        audio_dir=AUDIO_DIR,
        card_registry_path=args.card_registry,
        manual_cards_path=args.manual_cards,
        review_overrides_path=args.review_overrides,
        synonym_example_overrides_path=args.synonym_overrides,
        antonym_example_overrides_path=args.antonym_overrides,
        sense_label_overrides_path=args.sense_label_overrides,
    )

    print("=== Loading inputs ===", file=sys.stderr)
    print(f"  audio dir: {paths.audio_dir}", file=sys.stderr)
    print(f"Vocab 3000: {paths.oxford_3000_md.name}", file=sys.stderr)
    print(f"Vocab 5000: {paths.oxford_5000_md.name}", file=sys.stderr)
    print(f"Vocab AWL:   {paths.awl_md.name}", file=sys.stderr)

    try:
        res = build_notes_from_registry(paths)
        registry_inputs = load_registry_build_inputs(args.card_registry, args.manual_cards)
        validation_report = validate_build_result(res, registry_inputs, paths.audio_dir)
    except BuildValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("=== Building cards (registry scope) ===", file=sys.stderr)
    print(f"  Type A (POS fix): {res.type_a_count}", file=sys.stderr)
    print(f"  Type B (lemmatize): {res.type_b_count}", file=sys.stderr)
    print(f"  Type C (drop, no data): {res.type_c_count}", file=sys.stderr)
    print(f"  Dup emit skipped: {res.dup_emit_skip_count}", file=sys.stderr)
    print(f"  UNCLASSIFIED drop: {res.unclassified_drop_count}", file=sys.stderr)
    print(f"  built cards: {res.built_cards_count}", file=sys.stderr)
    print(f"  missing in jsonl: {res.missing_in_jsonl_count}", file=sys.stderr)

    if not validation_report.ok:
        print("Build validation failed:", file=sys.stderr)
        print(validation_report.error_text(), file=sys.stderr)
        return 1

    print(
        f"  validation: OK cards={validation_report.card_count} "
        f"jsonl_sha256={validation_report.jsonl_sha256} txt_sha256={validation_report.txt_sha256}",
        file=sys.stderr,
    )

    if not args.dry_run:
        try:
            publish_report = publish_build_result_transactional(
                res,
                args.out_jsonl,
                out_txt,
                registry_inputs,
                args.card_registry,
                paths.audio_dir,
                paths_registry.build_staging_dir,
            )
        except BuildValidationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            f"Wrote transactionally: {args.out_jsonl} and {out_txt} "
            f"(jsonl_sha256={publish_report.jsonl_sha256}, txt_sha256={publish_report.txt_sha256})",
            file=sys.stderr,
        )

    print("\n=== Quick stats ===", file=sys.stderr)
    print(f"  by cefr: {dict(Counter(c.cefr for c in res.built_cards))}", file=sys.stderr)
    print(f"  by deck: {dict(Counter(c.deck for c in res.built_cards))}", file=sys.stderr)
    print(f"  by source1: {dict(Counter(c.source1 for c in res.built_cards))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
