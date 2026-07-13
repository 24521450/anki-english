"""Generate deterministic Edge TTS media referenced by canonical build artifacts."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.build_contracts import BuildNotesPaths
from src.deck_builder.example_audio import generate_example_audio
from src.deck_builder.registry_build import build_notes_from_registry


def main(argv: list[str] | None = None) -> int:
    paths = ProjectPaths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-jsonl", type=Path, default=paths.oxford_jsonl)
    parser.add_argument("--audio-dir", type=Path, default=paths.audio_dir)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-prune", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    try:
        build_paths = BuildNotesPaths(
            oxford_jsonl_path=args.source_jsonl,
            deck_audit_jsonl_path=paths.deck_audit_jsonl,
            gamma_verdicts_path=paths.gamma_verdicts,
            oxford_3000_md=paths.oxford_3000_md,
            oxford_5000_md=paths.oxford_5000_md,
            awl_md=paths.awl_md,
            audio_dir=args.audio_dir,
            card_registry_path=paths.card_registry,
            manual_cards_path=paths.manual_cards,
            review_overrides_path=paths.non_oxford_non_c2_overrides,
            synonym_example_overrides_path=paths.synonym_example_overrides,
            antonym_example_overrides_path=paths.antonym_example_overrides,
            sense_label_overrides_path=paths.sense_label_overrides,
        )
        cards = build_notes_from_registry(build_paths).built_cards
        report = asyncio.run(generate_example_audio(
            cards,
            args.audio_dir,
            dry_run=args.dry_run,
            concurrency=args.concurrency,
            prune=not args.no_prune,
        ))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(
        f"Example audio: required={report.required} generated={report.generated} "
        f"reused={report.reused} pruned={report.pruned} dry_run={report.dry_run}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
