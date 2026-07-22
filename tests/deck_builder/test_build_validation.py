from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.deck_builder.build_contracts import BuildNotesResult, BuiltCard
from src.deck_builder.build_validation import (
    CANONICAL_TXT_HEADER,
    _parse_txt_cards,
    serialize_jsonl,
    serialize_txt,
    validate_artifact_paths,
    validate_build_result,
)
from src.deck_builder.registry_build import load_registry_build_inputs
from src.deck_builder.example_audio import plan_cards_example_audio, referenced_example_audio_names


def _card(guid: str = "g1", audio: str = "") -> BuiltCard:
    return BuiltCard(
        guid,
        "English Academic Vocabulary Model",
        "Deck",
        "word",
        "noun",
        "",
        "definition",
        "example",
        "",
        "",
        audio,
        "",
        "Oxford",
        "Oxford",
        "A1",
        "",
        "Source::Oxford CEFR::A1 CEFR::oxford",
        "",
        "",
        cambridge_url="https://dictionary.cambridge.org/dictionary/english/word",
    )


def _result(cards: list[BuiltCard]) -> BuildNotesResult:
    cards, _ = plan_cards_example_audio(cards)
    return BuildNotesResult(cards, serialize_jsonl(cards), serialize_txt(cards), 0, 0, 0, 0, 0, len(cards), 0)


def _result_with_audio(cards: list[BuiltCard], audio_dir: Path) -> BuildNotesResult:
    result = _result(cards)
    for filename in referenced_example_audio_names(result.built_cards):
        (audio_dir / filename).write_bytes(b"ID3" + b"x" * 509)
    return result


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_registry(path: Path, cards: list[BuiltCard]) -> None:
    rows = [
        {
            "word": card.word,
            "cefr": card.cefr,
            "list": "NO_LIST",
            "variant": "",
            "pos": card.pos,
            "guid": card.guid,
            "status": "active",
            "deck_override": card.deck,
        }
        for card in cards
    ]
    _write_jsonl(path, rows)


def _write_artifacts(tmp_path: Path, cards: list[BuiltCard]) -> tuple[Path, Path, Path, Path]:
    cards, _ = plan_cards_example_audio(cards)
    jsonl_path = tmp_path / "anki_notes.jsonl"
    txt_path = tmp_path / "anki_notes.txt"
    registry_path = tmp_path / "card_registry.jsonl"
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    jsonl_path.write_text(serialize_jsonl(cards), encoding="utf-8")
    txt_path.write_text(serialize_txt(cards), encoding="utf-8")
    _write_registry(registry_path, cards)
    return jsonl_path, txt_path, registry_path, audio_dir


def test_validate_build_result_accepts_valid_result(tmp_path: Path):
    card = _card()
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok
    assert report.card_count == 1


def test_validate_build_result_rejects_single_example_break(tmp_path: Path):
    card = _card()._replace(example="first example<br>second example")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(issue.code == "noncanonical_example_break" for issue in report.issues)


def test_validate_build_result_accepts_double_example_break(tmp_path: Path):
    card = _card()._replace(example="first example<br><br>second example")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok


