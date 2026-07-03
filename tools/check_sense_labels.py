"""CLI tool to validate sense label prefixes in built Anki notes.

Verifies:
1. Every label prefix `[tag1, tag2]` in definition chunks uses valid canonical labels
   (12 Register Labels or 23 Subject Labels).
2. Label ordering: register tags in source order, followed by subject domain.
3. No forbidden register conflict pairs (formal+informal, formal+slang, approving+disapproving).
4. No duplicate labels within a single prefix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.scraper.oxford_labels import REGISTER_LABELS, SUBJECT_LABELS
from src.deck_builder.sense_labels import (
    ALL_VALID_LABELS,
    CONFLICT_PAIRS,
    parse_existing_prefix,
)


def validate_sense_labels_in_notes(
    notes_jsonl_path: Path | str,
) -> list[str]:
    """Validate sense label prefixes in anki_notes.jsonl.

    Returns a list of error messages.
    """
    p = Path(notes_jsonl_path)
    if not p.exists():
        return [f"Notes file not found: {p}"]

    errors: list[str] = []
    card_count = 0
    labeled_chunk_count = 0

    with open(p, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            try:
                rec = json.loads(line_str)
            except Exception as err:
                errors.append(f"Line {line_num}: Invalid JSON: {err}")
                continue

            card_count += 1
            guid = rec.get("guid", f"line_{line_num}")
            word = rec.get("word", "<unknown>")
            defn = rec.get("definition", "")

            chunks = [ch.strip() for ch in defn.split("|") if ch.strip()]
            for chunk_idx, chunk in enumerate(chunks, start=1):
                labels, _ = parse_existing_prefix(chunk)
                if not labels:
                    continue

                labeled_chunk_count += 1

                # 1. Invalid label check
                for lbl in labels:
                    if lbl not in ALL_VALID_LABELS:
                        errors.append(
                            f"Card {word} ({guid}) chunk {chunk_idx}: "
                            f"Unknown label '{lbl}' in prefix [{', '.join(labels)}]"
                        )

                # 2. Duplicate check
                if len(labels) != len(set(labels)):
                    errors.append(
                        f"Card {word} ({guid}) chunk {chunk_idx}: "
                        f"Duplicate labels in prefix [{', '.join(labels)}]"
                    )

                # 3. Conflict check
                label_set = set(labels)
                for tag1, tag2 in CONFLICT_PAIRS:
                    if tag1 in label_set and tag2 in label_set:
                        errors.append(
                            f"Card {word} ({guid}) chunk {chunk_idx}: "
                            f"Forbidden conflict '{tag1}' and '{tag2}' in [{', '.join(labels)}]"
                        )

                # 4. Ordering check: register_tags first, domain last
                found_domain = False
                for lbl in labels:
                    is_reg = lbl in REGISTER_LABELS
                    is_sub = lbl in SUBJECT_LABELS
                    if is_sub:
                        found_domain = True
                    elif is_reg and found_domain:
                        errors.append(
                            f"Card {word} ({guid}) chunk {chunk_idx}: "
                            f"Register tag '{lbl}' appears after subject domain in [{', '.join(labels)}]"
                        )

    return errors


def main() -> None:
    paths = ProjectPaths()
    notes_jsonl = paths.anki_notes_jsonl

    print(f"Checking sense labels in {notes_jsonl}...")
    errors = validate_sense_labels_in_notes(notes_jsonl)

    if errors:
        print(f"\n[FAIL] Found {len(errors)} sense label validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print("[PASS] All sense labels in built notes are valid!")


if __name__ == "__main__":
    main()
