"""CLI tool to validate sense label prefixes in built Anki notes.

Three audit layers:

Layer 1 — Source audit (data/sources/oxford.jsonl):
  - No definition has a forbidden register conflict pair.
  - Register tags are canonical (REGISTER_LABELS).
  - No definition has duplicate register tags.

Layer 2 — Built-note audit (data/build/anki_notes.jsonl):
  - Every label prefix [tag1, tag2] uses valid canonical labels.
  - No forbidden conflict pairs.
  - No duplicate labels within a single prefix.
  - Correct ordering (register tags before subject domain).

Layer 3 — Source-to-build staleness audit:
  - Verify that the build timestamp is not older than the source timestamp.
  - Report if anki_notes.jsonl may be stale relative to oxford.jsonl.
  Note: full round-trip comparison requires a complete rebuild; staleness check
  is a lightweight proxy. Run `python -m src.pipeline build` to refresh.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.config import ProjectPaths
from src.scraper.oxford_labels import CONFLICT_PAIRS, REGISTER_LABELS, SUBJECT_LABELS
from src.deck_builder.sense_labels import (
    ALL_VALID_LABELS,
    parse_existing_prefix,
)


# ---------------------------------------------------------------------------
# Layer 1: Source audit
# ---------------------------------------------------------------------------

def validate_source_register_tags(
    oxford_jsonl_path: Path | str,
) -> list[str]:
    """Audit data/sources/oxford.jsonl for forbidden register conflicts.

    Checks each definition's register_tags for:
    - Forbidden conflict pairs (formal+informal, formal+slang, approving+disapproving).
    - Non-canonical register tags (not in REGISTER_LABELS).
    - Duplicate register tags on the same definition.

    Returns a list of error messages (empty == pass).
    """
    p = Path(oxford_jsonl_path)
    if not p.exists():
        return [f"Oxford source file not found: {p}"]

    errors: list[str] = []

    with open(p, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = json.loads(line_str)
            except Exception as err:
                errors.append(f"oxford.jsonl line {line_num}: Invalid JSON: {err}")
                continue

            word = rec.get("word", f"<line_{line_num}>")
            for pd in rec.get("pos_data", []):
                pos = pd.get("pos", "?")
                for d in pd.get("definitions", []):
                    sn = d.get("sensenum_local", "?")
                    rt = d.get("register_tags") or []

                    # Duplicate check
                    if len(rt) != len(set(rt)):
                        errors.append(
                            f"Source {word} pos={pos} sn={sn}: "
                            f"Duplicate register tags: {rt}"
                        )

                    # Non-canonical check
                    for tag in rt:
                        if tag not in REGISTER_LABELS:
                            errors.append(
                                f"Source {word} pos={pos} sn={sn}: "
                                f"Non-canonical register tag '{tag}' (not in REGISTER_LABELS)"
                            )

                    # Conflict check
                    rt_set = set(rt)
                    for tag1, tag2 in CONFLICT_PAIRS:
                        if tag1 in rt_set and tag2 in rt_set:
                            errors.append(
                                f"Source {word} pos={pos} sn={sn}: "
                                f"Forbidden conflict '{tag1}' and '{tag2}' in {rt}"
                            )

    return errors


# ---------------------------------------------------------------------------
# Layer 2: Built-note audit (existing logic, now a standalone function)
# ---------------------------------------------------------------------------

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

            guid = rec.get("guid", f"line_{line_num}")
            word = rec.get("word", "<unknown>")
            defn = rec.get("definition", "")

            chunks = [ch.strip() for ch in defn.split("|") if ch.strip()]
            for chunk_idx, chunk in enumerate(chunks, start=1):
                labels, _ = parse_existing_prefix(chunk)
                if not labels:
                    continue

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


# ---------------------------------------------------------------------------
# Layer 3: Source-to-build round-trip audit
# ---------------------------------------------------------------------------

def validate_source_to_build_roundtrip(
    notes_jsonl_path: Path | str,
) -> list[str]:
    """Run production build_notes() in-memory and compare definitions per GUID.

    Verifies that stored anki_notes.jsonl matches a fresh build from the current
    data/sources/oxford.jsonl and overrides. Fails if stored notes are stale,
    labels are lost or corrupted, or overrides hide source definitions incorrectly.
    """
    from src.deck_builder.build_notes import BuildNotesPaths, build_notes

    paths = ProjectPaths()
    build_paths = BuildNotesPaths(
        oxford_jsonl_path=paths.oxford_jsonl,
        notes_txt_path=paths.anki_notes_txt,
        deck_audit_jsonl_path=paths.deck_audit_jsonl,
        gamma_verdicts_path=paths.gamma_verdicts,
        oxford_3000_md=paths.oxford_3000_md,
        oxford_5000_md=paths.oxford_5000_md,
        awl_md=paths.awl_md,
        manual_card_fills_path=paths.manual_card_fills,
        audio_dir=paths.audio_dir,
        review_overrides_path=paths.non_oxford_non_c2_overrides,
        synonym_example_overrides_path=paths.synonym_example_overrides,
        antonym_example_overrides_path=paths.antonym_example_overrides,
        sense_label_overrides_path=paths.sense_label_overrides,
    )

    try:
        fresh_result = build_notes(build_paths)
    except Exception as err:
        return [f"In-memory build_notes() failed: {err}"]

    fresh_map = {c.guid: (c.word, c.definition) for c in fresh_result.built_cards}

    stored_p = Path(notes_jsonl_path)
    if not stored_p.exists():
        return [f"Stored notes file not found: {stored_p}"]

    errors: list[str] = []
    stored_guids = set()

    with open(stored_p, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = json.loads(line_str)
            except Exception as err:
                errors.append(f"Line {line_num}: Invalid JSON: {err}")
                continue

            guid = rec.get("guid")
            word = rec.get("word", "<unknown>")
            stored_def = rec.get("definition", "")
            stored_guids.add(guid)

            if guid not in fresh_map:
                errors.append(f"Stored card {word} ({guid}) not found in fresh build.")
                continue

            fresh_word, fresh_def = fresh_map[guid]
            if stored_def != fresh_def:
                errors.append(
                    f"Card {word} ({guid}): Stored definition in anki_notes.jsonl differs from in-memory build:\n"
                    f"  Stored: {stored_def!r}\n"
                    f"  Fresh:  {fresh_def!r}"
                )

    for g, (w, fdef) in fresh_map.items():
        if g not in stored_guids:
            errors.append(f"Fresh build card {w} ({g}) missing from stored anki_notes.jsonl.")

    return errors


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    paths = ProjectPaths()
    oxford_jsonl = getattr(paths, "oxford_jsonl", None) or Path("data/sources/oxford.jsonl")
    notes_jsonl = paths.anki_notes_jsonl

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Layer 1: Source audit
    print(f"[Layer 1] Auditing source: {oxford_jsonl}...")
    l1_errors = validate_source_register_tags(oxford_jsonl)
    if l1_errors:
        print(f"  [FAIL] {len(l1_errors)} source conflict(s):", file=sys.stderr)
        for err in l1_errors:
            print(f"    - {err}", file=sys.stderr)
        all_errors.extend(l1_errors)
    else:
        print("  [PASS] Source register tags are clean.")

    # Layer 2: Built-note audit
    print(f"[Layer 2] Auditing built notes: {notes_jsonl}...")
    l2_errors = validate_sense_labels_in_notes(notes_jsonl)
    if l2_errors:
        print(f"  [FAIL] {len(l2_errors)} built-note error(s):", file=sys.stderr)
        for err in l2_errors:
            print(f"    - {err}", file=sys.stderr)
        all_errors.extend(l2_errors)
    else:
        print("  [PASS] All sense labels in built notes are valid.")

    # Layer 3: Source-to-build round-trip audit
    print("[Layer 3] Auditing source-to-build round-trip in-memory...")
    l3_errors = validate_source_to_build_roundtrip(notes_jsonl)
    if l3_errors:
        print(f"  [FAIL] {len(l3_errors)} round-trip error(s):", file=sys.stderr)
        for err in l3_errors:
            print(f"    - {err}", file=sys.stderr)
        all_errors.extend(l3_errors)
    else:
        print("  [PASS] Stored notes match fresh in-memory build 100%.")

    if all_errors:
        print(
            f"\n[FAIL] check_sense_labels: {len(all_errors)} error(s).",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n[PASS] check_sense_labels: all 3 layers clean.")


if __name__ == "__main__":
    main()
