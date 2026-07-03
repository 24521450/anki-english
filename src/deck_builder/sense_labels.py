"""Sense label engine for Oxford definitions.

Attaches Register Labels and explicit Subject Labels to definition chunks
as prefixes (e.g. `[informal]cut greatly (cắt giảm mạnh)`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from src.scraper.oxford_labels import CONFLICT_PAIRS, REGISTER_LABELS, SUBJECT_LABELS

if TYPE_CHECKING:
    from src.deck_builder.build_notes import BuiltCard
    from src.deck_builder.simplify_senses import MergedSense

ALL_VALID_LABELS: frozenset[str] = REGISTER_LABELS | SUBJECT_LABELS
# CONFLICT_PAIRS is re-exported from oxford_labels (canonical location)

_PREFIX_RE = re.compile(r"^\[([^\]]+)\]\s*")


class _SourceLabelSpec(NamedTuple):
    source_definition: str
    labels: tuple[str, ...]
    examples: tuple[str, ...]
    relation_words: tuple[str, ...]



def load_sense_label_overrides(path: Path | str | None) -> dict[str, list[dict[str, Any]]]:
    """Load manual sense label overrides from a JSONL file.

    Schema:
    {
      "guid": "...",
      "word": "slash",
      "pos": "verb",
      "cefr": "C1",
      "source_definition": "...",
      "definition_chunk": "...",
      "action": "apply" | "skip",
      "labels": ["informal"],  # required for action == apply
      "reason": "..."           # required for action == skip
    }
    """
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        return {}

    overrides: dict[str, list[dict[str, Any]]] = {}
    with open(p, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            try:
                rec = json.loads(line_str)
            except Exception as err:
                raise ValueError(f"Invalid JSON in {p}:{line_num}: {err}") from err

            guid = rec.get("guid")
            if not guid:
                raise ValueError(f"Missing 'guid' in override {p}:{line_num}")

            chunk = (rec.get("definition_chunk") or "").strip()
            if not chunk:
                raise ValueError(f"Missing 'definition_chunk' in override {p}:{line_num}")

            seen_chunks = {(o.get("definition_chunk") or "").strip() for o in overrides.get(guid, [])}
            if chunk in seen_chunks:
                raise ValueError(f"Duplicate override for GUID '{guid}' chunk '{chunk}' in {p}:{line_num}")

            action = rec.get("action")
            if action not in ("apply", "skip"):
                raise ValueError(f"Invalid action '{action}' in {p}:{line_num} (must be 'apply' or 'skip')")

            if action == "apply":
                labels = rec.get("labels")
                if not isinstance(labels, list) or not labels:
                    raise ValueError(f"Action 'apply' requires non-empty 'labels' list in {p}:{line_num}")
                for lbl in labels:
                    if lbl not in ALL_VALID_LABELS:
                        raise ValueError(f"Invented label '{lbl}' in {p}:{line_num}")
            elif action == "skip":
                if not rec.get("reason"):
                    raise ValueError(f"Action 'skip' requires 'reason' in {p}:{line_num}")

            overrides.setdefault(guid, []).append(rec)

    return overrides


def format_label_prefix(register_tags: list[str] | None, domain: str | None) -> str:
    """Format register tags and domain into prefix string `[tag1, tag2]`.

    Order: register_tags (in source order), then domain.
    Returns empty string if no labels present.
    """
    labels: list[str] = []
    if register_tags:
        for r in register_tags:
            if r and r not in labels:
                labels.append(r)
    if domain and domain not in labels:
        labels.append(domain)

    if not labels:
        return ""
    return f"[{', '.join(labels)}]"


def parse_existing_prefix(chunk: str) -> tuple[list[str], str]:
    """Parse existing `[prefix]` from a definition chunk.

    Returns (labels_list, clean_chunk_without_prefix).
    """
    m = _PREFIX_RE.match(chunk)
    if not m:
        return [], chunk
    prefix_content = m.group(1)
    labels = [lbl.strip() for lbl in prefix_content.split(",") if lbl.strip()]
    rest = chunk[m.end():].strip()
    return labels, rest


def check_register_conflicts(register_tags: list[str]) -> str | None:
    """Check for forbidden hard conflicts in register tags."""
    reg_set = set(register_tags)
    for tag1, tag2 in CONFLICT_PAIRS:
        if tag1 in reg_set and tag2 in reg_set:
            return f"Hard conflict detected in register tags: '{tag1}' and '{tag2}'"
    return None


def _normalize_example(text: str) -> str:
    normalized = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return " ".join(normalized.lower().split())


def _strip_known_relation_annotations(text: str, relation_words: tuple[str, ...]) -> str:
    """Remove only parentheticals fully explained by known lexical relations."""
    known = {word.strip().lower() for word in relation_words if word.strip()}
    if not known:
        return text

    def replace_match(match: re.Match[str]) -> str:
        items = [item.strip().lower() for item in match.group(1).split(",") if item.strip()]
        return "" if items and all(item in known for item in items) else match.group(0)

    return re.sub(r"\s+\(([^)]+)\)", replace_match, text)


def _normalize_source_label_specs(raw_specs: list[dict]) -> list[_SourceLabelSpec]:
    specs: list[_SourceLabelSpec] = []
    for spec in raw_specs:
        source_definition = (spec.get("source_definition") or "").strip().lower()
        if not source_definition:
            continue
        labels = list(dict.fromkeys(spec.get("register_tags") or []))
        domain = spec.get("domain")
        if domain and domain not in labels:
            labels.append(domain)
        examples = tuple(
            example.strip()
            for example in (spec.get("examples") or [])
            if isinstance(example, str) and example.strip()
        )
        relation_words = tuple(dict.fromkeys(
            list(spec.get("synonyms") or []) + list(spec.get("antonyms") or [])
        ))
        specs.append(_SourceLabelSpec(
            source_definition=source_definition,
            labels=tuple(labels),
            examples=examples,
            relation_words=relation_words,
        ))
    return specs


def _source_label_specs(senses: list[MergedSense]) -> list[_SourceLabelSpec]:
    """Return normalized source definitions paired with their owned labels.

    Production senses carry ``label_specs`` from the exact Oxford definitions.
    The fallback keeps older callers and focused tests compatible without
    weakening source-definition ownership in production builds.
    """
    raw_specs_for_senses: list[dict] = []
    for sense in senses:
        if sense.label_specs is not None:
            raw_specs = sense.label_specs
        else:
            relation_words: list[str] = []
            for relation_spec in sense.relation_specs or []:
                relation_words.extend(relation_spec.get("synonyms") or [])
                relation_words.extend(relation_spec.get("antonyms") or [])
            raw_specs = [
                {
                    "source_definition": part,
                    "register_tags": sense.register_tags or [],
                    "domain": sense.domain,
                    "examples": [
                        (example.get("text") or "").strip()
                        for example in (sense.examples or [])
                        if (example.get("text") or "").strip()
                    ],
                    "synonyms": relation_words,
                    "antonyms": [],
                }
                for part in sense.text.split(" ; ")
                if part.strip()
            ]

        raw_specs_for_senses.extend(raw_specs)
    return _normalize_source_label_specs(raw_specs_for_senses)


def _matching_example_specs(
    example_chunk: str,
    source_specs: list[_SourceLabelSpec],
) -> list[_SourceLabelSpec]:
    if not example_chunk.strip():
        return []

    matches: list[_SourceLabelSpec] = []
    for spec in source_specs:
        cleaned_chunk = _strip_known_relation_annotations(example_chunk, spec.relation_words)
        chunk_key = _normalize_example(cleaned_chunk)
        if any(chunk_key == _normalize_example(source_example) for source_example in spec.examples):
            matches.append(spec)
    return matches


def _resolve_matching_labels(
    matching_specs: list[_SourceLabelSpec],
) -> tuple[tuple[str, ...] | None, list[list[str]] | None]:
    """Resolve label ownership, returning ambiguity candidates when unsafe."""
    if not matching_specs:
        return None, None
    distinct_sets = {frozenset(spec.labels) for spec in matching_specs}
    if len(distinct_sets) > 1:
        return None, sorted(sorted(labels) for labels in distinct_sets)
    return matching_specs[0].labels, None


def apply_sense_labels(
    all_cards: list[BuiltCard],
    guid_to_senses: dict[str, list[MergedSense]],
    overrides: dict[str, list[dict[str, Any]]] | None = None,
    guid_to_source_label_specs: dict[str, list[dict]] | None = None,
) -> tuple[list[BuiltCard], list[str]]:
    """Apply sense label prefixes to definition chunks of cards.

    Returns (annotated_cards, errors).
    """
    overrides = overrides or {}
    guid_to_source_label_specs = guid_to_source_label_specs or {}
    annotated_cards: list[BuiltCard] = []
    errors: list[str] = []
    used_override_keys: set[tuple[str, str]] = set()

    built_guids = {c.guid for c in all_cards}
    for g in overrides:
        if g not in built_guids:
            errors.append(f"Unknown card GUID in sense label overrides: '{g}'")


    for card in all_cards:
        def_chunks = [ch.strip() for ch in card.definition.split("|") if ch.strip()]
        if not def_chunks:
            annotated_cards.append(card)
            continue

        senses = guid_to_senses.get(card.guid) or []
        card_overrides = overrides.get(card.guid) or []
        raw_source_specs = guid_to_source_label_specs.get(card.guid)
        source_label_specs = (
            _normalize_source_label_specs(raw_source_specs)
            if raw_source_specs is not None
            else _source_label_specs(senses)
        )

        # Card identity & source definition validation on overrides
        card_word_clean = card.word.split(" (")[0].strip().lower()
        for ov in card_overrides:
            ov_word = (ov.get("word") or "").split(" (")[0].strip().lower()
            ov_pos = (ov.get("pos") or "").strip().lower()
            ov_cefr = (ov.get("cefr") or "").strip().upper()
            if (ov_word, ov_pos, ov_cefr) != (card_word_clean, card.pos.strip().lower(), card.cefr.strip().upper()):
                errors.append(
                    f"Identity mismatch in sense label override for GUID '{card.guid}': "
                    f"override ({ov_word}, {ov_pos}, {ov_cefr}) vs card ({card_word_clean}, {card.pos}, {card.cefr})"
                )

            ov_src_def = (ov.get("source_definition") or "").strip().lower()
            ov_chunk = (ov.get("definition_chunk") or "").strip()
            action = ov.get("action")

            matched_source_labels: frozenset[str] | None = None
            if not ov_src_def:
                errors.append(f"Missing 'source_definition' in sense label override for GUID '{card.guid}'")
            else:
                matching_specs = [
                    spec for spec in source_label_specs
                    if spec.source_definition == ov_src_def
                ]
                matched_source_labels, ambiguous_candidates = _resolve_matching_labels(matching_specs)
                if not matching_specs:
                    errors.append(
                        f"Source definition mismatch in sense label override for GUID '{card.guid}': "
                        f"source_definition '{ov.get('source_definition')}' does not exact-match any source definition of card '{card.word}'"
                    )
                elif ambiguous_candidates is not None:
                    errors.append(
                        f"Ambiguous source definition in sense label override for GUID '{card.guid}': "
                        f"source_definition '{ov.get('source_definition')}' has conflicting source label sets "
                        f"{ambiguous_candidates}"
                    )

            if matched_source_labels is not None and action == "skip":
                if not matched_source_labels:
                    errors.append(
                        f"Unnecessary 'skip' override for GUID '{card.guid}' chunk '{ov_chunk}': "
                        f"source definition has no labels to skip"
                    )
            elif matched_source_labels is not None and action == "apply":
                ov_labels = ov.get("labels") or []
                conflict_err = check_register_conflicts(ov_labels)
                if conflict_err:
                    errors.append(
                        f"Invalid 'apply' override for GUID '{card.guid}' chunk '{ov_chunk}': "
                        f"{conflict_err}"
                    )
                for lbl in ov_labels:
                    if lbl not in set(matched_source_labels):
                        errors.append(
                            f"Invalid label '{lbl}' in override for GUID '{card.guid}' chunk '{ov_chunk}': "
                            f"label is not present on source definition "
                            f"(source labels: {sorted(matched_source_labels)})"
                        )

        # Map def chunks to senses
        # Rule: auto-map 1:1 if counts match
        is_one_to_one = (len(def_chunks) == len(senses))
        example_chunks = [chunk.strip() for chunk in card.example.split("|")]
        new_chunks: list[str] = []

        for idx, chunk in enumerate(def_chunks):
            existing_labels, clean_chunk = parse_existing_prefix(chunk)

            # Check if an override applies to this chunk
            chunk_ov = None
            for ov in card_overrides:
                ov_chunk = (ov.get("definition_chunk") or "").strip()
                _, clean_ov_chunk = parse_existing_prefix(ov_chunk)
                if clean_ov_chunk == clean_chunk or ov_chunk == chunk:
                    chunk_ov = ov
                    used_override_keys.add((card.guid, ov_chunk))
                    break

            if chunk_ov:
                if chunk_ov["action"] == "skip":
                    new_chunks.append(clean_chunk)
                else:  # apply
                    prefix = format_label_prefix(chunk_ov["labels"], None)
                    new_chunks.append(f"{prefix}{clean_chunk}" if prefix else clean_chunk)
                continue

            example_chunk = example_chunks[idx] if idx < len(example_chunks) else ""
            example_specs = _matching_example_specs(example_chunk, source_label_specs)
            matched_labels, ambiguous_candidates = _resolve_matching_labels(example_specs)
            if ambiguous_candidates is not None:
                errors.append(
                    f"Card {card.word} ({card.guid}) chunk {idx+1}: exact source example "
                    f"matches conflicting source label sets {ambiguous_candidates}. "
                    f"Requires manual override."
                )
                new_chunks.append(clean_chunk)
                continue
            if matched_labels is not None:
                conflict_err = check_register_conflicts(list(matched_labels))
                if conflict_err:
                    errors.append(
                        f"Card {card.word} ({card.guid}) chunk {idx+1}: {conflict_err}. "
                        f"Requires manual override."
                    )
                prefix = format_label_prefix(list(matched_labels), None)
                new_chunks.append(f"{prefix}{clean_chunk}" if prefix else clean_chunk)
                continue

            # Auto-mapping path
            if is_one_to_one:
                sense = senses[idx]
                sense_specs = _source_label_specs([sense])
                matched_labels, ambiguous_candidates = _resolve_matching_labels(sense_specs)
                if ambiguous_candidates is not None:
                    errors.append(
                        f"Card {card.word} ({card.guid}) chunk {idx+1}: source definitions "
                        f"have conflicting label ownership {ambiguous_candidates} and no exact "
                        f"example match. Requires manual override."
                    )
                    new_chunks.append(clean_chunk)
                    continue
                reg_tags = list(matched_labels or ())

                conflict_err = check_register_conflicts(reg_tags)
                if conflict_err:
                    errors.append(f"Card {card.word} ({card.guid}) chunk {idx+1}: {conflict_err}. Requires manual override.")

                prefix = format_label_prefix(reg_tags, None)
                new_chunks.append(f"{prefix}{clean_chunk}" if prefix else clean_chunk)
            else:
                # Chunk counts differ -> check internal conflict per individual sense
                for s_idx, s in enumerate(senses, start=1):
                    conflict_err = check_register_conflicts(list(s.register_tags or []))
                    if conflict_err:
                        errors.append(f"Card {card.word} ({card.guid}) sense {s_idx}: {conflict_err}. Requires manual override.")
                new_chunks.append(clean_chunk)

        new_def_str = "|".join(new_chunks)
        annotated_cards.append(card._replace(definition=new_def_str))

    # Check unused overrides
    for g, ov_list in overrides.items():
        for ov in ov_list:
            ov_chunk = (ov.get("definition_chunk") or "").strip()
            if (g, ov_chunk) not in used_override_keys and g in built_guids:
                errors.append(f"Unused sense label override for GUID '{g}' chunk '{ov_chunk}'")

    return annotated_cards, errors
