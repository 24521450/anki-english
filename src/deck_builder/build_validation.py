"""Core validation for built Anki note artifacts."""
from __future__ import annotations

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
    MAX_IDIOM_EXAMPLES_PER_IDIOM,
    MAX_IDIOMS_PER_CARD,
    BuildNotesResult,
    BuiltCard,
    serialize_jsonl,
    serialize_txt,
)
from src.deck_builder.formatting import (
    normalize_idiom_example_key,
    parse_serialized_idiom_examples,
)
from src.deck_builder.audio_gate import validate_audio_gate
from src.deck_builder.example_audio import validate_example_audio_alignment
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
        if missing:
            issues.append(BuildIssue("error", "jsonl_missing_field", f"line {line_no} missing fields {missing}", source=source))
            continue
        if extra:
            issues.append(BuildIssue("error", "jsonl_extra_field", f"line {line_no} has extra fields {extra}", source=source))
        values = []
        for field in CARD_FIELDS:
            value = row.get(field)
            if not isinstance(value, str):
                issues.append(BuildIssue("error", "jsonl_non_string_field", f"line {line_no} field {field!r} must be string", source=source))
                value = "" if value is None else str(value)
            values.append(value)
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
        parts = line.split("\t")
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
