"""Registry-driven shadow builder used during build-contract migration."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.deck_builder.build_contracts import (
    BuildNotesPaths,
    BuildNotesResult,
    BuiltCard,
    COLL_SEPARATOR,
    DEF_SEPARATOR,
    EX_SEP,
    serialize_jsonl,
    serialize_txt,
)
from src.deck_builder.build_issues import BuildIssue, BuildValidationError
from src.deck_builder.build_support import (
    _audio_dir_filenames,
    _build_source_label_specs_index,
    _format_examples,
    _format_idioms,
    _format_ipa_field,
    _get_senses_for_card,
    _get_source_label_specs_for_card,
    _load_audit_overrides,
    _load_gamma_verdicts,
    _parse_vocab_list,
    _regenerate_tags,
    _resolve_audio_filename,
    _simplify_with_gamma,
    _source_label,
    find_idioms_for_word,
    get_word_candidates,
    lookup_gloss,
    resolve_primary_record,
)
from src.deck_builder.card_identity import (
    CardIdentity,
    normalize_cefr,
    normalize_list_name,
    normalize_variant,
    normalize_word,
)
from src.deck_builder.card_registry import (
    load_jsonl as load_registry_jsonl,
    validate_registry_rows,
)
from src.deck_builder.manual_cards import (
    load_jsonl as load_manual_cards_jsonl,
    validate_manual_cards_rows,
)


@dataclass(frozen=True, slots=True)
class RegistryTarget:
    row: dict
    identity: CardIdentity


@dataclass(frozen=True, slots=True)
class RegistryBuildInputs:
    targets: list[RegistryTarget]
    registry_by_key: dict[tuple[str, str, str, str], RegistryTarget]
    manual_by_key: dict[tuple[str, str, str, str], dict]


def _row_identity(row: dict) -> CardIdentity:
    return CardIdentity(
        word=normalize_word(row.get("word")),
        cefr=normalize_cefr(row.get("cefr")),
        list=normalize_list_name(row.get("list"), canonical=True),
        variant=normalize_variant(row.get("variant")),
    )


def load_registry_build_inputs(
    registry_path: Path,
    manual_cards_path: Path,
) -> RegistryBuildInputs:
    """Load and cross-validate canonical registry/manual build inputs."""
    issues: list[BuildIssue] = []

    registry_rows = load_registry_jsonl(registry_path)
    issues.extend(validate_registry_rows(registry_rows))

    manual_rows = load_manual_cards_jsonl(manual_cards_path)
    issues.extend(validate_manual_cards_rows(manual_rows))

    registry_by_key: dict[tuple[str, str, str, str], RegistryTarget] = {}
    targets: list[RegistryTarget] = []
    for row in registry_rows:
        identity = _row_identity(row)
        target = RegistryTarget(row=row, identity=identity)
        registry_by_key[identity.as_key()] = target
        if row.get("status") == "active":
            targets.append(target)

    manual_by_key: dict[tuple[str, str, str, str], dict] = {}
    for row in manual_rows:
        identity = _row_identity(row)
        key = identity.as_key()
        target = registry_by_key.get(key)
        if target is None:
            issues.append(BuildIssue(
                severity="error",
                code="manual_unknown_registry_key",
                message=f"manual payload does not match a registry row: {key}",
                identity=identity,
                source=manual_cards_path,
            ))
        elif target.row.get("status") != "active":
            issues.append(BuildIssue(
                severity="error",
                code="manual_retired_registry_key",
                message=f"manual payload points at retired registry row: {key}",
                identity=identity,
                source=manual_cards_path,
            ))
        manual_by_key[key] = row

    if issues:
        raise BuildValidationError(issues)

    return RegistryBuildInputs(
        targets=targets,
        registry_by_key=registry_by_key,
        manual_by_key=manual_by_key,
    )


def _default_deck_for_registry(row: dict) -> str:
    if row.get("deck_override"):
        return row["deck_override"]
    list_name = normalize_list_name(row.get("list"), canonical=True)
    if list_name == "AWL":
        return "English Academic Vocabulary::AWL 50 Academic Words"
    return "English Academic Vocabulary::Oxford"


def _load_source_indexes(paths, gamma: dict):
    issues: list[BuildIssue] = []
    by_word: dict[str, list[dict]] = {}
    idioms_db: dict[str, list[tuple[dict, dict]]] = {}

    with paths.oxford_jsonl_path.open(encoding="utf-8") as source_file:
        for line_no, line in enumerate(source_file, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(BuildIssue(
                    severity="error",
                    code="source_json_malformed",
                    message=f"invalid JSONL row {line_no}: {exc}",
                    source=paths.oxford_jsonl_path,
                ))
                continue
            word = (record.get("word") or "").lower()
            if word:
                by_word.setdefault(word, []).append(record)
            for idiom in record.get("idioms") or []:
                phrase = idiom.get("phrase") or ""
                phrase_clean = re.sub(r"\s*\(.*?\)\s*", "", phrase.lower()).strip()
                if phrase_clean:
                    idioms_db.setdefault(phrase_clean, []).append((record, idiom))

    by_word_simplified: dict[str, list[tuple[dict, list]]] = {}
    for word_lower, records in by_word.items():
        items: list[tuple[dict, list]] = []
        for record in records:
            try:
                simplified = _simplify_with_gamma(record, gamma)
            except Exception as exc:  # pragma: no cover - exercised by corrupt sources
                issues.append(BuildIssue(
                    severity="error",
                    code="simplify_failed",
                    message=f"simplify failed for {word_lower!r}: {exc}",
                    source=paths.oxford_jsonl_path,
                ))
                continue
            if simplified:
                items.append((record, simplified))
        if items:
            by_word_simplified[word_lower] = items

    senses_index: dict[tuple[str, str, str], list] = {}
    sense_source_record: dict[tuple[str, str, str], dict] = {}
    for word_lower, items in by_word_simplified.items():
        for record, senses in items:
            for merged_sense in senses:
                cefr = merged_sense.cefr or "UNCLASSIFIED"
                key = (word_lower, merged_sense.pos, cefr)
                senses_index.setdefault(key, []).append(merged_sense)
                sense_source_record.setdefault(key, record)

    word_pos_set: dict[str, set[str]] = {}
    for word_lower, records in by_word.items():
        pos_set: set[str] = set()
        for record in records:
            for pos_data in record.get("pos_data", []) or []:
                pos = pos_data.get("pos")
                if pos:
                    pos_set.add(pos)
        word_pos_set[word_lower] = pos_set

    return {
        "issues": issues,
        "by_word": by_word,
        "idioms_db": idioms_db,
        "senses_index": senses_index,
        "sense_source_record": sense_source_record,
        "word_pos_set": word_pos_set,
        "source_label_specs_index": _build_source_label_specs_index(by_word),
    }


def _serialize_result(cards, *, counters: dict[str, int]):
    jsonl_text = serialize_jsonl(cards)
    txt_text = serialize_txt(cards)
    return BuildNotesResult(
        built_cards=cards,
        jsonl_text=jsonl_text,
        txt_text=txt_text,
        type_a_count=counters.get("type_a", 0),
        type_b_count=counters.get("type_b", 0),
        type_c_count=counters.get("type_c", 0),
        dup_emit_skip_count=counters.get("dup_emit_skip", 0),
        unclassified_drop_count=0,
        built_cards_count=len(cards),
        missing_in_jsonl_count=counters.get("missing", 0),
    )


def build_notes_from_registry(paths: BuildNotesPaths) -> BuildNotesResult:
    """Build cards from registry/manual inputs without reading generated outputs."""
    from src.deck_builder.corpus_tag_sync import apply_corpus_routing_and_tags
    from src.deck_builder.review_overrides import apply_review_overrides, load_review_overrides
    from src.deck_builder.sense_labels import apply_sense_labels, load_sense_label_overrides
    from src.deck_builder.simplify_senses import MergedSense
    from src.deck_builder.synonym_annotator import (
        annotate_card_examples,
        get_relation_specs_for_card,
        load_relation_overrides,
    )

    if paths.card_registry_path is None or paths.manual_cards_path is None:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="missing_registry_inputs",
                message="card_registry_path and manual_cards_path are required",
            )
        ])

    inputs = load_registry_build_inputs(paths.card_registry_path, paths.manual_cards_path)
    audio_files = _audio_dir_filenames(paths.audio_dir)
    review_overrides = load_review_overrides(getattr(paths, "review_overrides_path", None))
    vocab_3000 = _parse_vocab_list(paths.oxford_3000_md)
    vocab_5000 = _parse_vocab_list(paths.oxford_5000_md)
    vocab_awl = _parse_vocab_list(paths.awl_md)
    gamma = _load_gamma_verdicts(paths.gamma_verdicts_path)
    audit_glosses, audit_examples, audit_collocations = _load_audit_overrides(
        paths.deck_audit_jsonl_path
    )
    indexes = _load_source_indexes(paths, gamma)
    issues: list[BuildIssue] = list(indexes["issues"])
    by_word = indexes["by_word"]
    idioms_db = indexes["idioms_db"]
    senses_index = indexes["senses_index"]
    sense_source_record = indexes["sense_source_record"]
    word_pos_set = indexes["word_pos_set"]
    source_label_specs_index = indexes["source_label_specs_index"]

    cards: list[BuiltCard] = []
    counters = {"type_a": 0, "type_b": 0, "type_c": 0, "missing": 0}
    guid_to_relation_specs: dict[str, list[dict]] = {}
    manual_payload_by_guid: dict[str, dict] = {}

    for target in inputs.targets:
        row = target.row
        identity = target.identity
        key = identity.as_key()
        manual = inputs.manual_by_key.get(key)
        row_pos = (row.get("pos") or "").strip()
        if manual is not None:
            card = BuiltCard(
                guid=(row.get("guid") or "").strip(),
                notetype="English Academic Vocabulary Model",
                deck=_default_deck_for_registry(row),
                word=identity.word,
                pos=row_pos,
                ipa=manual.get("ipa") or "",
                definition=manual.get("definition") or "",
                example=manual.get("example") or "",
                collocations=manual.get("collocations") or "",
                wordfamily=manual.get("wordfamily") or "",
                uk_audio=manual.get("uk_audio") or "",
                us_audio=manual.get("us_audio") or "",
                source1=manual.get("source1") or "",
                source2=manual.get("source2") or "",
                cefr=identity.cefr,
                idioms=manual.get("idioms") or "",
                tags=manual.get("tags") or f"Source::{manual.get('source1') or 'Oxford'} CEFR::{identity.cefr} CEFR::oxford",
                synonyms=manual.get("synonyms") or "",
                antonyms=manual.get("antonyms") or "",
            )
            manual_payload_by_guid[card.guid] = manual
            guid_to_relation_specs[card.guid] = []
            cards.append(card)
            continue

        word_lower = identity.word.lower()
        pos_parts = [part.strip() for part in row_pos.split(",") if part.strip()]
        candidates = get_word_candidates(word_lower)
        matched_records: list[dict] = []
        resolved_word = word_lower
        for candidate in candidates:
            if candidate in by_word:
                matched_records = by_word[candidate]
                resolved_word = candidate
                break

        if not matched_records:
            issues.append(BuildIssue(
                severity="error",
                code="source_word_missing",
                message=f"no source record for registry word {identity.word!r}",
                identity=identity,
                source=paths.oxford_jsonl_path,
            ))
            counters["type_c"] += 1
            counters["missing"] += 1
            continue

        available_pos = word_pos_set.get(resolved_word, set())
        if any(pos in available_pos for pos in pos_parts):
            resolved_pos_parts = pos_parts
        else:
            resolved_pos_parts = []
            seen_pos: set[str] = set()
            for pos in pos_parts:
                if pos in available_pos and pos not in seen_pos:
                    resolved_pos_parts.append(pos)
                    seen_pos.add(pos)
                elif available_pos:
                    candidate_pos = next(iter(sorted(available_pos)))
                    if candidate_pos not in seen_pos:
                        resolved_pos_parts.append(candidate_pos)
                        seen_pos.add(candidate_pos)

        if resolved_word != word_lower:
            counters["type_b"] += 1
        elif resolved_pos_parts != pos_parts:
            counters["type_a"] += 1

        all_senses_for_row: list = []
        contributing_records: list[dict] = []
        for pos in resolved_pos_parts:
            sense_key = (resolved_word, pos, identity.cefr)
            if sense_key in senses_index:
                all_senses_for_row.extend(senses_index[sense_key])
                contributing_records.append(sense_source_record[sense_key])

        primary_record: dict | None = None
        if all_senses_for_row:
            primary_record = resolve_primary_record(matched_records, contributing_records)
        else:
            matched_idioms = find_idioms_for_word(candidates[0], idioms_db)
            if matched_idioms:
                idiom_record, idiom = matched_idioms[0]
                idiom_cefr = idiom.get("cefr") or "UNCLASSIFIED"
                if idiom_cefr == identity.cefr:
                    primary_record = idiom_record
                    all_senses_for_row = [
                        MergedSense(
                            pos=pos_parts[0],
                            cefr=idiom_cefr,
                            text=idiom.get("text") or "",
                            register_tags=[],
                            topics=[],
                            collocations={},
                            examples=[{"text": ex} for ex in idiom.get("examples") or []],
                            countability=None,
                            domain=None,
                            is_phrase=True,
                            is_idiom=True,
                            source_pdd_idx=[0],
                            source_def_idx=[0],
                            cefr_originals=[idiom_cefr],
                            cefr_sources=["idiom"],
                        )
                    ]

        if not all_senses_for_row:
            issues.append(BuildIssue(
                severity="error",
                code="source_exact_sense_missing",
                message=(
                    f"no exact source sense for {identity.word!r}, "
                    f"pos={row_pos!r}, cefr={identity.cefr!r}"
                ),
                identity=identity,
                source=paths.oxford_jsonl_path,
            ))
            counters["type_c"] += 1
            counters["missing"] += 1
            continue

        seen_texts: set[str] = set()
        senses = []
        for sense in all_senses_for_row:
            text = (sense.text or "").strip()
            if text and text not in seen_texts:
                seen_texts.add(text)
                senses.append(sense)
        if not senses:
            issues.append(BuildIssue(
                severity="error",
                code="source_empty_sense",
                message=f"exact source senses are empty for {identity.as_key()}",
                identity=identity,
                source=paths.oxford_jsonl_path,
            ))
            counters["type_c"] += 1
            counters["missing"] += 1
            continue

        new_cefr = senses[0].cefr or "UNCLASSIFIED"
        if new_cefr != identity.cefr:
            issues.append(BuildIssue(
                severity="error",
                code="cross_cefr_rejected",
                message=f"source CEFR {new_cefr!r} does not match registry CEFR {identity.cefr!r}",
                identity=identity,
                source=paths.oxford_jsonl_path,
            ))
            continue

        record = primary_record or {}
        definition = DEF_SEPARATOR.join((sense.text or "") for sense in senses if (sense.text or ""))
        gloss = lookup_gloss(audit_glosses, word_lower, row_pos, identity.cefr, resolved_word, resolved_pos_parts, new_cefr)
        if gloss is not None:
            definition = gloss
        example = EX_SEP.join(_format_examples(sense.examples or []) for sense in senses)
        example_override = lookup_gloss(audit_examples, word_lower, row_pos, identity.cefr, resolved_word, resolved_pos_parts, new_cefr)
        if example_override is not None:
            example = example_override
        collocations = ""
        coll_override = lookup_gloss(audit_collocations, word_lower, row_pos, identity.cefr, resolved_word, resolved_pos_parts, new_cefr)
        if coll_override is not None:
            collocations = coll_override

        ipa = _format_ipa_field(record.get("uk_ipa"), record.get("us_ipa"))
        if not ipa:
            for candidate_record in by_word.get(resolved_word, []):
                if candidate_record is record:
                    continue
                uk_ipa = candidate_record.get("uk_ipa")
                us_ipa = candidate_record.get("us_ipa")
                if uk_ipa or us_ipa:
                    ipa = _format_ipa_field(uk_ipa, us_ipa)
                    break

        uk_audio = _resolve_audio_filename(resolved_word, row_pos, "uk", audio_files)
        us_audio = _resolve_audio_filename(resolved_word, row_pos, "us", audio_files)
        source1 = _source_label(record.get("source_files") or [])
        resolved_pos = resolved_pos_parts[0] if resolved_pos_parts else pos_parts[0]
        is_in_3000 = (resolved_word, resolved_pos, new_cefr) in vocab_3000
        is_in_5000 = (resolved_word, resolved_pos, new_cefr) in vocab_5000
        is_in_awl = (
            (resolved_word, resolved_pos, new_cefr) in vocab_awl
            or (
                resolved_word == "converse"
                and new_cefr == "UNCLASSIFIED"
                and identity.list == "AWL"
            )
        )

        audio_source = source1
        for accent in ("uk", "us"):
            url = (record.get("audio") or {}).get(accent) or ""
            if "cambridge" in str(url).lower():
                audio_source = "Cambridge"
                break

        tags = _regenerate_tags(
            word=resolved_word,
            pos=resolved_pos,
            cefr=new_cefr,
            source1=source1,
            audio_source=audio_source,
            has_idioms=bool(record.get("idioms")),
            oxford_lists=record.get("oxford_lists") or [],
            opal=record.get("opal"),
            awl_flag=is_in_awl,
            is_in_vocab_3000=is_in_3000,
            is_in_vocab_5000=is_in_5000,
        )

        specs = []
        for sense in senses:
            if getattr(sense, "relation_specs", None):
                specs.extend(sense.relation_specs)

        guid = (row.get("guid") or "").strip()
        guid_to_relation_specs[guid] = specs
        cards.append(BuiltCard(
            guid=guid,
            notetype="English Academic Vocabulary Model",
            deck=_default_deck_for_registry(row),
            word=identity.word,
            pos=", ".join(resolved_pos_parts) if resolved_pos_parts else row_pos,
            ipa=ipa,
            definition=definition,
            example=example,
            collocations=collocations,
            wordfamily="",
            uk_audio=uk_audio,
            us_audio=us_audio,
            source1=source1,
            source2="AWL" if is_in_awl else "Oxford",
            cefr=new_cefr,
            idioms=_format_idioms(record.get("idioms") or []),
            tags=tags,
            synonyms="",
            antonyms="",
        ))

    if issues:
        raise BuildValidationError(issues)

    cards = apply_review_overrides(cards, review_overrides)

    sense_label_overrides_file = getattr(paths, "sense_label_overrides_path", None)
    sense_label_overrides = load_sense_label_overrides(sense_label_overrides_file)
    guid_to_senses = {card.guid: _get_senses_for_card(card, senses_index) for card in cards}
    guid_to_source_label_specs = {
        card.guid: _get_source_label_specs_for_card(card, source_label_specs_index)
        for card in cards
    }
    cards, sense_label_errors = apply_sense_labels(
        cards,
        guid_to_senses,
        sense_label_overrides,
        guid_to_source_label_specs,
    )
    if sense_label_errors:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="sense_label_failed",
                message=message,
            )
            for message in sense_label_errors
        ])

    if manual_payload_by_guid:
        restored_cards = []
        for card in cards:
            manual = manual_payload_by_guid.get(card.guid)
            if manual is None:
                restored_cards.append(card)
                continue
            restored_cards.append(card._replace(
                definition=manual.get("definition") or "",
                example=manual.get("example") or "",
                collocations=manual.get("collocations") or "",
                wordfamily=manual.get("wordfamily") or "",
                ipa=manual.get("ipa") or "",
                uk_audio=manual.get("uk_audio") or "",
                us_audio=manual.get("us_audio") or "",
                source1=manual.get("source1") or "",
                source2=manual.get("source2") or "",
                idioms=manual.get("idioms") or "",
                tags=manual.get("tags") or card.tags,
                synonyms=manual.get("synonyms") or "",
                antonyms=manual.get("antonyms") or "",
            ))
        cards = restored_cards

    synonym_overrides_file = getattr(paths, "synonym_example_overrides_path", None)
    antonym_overrides_file = getattr(paths, "antonym_example_overrides_path", None)
    synonym_overrides = load_relation_overrides(synonym_overrides_file)
    antonym_overrides = load_relation_overrides(antonym_overrides_file)
    annotated_cards = []
    annotation_errors: list[str] = []
    for card in cards:
        if card.guid in manual_payload_by_guid:
            annotated_cards.append(card)
            continue
        specs = guid_to_relation_specs.get(card.guid)
        if specs is None:
            specs = get_relation_specs_for_card(card, senses_index)
        annotated_example, synonyms, antonyms, errors = annotate_card_examples(
            card,
            specs,
            synonym_overrides,
            antonym_overrides,
        )
        annotation_errors.extend(errors)
        annotated_cards.append(card._replace(
            example=annotated_example,
            synonyms=synonyms,
            antonyms=antonyms,
        ))

    built_guids = {card.guid for card in cards}
    for label, overrides in (("synonym", synonym_overrides), ("antonym", antonym_overrides)):
        unknown_guids = set(overrides.keys()) - built_guids
        if unknown_guids:
            annotation_errors.append(
                f"Unknown card GUIDs defined in {label} overrides: {sorted(unknown_guids)}"
            )

    if annotation_errors:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="relation_annotation_failed",
                message=message,
            )
            for message in annotation_errors
        ])

    cards = apply_corpus_routing_and_tags(annotated_cards, vocab_3000, vocab_5000, vocab_awl)
    return _serialize_result(cards, counters=counters)
