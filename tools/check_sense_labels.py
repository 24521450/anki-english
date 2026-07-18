"""CLI tool to validate sense label prefixes in built Anki notes.

Four audit layers:

Layer 1 — Source audit (data/sources/oxford.jsonl):
  - No definition has a forbidden register conflict pair.
  - Register tags are canonical (REGISTER_LABELS).
  - No definition has duplicate register tags.

Layer 2 — Built-note audit (data/build/anki_notes.jsonl):
  - Every label prefix [tag1, tag2] uses valid canonical labels.
  - No forbidden conflict pairs.
  - No duplicate labels within a single prefix.
  - Correct ordering (register tags before subject domain).

Layer 3 — Exact-example label completeness:
  - Match built examples to Oxford source examples independently.
  - Require the built prefix to equal the source definition labels.

Layer 4 — Source-to-build round-trip audit:
  - Run the production build in memory and compare every stored definition.
"""
from __future__ import annotations

import json
import re
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
# Layer 3: Independent exact-example label completeness
# ---------------------------------------------------------------------------

def _normalize_example(text: str) -> str:
    normalized = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return " ".join(normalized.lower().split())


def _strip_known_relations(text: str, relation_words: tuple[str, ...]) -> str:
    known = {word.strip().lower() for word in relation_words if word.strip()}
    if not known:
        return text

    def replace_match(match: re.Match[str]) -> str:
        items = [item.strip().lower() for item in match.group(1).split(",") if item.strip()]
        return "" if items and all(item in known for item in items) else match.group(0)

    return re.sub(r"\s+\(([^)]+)\)", replace_match, text)


