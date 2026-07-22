"""Core validation for built Anki note artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.deck_builder.build_issues import BuildIssue
from src.deck_builder.build_contracts import (
    CARD_FIELDS,
    CANONICAL_TXT_HEADER,
    COLLOCATION_SOURCE_TOKENS,
    IDIOM_DISPLAY_MODES,
    MAX_COLLOCATIONS_PER_CARD,
    MAX_IDIOM_EXAMPLES_PER_IDIOM,
    MAX_IDIOMS_PER_CARD,
    BuildNotesResult,
    BuiltCard,
    serialize_jsonl,
    serialize_txt,
)
from src.deck_builder.dictionary_links import is_official_cambridge_url, is_official_oxford_url
from src.deck_builder.formatting import (
    normalize_idiom_example_key,
    parse_serialized_idiom_examples,
)
from src.deck_builder.audio_gate import validate_audio_gate
from src.deck_builder.example_audio import validate_example_audio_alignment
from src.deck_builder.example_policy import (
    main_example_pos_shortfall,
    rendered_main_examples,
)
from src.deck_builder.card_identity import (
    CardIdentity,
    primary_list_from_tags,
    reviewed_identity_variant,
)
from src.deck_builder.card_registry import (
    load_jsonl as load_registry_jsonl,
    validate_registry_rows,
)
from src.deck_builder.registry_build import RegistryBuildInputs, RegistryTarget
from src.deck_builder.relation_validation import validate_lexical_relation_metadata
from src.deck_builder.production import (
    derive_production_answer,
    production_eligible,
)
from src.deck_builder.sense_pos import fallback_sense_pos, valid_sense_pos_cell
from src.deck_builder.text_integrity import has_suspected_lossy_unicode


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[BuildIssue, ...]
    card_count: int
    deck_counts: dict[str, int]
    jsonl_sha256: str | None
    txt_sha256: str | None

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def error_text(self) -> str:
        return "\n".join(issue.format() for issue in self.issues if issue.severity == "error")


_APPEND_ONLY_CARD_FIELDS: tuple[str, ...] = (
    "production_answer",
    "sense_pos",
    "idiom_meaning_vi",
    "collocation_sources",
)


def _legacy_collocation_sources(collocations: str) -> str:
    """Treat pre-provenance chips as neutral curated/default presentation."""

    if not collocations.strip():
        return ""
    return "|".join("curated" for _ in collocations.split("|"))


def _legacy_field_value(field: str, values: dict[str, str]) -> str:
    if field == "production_answer":
        return derive_production_answer(values.get("word") or "")
    if field == "sense_pos":
        return fallback_sense_pos(
            values.get("pos") or "",
            values.get("definition_vi") or "",
        )
    if field == "idiom_meaning_vi":
        return ""
    if field == "collocation_sources":
        return _legacy_collocation_sources(values.get("collocations") or "")
    raise AssertionError(f"unsupported append-only field: {field}")


def _normalized_collocation_key(value: str) -> str:
    value = value.replace("\u200b", "")
    return re.sub(r"\s+", " ", value).strip().casefold()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _identity_for_card(
    card: BuiltCard,
    registry_by_guid: dict[str, RegistryTarget] | None = None,
) -> CardIdentity:
    if registry_by_guid is not None:
        target = registry_by_guid.get(card.guid.strip())
        if target is not None:
            return target.identity

    list_name = primary_list_from_tags(card.tags, canonical=True)
    return CardIdentity(
        word=card.word.strip(),
        cefr=(card.cefr or "").strip().upper() or "UNCLASSIFIED",
        list=list_name,
        variant=reviewed_identity_variant(card.word, card.cefr, list_name, card.pos),
    )


def _registry_targets_from_rows(rows: list[dict]) -> tuple[list[RegistryTarget], dict[tuple[str, str, str, str], RegistryTarget], list[BuildIssue]]:
    issues = validate_registry_rows(rows)
    targets: list[RegistryTarget] = []
    by_key: dict[tuple[str, str, str, str], RegistryTarget] = {}
    for row in rows:
        identity = CardIdentity(
            word=(row.get("word") or "").strip(),
            cefr=(row.get("cefr") or "").strip().upper() or "UNCLASSIFIED",
            list=(row.get("list") or "").strip(),
            variant=(row.get("variant") or "").strip(),
        )
        target = RegistryTarget(row=row, identity=identity)
        by_key[identity.as_key()] = target
        if row.get("status") == "active":
            targets.append(target)
    return targets, by_key, issues


def _parse_jsonl_cards(text: str, source: Path | str | None = None) -> tuple[list[BuiltCard], list[BuildIssue]]:
    cards: list[BuiltCard] = []
    issues: list[BuildIssue] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(BuildIssue("error", "jsonl_malformed", f"line {line_no}: {exc}", source=source))
            continue
        if not isinstance(row, dict):
            issues.append(BuildIssue("error", "jsonl_row_not_object", f"line {line_no} is not an object", source=source))
            continue
        missing = [field for field in CARD_FIELDS if field not in row]
        extra = [field for field in row if field not in CARD_FIELDS]
        legacy_missing = tuple(
            field for field in CARD_FIELDS if field in missing
        )
        valid_legacy_missing = {
            _APPEND_ONLY_CARD_FIELDS[-count:]
            for count in range(1, len(_APPEND_ONLY_CARD_FIELDS) + 1)
        }
        if legacy_missing and legacy_missing not in valid_legacy_missing:
            issues.append(BuildIssue("error", "jsonl_missing_field", f"line {line_no} missing fields {missing}", source=source))
            continue
        if extra:
            issues.append(BuildIssue("error", "jsonl_extra_field", f"line {line_no} has extra fields {extra}", source=source))
        values = []
        parsed_values: dict[str, str] = {
            field: value
            for field, value in row.items()
            if field in CARD_FIELDS and isinstance(value, str)
        }
        for field in CARD_FIELDS:
            value = row.get(field)
            if field in legacy_missing:
                value = _legacy_field_value(field, parsed_values)
            if not isinstance(value, str):
                issues.append(BuildIssue("error", "jsonl_non_string_field", f"line {line_no} field {field!r} must be string", source=source))
                value = "" if value is None else str(value)
            values.append(value)
            parsed_values[field] = value
        cards.append(BuiltCard(*values))
    return cards, issues


def _parse_txt_cards(text: str, source: Path | str | None = None) -> tuple[list[BuiltCard], list[BuildIssue]]:
    issues: list[BuildIssue] = []
    lines = text.splitlines()
    header = tuple(lines[: len(CANONICAL_TXT_HEADER)])
    if header != CANONICAL_TXT_HEADER:
        issues.append(BuildIssue(
            "error",
            "txt_bad_header",
            f"TXT header must be exactly {CANONICAL_TXT_HEADER!r}",
            source=source,
        ))
    cards: list[BuiltCard] = []
    for line_no, line in enumerate(lines[len(CANONICAL_TXT_HEADER):], len(CANONICAL_TXT_HEADER) + 1):
        if not line.strip():
            continue
        try:
            parts = next(csv.reader([line], delimiter="\t", strict=True))
        except csv.Error as exc:
            issues.append(BuildIssue(
                "error",
                "txt_malformed_row",
                f"line {line_no}: {exc}",
                source=source,
            ))
            continue
        legacy_prefix_lengths = {
            len(CARD_FIELDS) - missing_count
            for missing_count in range(1, len(_APPEND_ONLY_CARD_FIELDS) + 1)
        }
        if len(parts) in legacy_prefix_lengths:
            # Read-only compatibility for exact historical append-only
            # prefixes. Canonical serialization still writes every column.
            while len(parts) < len(CARD_FIELDS):
                field = CARD_FIELDS[len(parts)]
                current = dict(zip(CARD_FIELDS, parts))
                parts.append(_legacy_field_value(field, current))
            cards.append(BuiltCard(*parts))
            continue
        if len(parts) != len(CARD_FIELDS):
            issues.append(BuildIssue("error", "txt_bad_column_count", f"line {line_no} has {len(parts)} columns", source=source))
            continue
        cards.append(BuiltCard(*parts))
    return cards, issues


def _validate_cards(
    cards: list[BuiltCard],
    registry_targets: list[RegistryTarget],
    registry_by_key: dict[tuple[str, str, str, str], RegistryTarget],
) -> list[BuildIssue]:
    issues: list[BuildIssue] = []
    seen_guids: dict[str, int] = {}
    seen_keys: dict[tuple[str, str, str, str], int] = {}
    registry_by_guid = {
        (target.row.get("guid") or "").strip(): target
        for target in registry_targets
        if (target.row.get("guid") or "").strip()
    }

    for idx, card in enumerate(cards, 1):
        identity = _identity_for_card(card, registry_by_guid)
        for field in ("guid", "notetype", "deck", "word", "pos", "cefr"):
            if not getattr(card, field).strip():
                issues.append(BuildIssue("error", "required_field_empty", f"row {idx} field {field!r} is empty", identity=identity))

        for field in ("definition_vi", "idiom_meaning_vi"):
            if has_suspected_lossy_unicode(getattr(card, field)):
                issues.append(BuildIssue(
                    "error",
                    "suspected_lossy_unicode",
                    f"row {idx} field {field!r} contains suspected lossy Unicode",
                    identity=identity,
                ))

        pos_cells = [part.strip() for part in card.pos.split(",") if part.strip()]
        oxford_url_cells = card.oxford_pos_urls.split("|")
        if len(oxford_url_cells) != len(pos_cells):
            issues.append(BuildIssue(
                "error",
                "oxford_pos_url_alignment_mismatch",
                f"row {idx} OxfordPOSURLs has {len(oxford_url_cells)} cells for {len(pos_cells)} POS values",
                identity=identity,
            ))
        for url in oxford_url_cells:
            if any(char in url for char in ("\t", "\n", "\r", "|")) or (url and not is_official_oxford_url(url)):
                issues.append(BuildIssue(
                    "error",
                    "invalid_oxford_pos_url",
                    f"row {idx} contains an invalid Oxford POS URL",
                    identity=identity,
                ))
        if (
            any(char in card.cambridge_url for char in ("\t", "\n", "\r", "|"))
            or not is_official_cambridge_url(card.cambridge_url)
        ):
            issues.append(BuildIssue(
                "error",
                "invalid_cambridge_url",
                f"row {idx} contains an invalid Cambridge URL",
                identity=identity,
            ))

        example_without_double_breaks = re.sub(
            r"(?:<br\s*/?>\s*){2}", "", card.example, flags=re.IGNORECASE
        )
        if re.search(r"<br\s*/?>", example_without_double_breaks, flags=re.IGNORECASE):
            issues.append(BuildIssue(
                "error",
                "noncanonical_example_break",
                f"row {idx} Example must use <br><br> between examples of one sense",
                identity=identity,
            ))

        if card.definition_vi.strip():
            shortfall = main_example_pos_shortfall(
                card.pos,
                rendered_main_examples(card.example),
            )
            if shortfall is not None:
                actual, required = shortfall
                issues.append(BuildIssue(
                    "error",
                    "main_example_pos_shortfall",
                    (
                        f"row {idx} has {actual} nonblank main Examples for "
                        f"{required} distinct POS values"
                    ),
                    identity=identity,
                ))

        for relation_issue in validate_lexical_relation_metadata(
            card.example,
            card.synonyms,
            card.antonyms,
        ):
            issues.append(BuildIssue(
                "error",
                relation_issue.code,
                f"row {idx} {relation_issue.message}",
                identity=identity,
            ))

        collocation_cells = (
            card.collocations.split("|") if card.collocations else []
        )
        collocation_source_cells = (
            card.collocation_sources.split("|")
            if card.collocation_sources else []
        )
        if len(collocation_cells) > MAX_COLLOCATIONS_PER_CARD:
            issues.append(BuildIssue(
                "error",
                "collocation_limit_exceeded",
                (
                    f"row {idx} has {len(collocation_cells)} collocations; "
                    f"maximum is {MAX_COLLOCATIONS_PER_CARD}"
                ),
                identity=identity,
            ))
        if collocation_source_cells and not collocation_cells:
            issues.append(BuildIssue(
                "error",
                "collocation_sources_without_collocations",
                f"row {idx} has CollocationSources without Collocations content",
                identity=identity,
            ))
        if (
            collocation_source_cells
            and len(collocation_source_cells) != len(collocation_cells)
        ):
            issues.append(BuildIssue(
                "error",
                "collocation_source_alignment_mismatch",
                (
                    f"row {idx} CollocationSources has "
                    f"{len(collocation_source_cells)} cells for "
                    f"{len(collocation_cells)} Collocations cells"
                ),
                identity=identity,
            ))
        seen_collocations: set[str] = set()
        idiom_keys = {
            _normalized_collocation_key(entry.split("::", 1)[0])
            for entry in card.idioms.split("$$")
            if entry.strip()
        }
        for collocation_index, collocation in enumerate(collocation_cells):
            display_index = collocation_index + 1
            normalized = _normalized_collocation_key(collocation)
            if not normalized:
                issues.append(BuildIssue(
                    "error",
                    "collocation_empty_cell",
                    f"row {idx} Collocations cell {display_index} is empty",
                    identity=identity,
                ))
            if normalized in seen_collocations:
                issues.append(BuildIssue(
                    "error",
                    "collocation_duplicate",
                    (
                        f"row {idx} Collocations cell {display_index} "
                        "duplicates an earlier chip"
                    ),
                    identity=identity,
                ))
            seen_collocations.add(normalized)
            if normalized and normalized in idiom_keys:
                issues.append(BuildIssue(
                    "error",
                    "collocation_duplicates_idiom",
                    (
                        f"row {idx} Collocations cell {display_index} "
                        "duplicates an Idiom phrase"
                    ),
                    identity=identity,
                ))
            if (
                any(char in collocation for char in ("\t", "\n", "\r", ";"))
                or "::" in collocation
                or "$$" in collocation
                or re.search(r"<[^>]+>", collocation)
            ):
                issues.append(BuildIssue(
                    "error",
                    "collocation_invalid_text",
                    (
                        f"row {idx} Collocations cell {display_index} contains "
                        "forbidden markup or delimiters"
                    ),
                    identity=identity,
                ))
            if collocation_index < len(collocation_source_cells):
                source = collocation_source_cells[collocation_index]
                if source not in COLLOCATION_SOURCE_TOKENS:
                    issues.append(BuildIssue(
                        "error",
                        "collocation_source_invalid",
                        (
                            f"row {idx} CollocationSources cell {display_index} "
                            f"has invalid token {source!r}"
                        ),
                        identity=identity,
                    ))
                elif source != "curated" and "/" in collocation:
                    issues.append(BuildIssue(
                        "error",
                        "source_collocation_slash_compression",
                        (
                            f"row {idx} source-backed Collocations cell "
                            f"{display_index} must be one exact phrase"
                        ),
                        identity=identity,
                    ))

        if not card.definition.strip() and not card.idioms.strip():
            issues.append(BuildIssue(
                "error",
                "missing_learning_content",
                f"row {idx} must have either Definition or Idioms content",
                identity=identity,
            ))

        if card.definition_vi:
            definition_cells = card.definition.split("|")
            definition_vi_cells = card.definition_vi.split("|")
            if len(definition_cells) != len(definition_vi_cells):
                issues.append(BuildIssue(
                    "error",
                    "definition_vi_alignment_mismatch",
                    (
                        f"row {idx} DefinitionVI has {len(definition_vi_cells)} cells "
                        f"for {len(definition_cells)} Definition cells"
                    ),
                    identity=identity,
                ))
            elif any(
                definition.strip() and not vietnamese.strip()
                for definition, vietnamese in zip(definition_cells, definition_vi_cells)
            ):
                issues.append(BuildIssue(
                    "error",
                    "definition_vi_empty_cell",
                    f"row {idx} has an empty DefinitionVI cell for a populated Definition",
                    identity=identity,
                ))

            example_cells = card.example.split("|")
            sense_pos_cells = card.sense_pos.split("|") if card.sense_pos else []
            if len(example_cells) != len(definition_vi_cells):
                issues.append(BuildIssue(
                    "error",
                    "example_sense_alignment_mismatch",
                    (
                        f"row {idx} Example has {len(example_cells)} cells "
                        f"for {len(definition_vi_cells)} DefinitionVI cells"
                    ),
                    identity=identity,
                ))
            if len(sense_pos_cells) != len(definition_vi_cells):
                issues.append(BuildIssue(
                    "error",
                    "sense_pos_alignment_mismatch",
                    (
                        f"row {idx} SensePOS has {len(sense_pos_cells)} cells "
                        f"for {len(definition_vi_cells)} DefinitionVI cells"
                    ),
                    identity=identity,
                ))
            else:
                for sense_index, sense_pos in enumerate(sense_pos_cells, 1):
                    if not sense_pos.strip():
                        issues.append(BuildIssue(
                            "error",
                            "sense_pos_empty_cell",
                            f"row {idx} SensePOS cell {sense_index} is empty",
                            identity=identity,
                        ))
                    elif not valid_sense_pos_cell(card.pos, sense_pos):
                        issues.append(BuildIssue(
                            "error",
                            "sense_pos_invalid_cell",
                            (
                                f"row {idx} SensePOS cell {sense_index} "
                                f"{sense_pos!r} is not an ordered subset of {card.pos!r}"
                            ),
                            identity=identity,
                        ))
        elif card.sense_pos:
            issues.append(BuildIssue(
                "error",
                "sense_pos_without_definition_vi",
                f"row {idx} has SensePOS without DefinitionVI content",
                identity=identity,
            ))

        expected_production_answer = derive_production_answer(card.word)
        has_production_prompt_content = bool(
            card.definition_vi.strip() and card.example.strip()
        )
        if has_production_prompt_content and not card.production_answer.strip():
            issues.append(BuildIssue(
                "error",
                "production_answer_missing",
                (
                    f"row {idx} has Vietnamese/example content but no "
                    "ProductionAnswer"
                ),
                identity=identity,
            ))
        elif production_eligible(card) and card.production_answer != expected_production_answer:
            issues.append(BuildIssue(
                "error",
                "production_answer_mismatch",
                (
                    f"row {idx} ProductionAnswer {card.production_answer!r} "
                    f"must equal the canonical value {expected_production_answer!r}"
                ),
                identity=identity,
            ))
        elif (
            card.production_answer.strip()
            and card.production_answer != expected_production_answer
        ):
            # Ineligible legacy/unit-test rows may omit the appended field, but
            # a populated value must never drift from its deterministic source.
            issues.append(BuildIssue(
                "error",
                "production_answer_mismatch",
                (
                    f"row {idx} ProductionAnswer {card.production_answer!r} "
                    f"must equal the canonical value {expected_production_answer!r}"
                ),
                identity=identity,
            ))

        idiom_count = len([
            entry for entry in card.idioms.split("$$") if entry.strip()
        ])
        if idiom_count > MAX_IDIOMS_PER_CARD:
            issues.append(BuildIssue(
                "error",
                "idiom_limit_exceeded",
                f"row {idx} has {idiom_count} idioms; maximum is {MAX_IDIOMS_PER_CARD}",
                identity=identity,
            ))

        idiom_vi_cells = (
            card.idiom_meaning_vi.split("$$") if card.idiom_meaning_vi else []
        )
        if not idiom_count and idiom_vi_cells:
            issues.append(BuildIssue(
                "error",
                "idiom_meaning_vi_without_idioms",
                f"row {idx} has IdiomMeaningVI without Idioms content",
                identity=identity,
            ))
        elif idiom_count != len(idiom_vi_cells):
            issues.append(BuildIssue(
                "error",
                "idiom_meaning_vi_alignment_mismatch",
                (
                    f"row {idx} IdiomMeaningVI has {len(idiom_vi_cells)} cells "
                    f"for {idiom_count} Idioms entries"
                ),
                identity=identity,
            ))
        else:
            for idiom_idx, cell in enumerate(idiom_vi_cells, 1):
                parts = cell.split("::")
                if len(parts) != 2:
                    issues.append(BuildIssue(
                        "error",
                        "idiom_meaning_vi_malformed_cell",
                        f"row {idx} IdiomMeaningVI cell {idiom_idx} is malformed",
                        identity=identity,
                    ))
                    continue
                mode, vietnamese = (part.strip() for part in parts)
                if mode not in IDIOM_DISPLAY_MODES:
                    issues.append(BuildIssue(
                        "error",
                        "idiom_meaning_vi_invalid_mode",
                        f"row {idx} IdiomMeaningVI cell {idiom_idx} has invalid mode {mode!r}",
                        identity=identity,
                    ))
                if (
                    not vietnamese
                    or any(char in vietnamese for char in "\t\r\n")
                    or re.search(r"<br\s*/?>", vietnamese, flags=re.IGNORECASE)
                ):
                    issues.append(BuildIssue(
                        "error",
                        "idiom_meaning_vi_invalid_text",
                        f"row {idx} IdiomMeaningVI cell {idiom_idx} has invalid Vietnamese text",
                        identity=identity,
                    ))

        seen_idiom_example_keys: set[str] = set()
        for idiom_idx, examples in enumerate(
            parse_serialized_idiom_examples(card.idioms), 1
        ):
            if len(examples) > MAX_IDIOM_EXAMPLES_PER_IDIOM:
                issues.append(BuildIssue(
                    "error",
                    "idiom_example_limit_exceeded",
                    (
                        f"row {idx} idiom {idiom_idx} has {len(examples)} examples; "
                        f"maximum is {MAX_IDIOM_EXAMPLES_PER_IDIOM}"
                    ),
                    identity=identity,
                ))
            if len(examples) == 1:
                key = normalize_idiom_example_key(examples[0])
                if key in seen_idiom_example_keys:
                    issues.append(BuildIssue(
                        "error",
                        "idiom_example_duplicate",
                        (
                            f"row {idx} idiom {idiom_idx} repeats an example "
                            "used by an earlier idiom"
                        ),
                        identity=identity,
                    ))
                else:
                    seen_idiom_example_keys.add(key)

        for field in validate_example_audio_alignment(card):
            issues.append(BuildIssue(
                "error",
                "example_audio_alignment_mismatch",
                f"row {idx} field {field!r} does not match canonical Example/Idioms audio planning",
                identity=identity,
            ))

        if card.guid in seen_guids:
            issues.append(BuildIssue("error", "duplicate_guid", f"GUID {card.guid!r} appears at rows {seen_guids[card.guid]} and {idx}", identity=identity))
        else:
            seen_guids[card.guid] = idx

        key = identity.as_key()
        if key in seen_keys:
            issues.append(BuildIssue("error", "duplicate_registry_identity", f"identity {key} appears at rows {seen_keys[key]} and {idx}", identity=identity))
        else:
            seen_keys[key] = idx

        target = registry_by_key.get(key)
        if target is None:
            issues.append(BuildIssue("error", "unknown_registry_identity", f"output row {idx} has no registry row", identity=identity))
        elif target.row.get("status") != "active":
            issues.append(BuildIssue("error", "retired_registry_identity_emitted", f"output row {idx} emits retired registry row", identity=identity))
        else:
            expected_guid = (target.row.get("guid") or "").strip()
            if card.guid != expected_guid:
                issues.append(BuildIssue("error", "registry_guid_mismatch", f"row {idx} GUID {card.guid!r} != registry {expected_guid!r}", identity=identity))
            expected_pos = (target.row.get("pos") or "").strip()
            if card.pos != expected_pos:
                issues.append(BuildIssue("error", "registry_pos_mismatch", f"row {idx} POS {card.pos!r} != registry {expected_pos!r}", identity=identity))

    actual_order = [_identity_for_card(card, registry_by_guid).as_key() for card in cards]
    expected_order = [target.identity.as_key() for target in registry_targets]
    if actual_order != expected_order:
        first_diff = next(
            (idx for idx, (actual, expected) in enumerate(zip(actual_order, expected_order), 1) if actual != expected),
            None,
        )
        if len(actual_order) != len(expected_order):
            message = f"card count/order differs: output={len(actual_order)} registry={len(expected_order)}"
        else:
            message = f"registry order differs at row {first_diff}: output={actual_order[first_diff - 1]!r} registry={expected_order[first_diff - 1]!r}"
        issues.append(BuildIssue("error", "registry_coverage_order_mismatch", message))

    missing_keys = set(expected_order) - set(actual_order)
    unknown_keys = set(actual_order) - set(registry_by_key)
    for key in sorted(missing_keys)[:20]:
        issues.append(BuildIssue("error", "registry_active_missing", f"active registry key missing from output: {key}", identity=CardIdentity(*key)))
    for key in sorted(unknown_keys)[:20]:
        issues.append(BuildIssue("error", "registry_unknown_output", f"output key missing from registry: {key}", identity=CardIdentity(*key)))
    return issues


def _report(cards: list[BuiltCard], issues: list[BuildIssue], jsonl_text: str | None, txt_text: str | None) -> ValidationReport:
    deck_counts = dict(Counter(card.deck for card in cards))
    return ValidationReport(
        issues=tuple(issues),
        card_count=len(cards),
        deck_counts=deck_counts,
        jsonl_sha256=_sha256_text(jsonl_text) if jsonl_text is not None else None,
        txt_sha256=_sha256_text(txt_text) if txt_text is not None else None,
    )


def validate_build_result(
    result: BuildNotesResult,
    registry_inputs: RegistryBuildInputs,
    audio_dir: Path,
    *,
    validate_audio: bool = True,
) -> ValidationReport:
    issues: list[BuildIssue] = []

    parsed_jsonl, jsonl_issues = _parse_jsonl_cards(result.jsonl_text, "build-result-jsonl")
    parsed_txt, txt_issues = _parse_txt_cards(result.txt_text, "build-result-txt")
    issues.extend(jsonl_issues)
    issues.extend(txt_issues)

    if parsed_jsonl != result.built_cards:
        issues.append(BuildIssue("error", "jsonl_result_mismatch", "result.jsonl_text does not match result.built_cards"))
    if parsed_txt != result.built_cards:
        issues.append(BuildIssue("error", "txt_result_mismatch", "result.txt_text does not match result.built_cards"))
    if result.jsonl_text != serialize_jsonl(result.built_cards):
        issues.append(BuildIssue("error", "jsonl_serialization_mismatch", "JSONL serialization is not deterministic"))
    if result.txt_text != serialize_txt(result.built_cards):
        issues.append(BuildIssue("error", "txt_serialization_mismatch", "TXT serialization is not deterministic/canonical"))

    issues.extend(_validate_cards(
        result.built_cards,
        registry_inputs.targets,
        registry_inputs.registry_by_key,
    ))
    if validate_audio:
        issues.extend(validate_audio_gate(result.built_cards, audio_dir).issues)
    return _report(result.built_cards, issues, result.jsonl_text, result.txt_text)


def validate_artifact_paths(
    jsonl_path: Path,
    txt_path: Path,
    registry_path: Path,
    audio_dir: Path,
) -> ValidationReport:
    issues: list[BuildIssue] = []
    jsonl_text: str | None = None
    txt_text: str | None = None

    try:
        jsonl_text = jsonl_path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(BuildIssue("error", "jsonl_read_failed", str(exc), source=jsonl_path))
    try:
        txt_text = txt_path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(BuildIssue("error", "txt_read_failed", str(exc), source=txt_path))

    registry_rows: list[dict] = []
    try:
        registry_rows = load_registry_jsonl(registry_path)
    except Exception as exc:
        issues.append(BuildIssue("error", "registry_read_failed", str(exc), source=registry_path))
    registry_targets, registry_by_key, registry_issues = _registry_targets_from_rows(registry_rows)
    issues.extend(registry_issues)

    jsonl_cards: list[BuiltCard] = []
    txt_cards: list[BuiltCard] = []
    if jsonl_text is not None:
        jsonl_cards, jsonl_issues = _parse_jsonl_cards(jsonl_text, jsonl_path)
        issues.extend(jsonl_issues)
    if txt_text is not None:
        txt_cards, txt_issues = _parse_txt_cards(txt_text, txt_path)
        issues.extend(txt_issues)

    if jsonl_cards and txt_cards:
        if len(jsonl_cards) != len(txt_cards):
            issues.append(BuildIssue("error", "artifact_card_count_mismatch", f"JSONL has {len(jsonl_cards)} cards; TXT has {len(txt_cards)} cards"))
        for idx, (jsonl_card, txt_card) in enumerate(zip(jsonl_cards, txt_cards), 1):
            if jsonl_card != txt_card:
                identity = _identity_for_card(jsonl_card)
                for field in CARD_FIELDS:
                    if getattr(jsonl_card, field) != getattr(txt_card, field):
                        issues.append(BuildIssue("error", "artifact_field_mismatch", f"row {idx} field {field}: JSONL={getattr(jsonl_card, field)!r} TXT={getattr(txt_card, field)!r}", identity=identity))
                        break
    cards = jsonl_cards or txt_cards

    if jsonl_text is not None and jsonl_cards and jsonl_text != serialize_jsonl(jsonl_cards):
        issues.append(BuildIssue("error", "jsonl_serialization_mismatch", "JSONL artifact is not canonical serialization"))
    if txt_text is not None and txt_cards and txt_text != serialize_txt(txt_cards):
        issues.append(BuildIssue("error", "txt_serialization_mismatch", "TXT artifact is not canonical serialization"))

    if cards:
        issues.extend(_validate_cards(cards, registry_targets, registry_by_key))
        issues.extend(validate_audio_gate(cards, audio_dir).issues)

    return _report(cards, issues, jsonl_text, txt_text)
