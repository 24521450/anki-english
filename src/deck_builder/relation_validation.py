"""Validation for pipe-aligned lexical-relation metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass


_PARENTHETICAL_RE = re.compile(r"\(([^()]*)\)")


@dataclass(frozen=True, slots=True)
class RelationValidationIssue:
    code: str
    message: str


def _relation_items(value: str) -> set[str]:
    value = re.sub(r"^=\s*", "", value.strip())
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def _metadata_items(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def validate_lexical_relation_metadata(
    example: str,
    synonyms: str,
    antonyms: str,
) -> tuple[RelationValidationIssue, ...]:
    """Ensure relation metadata can be rendered unambiguously in its Example cell."""
    issues: list[RelationValidationIssue] = []
    example_cells = example.split("|")

    relation_fields = (("synonym", synonyms), ("antonym", antonyms))
    split_fields: dict[str, list[str]] = {}
    for channel, raw_value in relation_fields:
        cells = raw_value.split("|") if raw_value else []
        split_fields[channel] = cells
        if raw_value and len(cells) != len(example_cells):
            issues.append(
                RelationValidationIssue(
                    "relation_metadata_alignment",
                    f"{channel} metadata has {len(cells)} pipe cells but Example has "
                    f"{len(example_cells)}",
                )
            )

    for cell_index, example_cell in enumerate(example_cells, 1):
        synonym_cells = split_fields["synonym"]
        antonym_cells = split_fields["antonym"]
        synonym_set = _metadata_items(
            synonym_cells[cell_index - 1] if cell_index <= len(synonym_cells) else ""
        )
        antonym_set = _metadata_items(
            antonym_cells[cell_index - 1] if cell_index <= len(antonym_cells) else ""
        )

        overlap = synonym_set & antonym_set
        if overlap:
            issues.append(
                RelationValidationIssue(
                    "relation_channel_overlap",
                    f"Example cell {cell_index} has terms in both relation channels: "
                    f"{sorted(overlap)}",
                )
            )

        represented_synonyms: set[str] = set()
        represented_antonyms: set[str] = set()
        relation_union = synonym_set | antonym_set
        for match in _PARENTHETICAL_RE.finditer(example_cell):
            items = _relation_items(match.group(1))
            if not items:
                continue
            is_synonym = bool(synonym_set) and items <= synonym_set
            is_antonym = bool(antonym_set) and items <= antonym_set
            if is_synonym and is_antonym:
                issues.append(
                    RelationValidationIssue(
                        "relation_channel_ambiguous",
                        f"Example cell {cell_index} parenthetical {match.group(0)!r} "
                        "matches both relation channels",
                    )
                )
            elif is_synonym:
                represented_synonyms.update(items)
            elif is_antonym:
                represented_antonyms.update(items)
            elif items & relation_union:
                issues.append(
                    RelationValidationIssue(
                        "relation_annotation_unrenderable",
                        f"Example cell {cell_index} parenthetical {match.group(0)!r} mixes "
                        "relation metadata with unrelated or cross-channel terms",
                    )
                )

        missing_synonyms = synonym_set - represented_synonyms
        missing_antonyms = antonym_set - represented_antonyms
        if missing_synonyms:
            issues.append(
                RelationValidationIssue(
                    "relation_metadata_unrepresented",
                    f"Example cell {cell_index} has synonym metadata without a renderable "
                    f"parenthetical: {sorted(missing_synonyms)}",
                )
            )
        if missing_antonyms:
            issues.append(
                RelationValidationIssue(
                    "relation_metadata_unrepresented",
                    f"Example cell {cell_index} has antonym metadata without a renderable "
                    f"parenthetical: {sorted(missing_antonyms)}",
                )
            )

    return tuple(issues)