def validate_exact_example_label_completeness(
    oxford_jsonl_path: Path | str,
    notes_jsonl_path: Path | str,
) -> list[str]:
    """Independently compare built prefixes with exact Oxford examples."""
    source_path = Path(oxford_jsonl_path)
    notes_path = Path(notes_jsonl_path)
    if not source_path.exists():
        return [f"Oxford source file not found: {source_path}"]
    if not notes_path.exists():
        return [f"Notes file not found: {notes_path}"]

    source_specs: dict[tuple[str, str], list[dict]] = {}
    with source_path.open(encoding="utf-8") as source_file:
        for line_num, line in enumerate(source_file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except Exception as err:
                return [f"Oxford source line {line_num}: Invalid JSON: {err}"]
            word = (record.get("word") or "").strip().lower()
            for pos_data in record.get("pos_data") or []:
                pos = (pos_data.get("pos") or "").strip().lower()
                for definition in pos_data.get("definitions") or []:
                    labels = list(dict.fromkeys(definition.get("register_tags") or []))
                    domain = definition.get("domain")
                    if domain and domain not in labels:
                        labels.append(domain)
                    relation_words = tuple(dict.fromkeys(
                        list(definition.get("synonyms") or [])
                        + list(definition.get("antonyms") or [])
                    ))
                    for example in definition.get("examples") or []:
                        example_text = (example.get("text") or "").strip()
                        if example_text:
                            source_specs.setdefault((word, pos), []).append({
                                "example": example_text,
                                "labels": tuple(labels),
                                "relation_words": relation_words,
                            })

    errors: list[str] = []
    with notes_path.open(encoding="utf-8") as notes_file:
        for line_num, line in enumerate(notes_file, start=1):
            if not line.strip():
                continue
            try:
                card = json.loads(line)
            except Exception as err:
                errors.append(f"Notes line {line_num}: Invalid JSON: {err}")
                continue

            word = (card.get("word") or "").split(" (")[0].strip().lower()
            positions = [
                part.strip().lower()
                for part in (card.get("pos") or "").split(",")
                if part.strip()
            ]
            definitions = (card.get("definition") or "").split("|")
            examples = (card.get("example") or "").split("|")

            for chunk_index, (definition, example) in enumerate(
                zip(definitions, examples), start=1
            ):
                matching_labels: list[tuple[str, ...]] = []
                for pos in positions:
                    for spec in source_specs.get((word, pos), []):
                        cleaned = _strip_known_relations(example, spec["relation_words"])
                        if _normalize_example(cleaned) == _normalize_example(spec["example"]):
                            matching_labels.append(spec["labels"])

                if not matching_labels:
                    continue
                distinct_sets = {frozenset(labels) for labels in matching_labels}
                if len(distinct_sets) > 1:
                    errors.append(
                        f"Card {card.get('word')} ({card.get('guid')}) chunk {chunk_index}: "
                        f"exact source example has ambiguous label sets "
                        f"{sorted(sorted(labels) for labels in distinct_sets)}"
                    )
                    continue

                expected = matching_labels[0]
                actual, _ = parse_existing_prefix(definition.strip())
                if tuple(actual) != expected:
                    errors.append(
                        f"Card {card.get('word')} ({card.get('guid')}) chunk {chunk_index}: "
                        f"expected exact-source labels {list(expected)}, found {actual}"
                    )

    return errors


# ---------------------------------------------------------------------------
# Layer 4: Source-to-build round-trip audit
# ---------------------------------------------------------------------------

def validate_source_to_build_roundtrip(
    notes_jsonl_path: Path | str,
) -> list[str]:
    """Run production build_notes() in-memory and compare definitions per GUID.

    Verifies that stored anki_notes.jsonl matches a fresh build from the current
    data/sources/oxford.jsonl and overrides. Fails if stored notes are stale,
    labels are lost or corrupted, or overrides hide source definitions incorrectly.
    """
    from src.deck_builder.build_contracts import BuildNotesPaths
    from src.deck_builder.registry_build import build_notes_from_registry

    paths = ProjectPaths()
    build_paths = BuildNotesPaths(
        oxford_jsonl_path=paths.oxford_jsonl,
        deck_audit_jsonl_path=paths.deck_audit_jsonl,
        gamma_verdicts_path=paths.gamma_verdicts,
        oxford_3000_md=paths.oxford_3000_md,
        oxford_5000_md=paths.oxford_5000_md,
        awl_md=paths.awl_md,
        audio_dir=paths.audio_dir,
        card_registry_path=paths.card_registry,
        manual_cards_path=paths.manual_cards,
        review_overrides_path=paths.non_oxford_non_c2_overrides,
        synonym_example_overrides_path=paths.synonym_example_overrides,
        antonym_example_overrides_path=paths.antonym_example_overrides,
        sense_label_overrides_path=paths.sense_label_overrides,
        semantic_registry_path=paths.semantic_registry,
        collocation_registry_path=paths.collocation_registry,
        cambridge_jsonl_path=paths.cambridge_jsonl,
    )

    try:
        fresh_result = build_notes_from_registry(build_paths)
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

    # Layer 3: independent exact-example completeness audit
    print("[Layer 3] Auditing exact-example label completeness...")
    l3_errors = validate_exact_example_label_completeness(oxford_jsonl, notes_jsonl)
    if l3_errors:
        print(f"  [FAIL] {len(l3_errors)} completeness error(s):", file=sys.stderr)
        for err in l3_errors:
            print(f"    - {err}", file=sys.stderr)
        all_errors.extend(l3_errors)
    else:
        print("  [PASS] Exact source examples have complete, correctly owned labels.")

    # Layer 4: Source-to-build round-trip audit
    print("[Layer 4] Auditing source-to-build round-trip in-memory...")
    l4_errors = validate_source_to_build_roundtrip(notes_jsonl)
    if l4_errors:
        print(f"  [FAIL] {len(l4_errors)} round-trip error(s):", file=sys.stderr)
        for err in l4_errors:
            print(f"    - {err}", file=sys.stderr)
        all_errors.extend(l4_errors)
    else:
        print("  [PASS] Stored notes match fresh in-memory build 100%.")

    if all_errors:
        print(
            f"\n[FAIL] check_sense_labels: {len(all_errors)} error(s).",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n[PASS] check_sense_labels: all 4 layers clean.")


if __name__ == "__main__":
    main()