def test_validate_build_result_requires_one_main_example_per_distinct_pos(
    tmp_path: Path,
):
    card = _card()._replace(
        pos="noun, verb",
        definition_vi="nghĩa",
        example="Only one example.",
        sense_pos="noun, verb",
        production_answer="word",
        oxford_pos_urls="|",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert any(
        issue.code == "main_example_pos_shortfall" for issue in report.issues
    )


def test_validate_build_result_counts_multiple_examples_in_one_merged_sense(
    tmp_path: Path,
):
    card = _card()._replace(
        pos="noun, verb",
        definition_vi="nghĩa",
        example="First example.<br><br>Second example.",
        sense_pos="noun, verb",
        production_answer="word",
        oxford_pos_urls="|",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok


def test_validate_build_result_accepts_aligned_collocation_provenance(
    tmp_path: Path,
):
    card = _card()._replace(
        collocations="on the curriculum|in the curriculum|curriculum development",
        collocation_sources="oxford|oxford+cambridge|curated",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(
        _result_with_audio([card], tmp_path), inputs, tmp_path
    )

    assert report.ok


def test_validate_build_result_rejects_invalid_collocation_contract(
    tmp_path: Path,
):
    card = _card()._replace(
        collocations=(
            "on/in the curriculum|on the curriculum|bad<br><br>markup|"
            "four|five|six"
        ),
        collocation_sources=(
            "oxford|oxford|curated|curated|unknown|cambridge"
        ),
        idioms="on the curriculum :: listed phrase",
        idiom_meaning_vi="bilingual_gloss :: nghĩa",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(
        _result_with_audio([card], tmp_path), inputs, tmp_path
    )

    codes = {issue.code for issue in report.issues}
    assert "collocation_limit_exceeded" in codes
    assert "source_collocation_slash_compression" in codes
    assert "collocation_invalid_text" in codes
    assert "collocation_source_invalid" in codes
    assert "collocation_duplicates_idiom" in codes


def test_validate_build_result_rejects_collocation_source_misalignment(
    tmp_path: Path,
):
    card = _card()._replace(
        collocations="first phrase|second phrase",
        collocation_sources="oxford",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(
        _result_with_audio([card], tmp_path), inputs, tmp_path
    )

    assert any(
        issue.code == "collocation_source_alignment_mismatch"
        for issue in report.issues
    )


def test_validate_build_result_rejects_misaligned_definition_vi(tmp_path: Path):
    card = _card()._replace(
        definition="first (một)|second (hai)",
        definition_vi="một",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(
        issue.code == "definition_vi_alignment_mismatch"
        for issue in report.issues
    )


def test_validate_build_result_accepts_pipe_aligned_sense_pos(tmp_path: Path):
    card = _card()._replace(
        pos="noun, verb",
        definition="first (một)|second (hai)",
        definition_vi="một|hai",
        example="First example.|Second example.",
        sense_pos="noun|verb",
        production_answer="word",
        oxford_pos_urls="|",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok


def test_validate_build_result_rejects_sense_pos_alignment_and_empty_cells(
    tmp_path: Path,
):
    card = _card()._replace(
        definition="first (một)|second (hai)",
        definition_vi="một|hai",
        example="First example.|Second example.",
        sense_pos="noun|",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert any(issue.code == "sense_pos_empty_cell" for issue in report.issues)

    misaligned = card._replace(sense_pos="noun")
    report = validate_build_result(
        _result_with_audio([misaligned], tmp_path), inputs, tmp_path
    )
    assert any(
        issue.code == "sense_pos_alignment_mismatch" for issue in report.issues
    )


def test_validate_build_result_rejects_sense_pos_outside_card_order(tmp_path: Path):
    card = _card()._replace(
        pos="noun, verb",
        definition_vi="nghĩa",
        sense_pos="verb, noun",
        oxford_pos_urls="|",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert any(issue.code == "sense_pos_invalid_cell" for issue in report.issues)


def test_validate_build_result_rejects_unrenderable_relation_metadata(tmp_path: Path):
    card = _card()._replace(example="The result was clear.", synonyms="plain")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(
        issue.code == "relation_metadata_unrepresented" for issue in report.issues
    )


def test_validate_build_result_accepts_idiom_only_card(tmp_path: Path):
    card = _card()._replace(
        definition="",
        example="",
        idioms="phrase :: meaning :: example",
        idiom_meaning_vi="bilingual_gloss :: nghĩa",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok


def test_multi_pos_idiom_only_card_is_exempt_from_main_example_cardinality(
    tmp_path: Path,
):
    card = _card()._replace(
        pos="noun, verb",
        definition="",
        definition_vi="",
        example="",
        sense_pos="",
        idioms="phrase :: meaning :: example",
        idiom_meaning_vi="bilingual_gloss :: nghĩa",
        oxford_pos_urls="|",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert report.ok


def test_idiom_example_does_not_satisfy_main_example_cardinality(tmp_path: Path):
    card = _card()._replace(
        pos="noun, verb",
        definition_vi="nghĩa",
        example="Only one main example.",
        sense_pos="noun, verb",
        production_answer="word",
        idioms="phrase :: meaning :: An idiom example.",
        idiom_meaning_vi="bilingual_gloss :: nghĩa",
        oxford_pos_urls="|",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert any(
        issue.code == "main_example_pos_shortfall" for issue in report.issues
    )


def test_validate_build_result_rejects_invalid_idiom_vi_contract(tmp_path: Path):
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    base = _card()._replace(idioms="phrase :: meaning")
    _write_registry(registry, [base])
    _write_jsonl(manual, [])
    inputs = load_registry_build_inputs(registry, manual)

    cases = {
        "": "idiom_meaning_vi_alignment_mismatch",
        "unknown :: nghĩa": "idiom_meaning_vi_invalid_mode",
        "bilingual_gloss": "idiom_meaning_vi_malformed_cell",
        "bilingual_gloss :: ": "idiom_meaning_vi_invalid_text",
    }
    for value, expected_code in cases.items():
        report = validate_build_result(
            _result_with_audio([base._replace(idiom_meaning_vi=value)], tmp_path),
            inputs,
            tmp_path,
        )
        assert any(issue.code == expected_code for issue in report.issues)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("definition_vi", "ngh?a bị lỗi"),
        ("definition_vi", "nghĩa bị \ufffd lỗi"),
        ("idiom_meaning_vi", "bilingual_gloss :: ho?n toàn"),
    ],
)
def test_validate_build_result_rejects_suspected_lossy_unicode(
    tmp_path: Path, field: str, value: str
):
    replacements = {field: value}
    if field == "definition_vi":
        replacements.update(sense_pos="noun", production_answer="word")
    else:
        replacements["idioms"] = "phrase :: meaning"
    card = _card()._replace(**replacements)
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert any(issue.code == "suspected_lossy_unicode" for issue in report.issues)


def test_validate_build_result_allows_terminal_question_punctuation(
    tmp_path: Path,
):
    card = _card()._replace(
        definition_vi="Tại sao?",
        sense_pos="noun",
        production_answer="word",
        idioms="phrase :: meaning",
        idiom_meaning_vi="bilingual_gloss :: Ai biết?",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not any(
        issue.code == "suspected_lossy_unicode" for issue in report.issues
    )


def test_validate_build_result_rejects_misaligned_oxford_pos_urls(tmp_path: Path):
    card = _card()._replace(pos="noun, verb", oxford_pos_urls="https://www.oxfordlearnersdictionaries.com/definition/english/word_1")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])
    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)
    assert any(issue.code == "oxford_pos_url_alignment_mismatch" for issue in report.issues)


def test_validate_build_result_requires_cambridge_url(tmp_path: Path):
    card = _card()._replace(cambridge_url="")
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])
    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)
    assert any(issue.code == "invalid_cambridge_url" for issue in report.issues)


def test_validate_build_result_rejects_more_than_two_idioms(tmp_path: Path):
    card = _card()._replace(
        idioms=(
            "first :: meaning :: example$$"
            "second :: meaning :: example$$"
            "third :: meaning :: example"
        ),
        idiom_meaning_vi=(
            "bilingual_gloss :: một$$bilingual_gloss :: hai$$"
            "bilingual_gloss :: ba"
        ),
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(issue.code == "idiom_limit_exceeded" for issue in report.issues)


def test_validate_build_result_rejects_more_than_one_example_per_idiom(tmp_path: Path):
    card = _card()._replace(
        idioms="phrase :: meaning :: First example.|Second example.",
        idiom_meaning_vi="bilingual_gloss :: nghĩa",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(
        issue.code == "idiom_example_limit_exceeded" for issue in report.issues
    )


def test_validate_build_result_rejects_duplicate_idiom_examples(tmp_path: Path):
    card = _card()._replace(
        idioms=(
            "first :: meaning :: Shared   sentence.$$"
            "second :: meaning :: shared sentence."
        ),
        idiom_meaning_vi=(
            "bilingual_gloss :: một$$bilingual_gloss :: hai"
        ),
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    report = validate_build_result(_result_with_audio([card], tmp_path), inputs, tmp_path)

    assert not report.ok
    assert any(issue.code == "idiom_example_duplicate" for issue in report.issues)


def test_validate_build_result_rejects_tampered_idiom_accent_audio(tmp_path: Path):
    card = _card()._replace(
        idioms="phrase :: meaning :: One example.",
        idiom_meaning_vi="bilingual_gloss :: nghĩa",
    )
    registry = tmp_path / "card_registry.jsonl"
    manual = tmp_path / "manual_cards.jsonl"
    _write_registry(registry, [card])
    _write_jsonl(manual, [])

    inputs = load_registry_build_inputs(registry, manual)
    result = _result_with_audio([card], tmp_path)
    tampered_cards = [result.built_cards[0]._replace(idiom_example_audio_uk="")]
    result = result._replace(
        built_cards=tampered_cards,
        jsonl_text=serialize_jsonl(tampered_cards),
        txt_text=serialize_txt(tampered_cards),
    )
    report = validate_build_result(result, inputs, tmp_path)

    assert not report.ok
    assert any(
        issue.code == "example_audio_alignment_mismatch" for issue in report.issues
    )


def test_validate_artifact_paths_rejects_txt_field_drift(tmp_path: Path):
    card = _card()
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [card])
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    parts = lines[len(CANONICAL_TXT_HEADER)].split("\t")
    parts[6] = "changed"
    lines[len(CANONICAL_TXT_HEADER)] = "\t".join(parts)
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code == "artifact_field_mismatch" for issue in report.issues)


def test_txt_parser_decodes_legacy_quoted_hash_guid():
    card = _card("P7#quoted")
    line = card.to_tsv()
    assert line.startswith("P7#quoted\t")
    legacy_line = '"P7#quoted"' + line[len("P7#quoted"):]

    cards, issues = _parse_txt_cards(
        "\n".join([*CANONICAL_TXT_HEADER, legacy_line]) + "\n",
        "legacy-export",
    )

    assert not issues
    assert cards == [card]


def test_txt_parser_backfills_pre_provenance_collocations_as_curated():
    card = _card()._replace(collocations="first phrase|second phrase")
    legacy_fields = card.to_tsv().split("\t")[:-1]

    cards, issues = _parse_txt_cards(
        "\n".join([*CANONICAL_TXT_HEADER, "\t".join(legacy_fields)]) + "\n",
        "legacy-export",
    )

    assert not issues
    assert cards == [card._replace(collocation_sources="curated|curated")]


def test_validate_artifact_paths_rejects_duplicate_guid(tmp_path: Path):
    first = _card("dup")
    second = _card("dup")._replace(word="word2")
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [first, second])

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code == "duplicate_guid" for issue in report.issues)


def test_validate_artifact_paths_rejects_missing_registry_card(tmp_path: Path):
    card = _card()
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [card])
    _write_jsonl(registry_path, [])

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code in {"unknown_registry_identity", "registry_coverage_order_mismatch"} for issue in report.issues)


def test_validate_artifact_paths_rejects_missing_audio(tmp_path: Path):
    card = _card(audio="[sound:missing.mp3]")
    jsonl_path, txt_path, registry_path, audio_dir = _write_artifacts(tmp_path, [card])

    report = validate_artifact_paths(jsonl_path, txt_path, registry_path, audio_dir)

    assert not report.ok
    assert any(issue.code == "audio_missing_reference" for issue in report.issues)
