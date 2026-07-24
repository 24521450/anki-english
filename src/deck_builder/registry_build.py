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
from src.deck_builder.audio_resolution import (
    audio_dir_filenames as _audio_dir_filenames,
    resolve_audio_filename as _resolve_audio_filename,
)
from src.deck_builder.audit_overrides import (
    find_cross_cefr_override_examples,
    load_audit_overrides as _load_audit_overrides,
    lookup_gloss,
)
from src.deck_builder.build_metadata import (
    regenerate_tags as _regenerate_tags,
    source_label as _source_label,
    sync_idioms_feature_tag,
    sync_semantic_identity_tag,
)
from src.deck_builder.deck_names import AWL_DECK
from src.deck_builder.build_issues import BuildIssue, BuildValidationError
from src.deck_builder.example_audio import plan_cards_example_audio
from src.deck_builder.dictionary_links import OxfordLinkIndex, cambridge_url
from src.deck_builder.formatting import (
    format_examples as _format_examples,
    format_idioms as _format_idioms,
    format_ipa_field as _format_ipa_field,
)
from src.deck_builder.gamma_support import (
    load_gamma_verdicts as _load_gamma_verdicts,
    simplify_with_gamma as _simplify_with_gamma,
)
from src.deck_builder.source_label_specs import (
    build_source_label_specs_index as _build_source_label_specs_index,
    get_source_label_specs_for_card as _get_source_label_specs_for_card,
)
from src.deck_builder.vocab_lists import parse_vocab_list as _parse_vocab_list
from src.deck_builder.word_lookup import (
    find_idioms_for_word,
    get_senses_for_card as _get_senses_for_card,
    get_word_candidates,
    resolve_primary_record,
)
from src.deck_builder.production import apply_production_answers
from src.deck_builder.sense_pos import build_source_sense_pos_index
from src.deck_builder.simplify_senses import _flatten_senses
from src.deck_builder.source_sense_identity import source_sense_id
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
from src.deck_builder.opal_tags import apply_opal_tags, build_opal_index
from src.deck_builder.pronunciation_resolution import (
    PronunciationRequest,
    PronunciationResolutionError,
    bind_headword_audio_manifest,
    index_headword_audio_manifest,
    index_pronunciation_records,
    index_pronunciation_locks,
    normalize_source_word,
    select_pronunciation,
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
        return AWL_DECK
    return "English Academic Vocabulary::Oxford"


def _load_source_indexes(paths, gamma: dict):
    issues: list[BuildIssue] = []
    by_word: dict[str, list[dict]] = {}
    idioms_db: dict[str, list[tuple[dict, dict]]] = {}
    source_records: list[dict] = []

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
            source_records.append(record)
            for idiom in record.get("idioms") or []:
                phrase = idiom.get("phrase") or ""
                phrase_clean = re.sub(r"\s*\(.*?\)\s*", "", phrase.lower()).strip()
                if phrase_clean:
                    idioms_db.setdefault(phrase_clean, []).append((record, idiom))

    cambridge_path = getattr(paths, "cambridge_jsonl_path", None)
    if cambridge_path is not None:
        try:
            with cambridge_path.open(encoding="utf-8") as source_file:
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
                            source=cambridge_path,
                        ))
                        continue
                    if not isinstance(record, dict):
                        issues.append(BuildIssue(
                            severity="error",
                            code="source_json_invalid_row",
                            message=f"JSONL row {line_no} must be an object",
                            source=cambridge_path,
                        ))
                        continue
                    source_records.append(record)
        except OSError as exc:
            issues.append(BuildIssue(
                severity="error",
                code="source_json_unreadable",
                message=f"cannot read Cambridge source JSONL: {exc}",
                source=cambridge_path,
            ))

    try:
        source_sense_pos_index = build_source_sense_pos_index(source_records)
    except (KeyError, TypeError, ValueError) as exc:
        issues.append(BuildIssue(
            severity="error",
            code="source_sense_pos_index_failed",
            message=str(exc),
        ))
        source_sense_pos_index = {}

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
    sense_source_ids: dict[int, set[str]] = {}
    sense_source_record_by_id: dict[int, dict] = {}
    for word_lower, items in by_word_simplified.items():
        for record, senses in items:
            source_id_by_location = {
                (flat_sense.pd_idx, flat_sense.def_idx): source_sense_id(
                    record, flat_sense
                )
                for flat_sense in _flatten_senses(record)
            }
            for merged_sense in senses:
                cefr = merged_sense.cefr or "UNCLASSIFIED"
                key = (word_lower, merged_sense.pos, cefr)
                senses_index.setdefault(key, []).append(merged_sense)
                sense_source_record.setdefault(key, record)
                sense_source_ids[id(merged_sense)] = {
                    source_id_by_location[location]
                    for location in zip(
                        merged_sense.source_pdd_idx,
                        merged_sense.source_def_idx,
                    )
                    if location in source_id_by_location
                }
                sense_source_record_by_id[id(merged_sense)] = record

    word_pos_set: dict[str, set[str]] = {}
    for word_lower, records in by_word.items():
        pos_set: set[str] = set()
        for record in records:
            for pos_data in record.get("pos_data", []) or []:
                pos = pos_data.get("pos")
                if pos:
                    pos_set.add(pos)
        word_pos_set[word_lower] = pos_set

    try:
        opal_index = build_opal_index(
            record
            for records in by_word.values()
            for record in records
        )
    except (TypeError, ValueError) as exc:
        issues.append(BuildIssue(
            severity="error",
            code="opal_source_index_failed",
            message=str(exc),
            source=paths.oxford_jsonl_path,
        ))
        opal_index = {}

    return {
        "issues": issues,
        "source_records": source_records,
        "by_word": by_word,
        "idioms_db": idioms_db,
        "senses_index": senses_index,
        "sense_source_record": sense_source_record,
        "sense_source_ids": sense_source_ids,
        "sense_source_record_by_id": sense_source_record_by_id,
        "word_pos_set": word_pos_set,
        "opal_index": opal_index,
        "source_label_specs_index": _build_source_label_specs_index(by_word),
        "source_sense_pos_index": source_sense_pos_index,
    }


def _semantic_cefr_fallback_senses(
    senses: list,
    *,
    semantic_source_ids: set[str],
    source_ids_by_sense: dict[int, set[str]],
    reviewed_cefr: str,
) -> list:
    """Use an unbadged exact source sense only when Semantic Registry owns it."""
    return [
        sense._replace(cefr=reviewed_cefr)
        for sense in senses
        if semantic_source_ids & source_ids_by_sense.get(id(sense), set())
    ]


def _sync_audio_source_tags(
    tags: str,
    source1: str,
    selected_sources: list[str],
) -> str:
    tokens = [token for token in tags.split() if not token.startswith("Audio::")]
    source1_key = source1.casefold()
    seen: set[str] = set()
    for source in selected_sources:
        label = source.capitalize()
        if source.casefold() == source1_key or label in seen:
            continue
        seen.add(label)
        tokens.append(f"Audio::{label}")
    return " ".join(tokens)


def _apply_pronunciation_authorities(
    cards: list[BuiltCard],
    *,
    source_records: list[dict],
    locks_path: Path,
    manifest_path: Path,
    audio_dir: Path,
) -> list[BuiltCard]:
    """Resolve IPA/media only from entry-scoped evidence and bound media."""
    try:
        locks = index_pronunciation_locks(load_registry_jsonl(locks_path))
        manifest = index_headword_audio_manifest(
            load_registry_jsonl(manifest_path),
            audio_dir=audio_dir,
        )
        records_by_word = index_pronunciation_records(source_records)
    except (OSError, json.JSONDecodeError, PronunciationResolutionError) as exc:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="pronunciation_authority_invalid",
                message=str(exc),
                source=manifest_path if manifest_path.exists() else locks_path,
            )
        ]) from exc

    # Authorities are release inputs, not an append-only cache.  Reject rows
    # that cannot be reached from the active Card Registry before resolving
    # cards; otherwise a retired GUID or stale media row could silently remain
    # trusted forever.  The same exact-coverage check is repeated for selected
    # fingerprints below so a manifest cannot contain an unreferenced entry.
    active_keys = {
        (card.guid, accent)
        for card in cards
        for accent in ("uk", "us")
    }
    extra_lock_keys = sorted(set(locks) - active_keys)
    if extra_lock_keys:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="pronunciation_authority_invalid",
                message=(
                    "pronunciation locks contain inactive GUID/accent rows: "
                    + ", ".join(f"{guid}:{accent}" for guid, accent in extra_lock_keys[:20])
                ),
                source=locks_path,
            )
        ])

    resolved_cards: list[BuiltCard] = []
    issues: list[BuildIssue] = []
    used_lock_keys: set[tuple[str, str]] = set()
    used_manifest_fingerprints: set[str] = set()
    for card in cards:
        request = PronunciationRequest(
            guid=card.guid,
            word=card.word,
            pos=card.pos,
        )
        resolved = {}
        try:
            for accent in ("uk", "us"):
                lock_key = (card.guid, accent)
                lock = locks.get(lock_key)
                if lock is not None:
                    used_lock_keys.add(lock_key)
                lookup_word = (
                    str(lock.get("source_word") or "")
                    if lock is not None and "source_word" in lock
                    else card.word
                )
                selection = select_pronunciation(
                    request,
                    accent,
                    records_by_word.get(normalize_source_word(lookup_word), ()),
                    lock,
                )
                resolved[accent] = bind_headword_audio_manifest(selection, manifest)
                if not selection.no_pronunciation:
                    candidate = selection.candidate
                    if candidate is None:
                        raise PronunciationResolutionError(
                            "selected pronunciation has no candidate"
                        )
                    used_manifest_fingerprints.add(candidate.fingerprint)
        except PronunciationResolutionError as exc:
            issues.append(BuildIssue(
                severity="error",
                code="pronunciation_resolution_failed",
                message=f"{card.guid} ({card.word}): {exc}",
            ))
            continue

        uk = resolved["uk"]
        us = resolved["us"]
        selected_sources = [
            item.source for item in (uk, us) if not item.no_pronunciation
        ]
        resolved_cards.append(card._replace(
            ipa=_format_ipa_field(uk.ipa, us.ipa),
            uk_audio=(f"[sound:{uk.media_filename}]" if uk.media_filename else ""),
            us_audio=(f"[sound:{us.media_filename}]" if us.media_filename else ""),
            tags=_sync_audio_source_tags(card.tags, card.source1, selected_sources),
        ))

    if issues:
        raise BuildValidationError(issues)

    # Every manifest row must be consumed by one of the active requests.  A
    # candidate may legitimately be shared by several cards, so this compares
    # fingerprints rather than card counts.  Keep this check after resolution
    # to avoid masking the more actionable stale-lock error above.
    extra_manifest_fingerprints = sorted(
        set(manifest) - used_manifest_fingerprints
    )
    if extra_manifest_fingerprints:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="pronunciation_authority_invalid",
                message=(
                    "headword audio manifest contains unselected rows: "
                    + ", ".join(extra_manifest_fingerprints[:20])
                ),
                source=manifest_path,
            )
        ])

    # This is intentionally an assertion-like guard rather than a count
    # comparison: a lock row is consumed only when its exact GUID/accent was
    # resolved, and duplicate rows are already rejected by the indexer.
    if used_lock_keys != set(locks):
        missing_lock_keys = sorted(set(locks) - used_lock_keys)
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="pronunciation_authority_invalid",
                message=(
                    "pronunciation lock rows were not resolved: "
                    + ", ".join(f"{guid}:{accent}" for guid, accent in missing_lock_keys[:20])
                ),
                source=locks_path,
            )
        ])
    return resolved_cards


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


def build_notes_from_registry(
    paths: BuildNotesPaths,
    *,
    apply_semantic_payload: bool = True,
) -> BuildNotesResult:
    """Build cards from registry/manual inputs without reading generated outputs.

    ``apply_semantic_payload=False`` is reserved for canonical audit writers
    that need the current source-owned idiom text before learner-facing
    Semantic Registry rewrites.
    """
    from src.deck_builder.corpus_tag_sync import apply_corpus_routing_and_tags
    from src.deck_builder.collocation_audit import (
        apply_collocation_registry,
        load_collocation_registry,
    )
    from src.deck_builder.review_overrides import apply_review_overrides, load_review_overrides
    from src.deck_builder.relation_validation import validate_lexical_relation_metadata
    from src.deck_builder.sense_labels import apply_sense_labels, load_sense_label_overrides
    from src.deck_builder.semantic_registry import (
        apply_variant_idiom_ownership,
        apply_semantic_registry,
        validate_semantic_registry_rows,
    )
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
    collocation_registry_rows: list[dict] | None = None
    collocation_registry_path = getattr(paths, "collocation_registry_path", None)
    if collocation_registry_path is not None:
        try:
            collocation_registry_rows = load_collocation_registry(
                collocation_registry_path,
                [target.row for target in inputs.targets],
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise BuildValidationError([
                BuildIssue(
                    severity="error",
                    code="collocation_registry_invalid",
                    message=str(exc),
                    source=collocation_registry_path,
                )
            ]) from exc
    semantic_registry_rows: list[dict] | None = None
    semantic_registry_path = getattr(paths, "semantic_registry_path", None)
    if semantic_registry_path is not None:
        try:
            semantic_registry_rows = load_registry_jsonl(semantic_registry_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise BuildValidationError([
                BuildIssue(
                    severity="error",
                    code="semantic_registry_load_failed",
                    message=str(exc),
                    source=semantic_registry_path,
                )
            ]) from exc
        try:
            semantic_errors = validate_semantic_registry_rows(
                semantic_registry_rows,
                [target.row for target in inputs.targets],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BuildValidationError([
                BuildIssue(
                    severity="error",
                    code="semantic_registry_invalid",
                    message=str(exc),
                    source=semantic_registry_path,
                )
            ]) from exc
        if semantic_errors:
            raise BuildValidationError([
                BuildIssue(
                    severity="error",
                    code="semantic_registry_invalid",
                    message=message,
                    source=semantic_registry_path,
                )
                for message in semantic_errors
            ])
    pronunciation_locks_path = getattr(
        paths, "pronunciation_selection_locks_path", None
    )
    headword_audio_manifest_path = getattr(
        paths, "headword_audio_manifest_path", None
    )
    allow_legacy_pronunciation = bool(getattr(
        paths, "allow_legacy_pronunciation_for_tests", False
    ))
    has_pronunciation_authorities = (
        pronunciation_locks_path is not None
        and headword_audio_manifest_path is not None
    )
    if not has_pronunciation_authorities and not allow_legacy_pronunciation:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="pronunciation_authority_incomplete",
                message=(
                    "pronunciation_selection_locks_path and "
                    "headword_audio_manifest_path are required"
                ),
            )
        ])
    audio_files = (
        _audio_dir_filenames(paths.audio_dir)
        if allow_legacy_pronunciation
        else set()
    )
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
    source_records = indexes["source_records"]
    idioms_db = indexes["idioms_db"]
    senses_index = indexes["senses_index"]
    sense_source_record = indexes["sense_source_record"]
    sense_source_ids = indexes["sense_source_ids"]
    sense_source_record_by_id = indexes["sense_source_record_by_id"]
    word_pos_set = indexes["word_pos_set"]
    opal_index = indexes["opal_index"]
    source_label_specs_index = indexes["source_label_specs_index"]
    source_sense_pos_index = indexes["source_sense_pos_index"]
    oxford_link_index = OxfordLinkIndex(by_word)
    semantic_source_ids_by_guid = {
        row.get("guid", ""): {
            source_id
            for sense in row.get("senses") or []
            for source_id in sense.get("source_sense_ids") or []
        }
        for row in semantic_registry_rows or []
    }

    audit_rows = []
    if paths.deck_audit_jsonl_path and paths.deck_audit_jsonl_path.exists():
        audit_rows = [
            json.loads(line)
            for line in paths.deck_audit_jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    manual_keys = set(inputs.manual_by_key)
    active_non_manual_cards = {
        (
            target.identity.word.lower(),
            (target.row.get("pos") or "").strip().lower(),
            target.identity.cefr,
        )
        for target in inputs.targets
        if target.identity.as_key() not in manual_keys
    }
    for issue in find_cross_cefr_override_examples(
        audit_rows,
        by_word,
        active_non_manual_cards=active_non_manual_cards,
    ):
        issues.append(BuildIssue(
            severity="error",
            code="cross_cefr_audit_override_example",
            message=(
                f"curated example {issue['example']!r} for {issue['word']!r} "
                f"{issue['pos']!r} {issue['cefr']} comes from source sense "
                f"{issue['sense_number']!r} assigned to {issue['assigned_cefr']}"
            ),
            source=paths.deck_audit_jsonl_path,
        ))

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
        pos_parts = [part.strip() for part in row_pos.split(",") if part.strip()]
        if manual is not None:
            candidates = get_word_candidates(identity.word.casefold())
            resolved_word = next((candidate for candidate in candidates if candidate in by_word), candidates[0])
            card = BuiltCard(
                guid=(row.get("guid") or "").strip(),
                notetype="English Academic Vocabulary Model",
                deck=_default_deck_for_registry(row),
                word=identity.word,
                pos=row_pos,
                ipa=(manual.get("ipa") or "") if allow_legacy_pronunciation else "",
                definition=manual.get("definition") or "",
                example=manual.get("example") or "",
                collocations=manual.get("collocations") or "",
                wordfamily=manual.get("wordfamily") or "",
                uk_audio=(manual.get("uk_audio") or "") if allow_legacy_pronunciation else "",
                us_audio=(manual.get("us_audio") or "") if allow_legacy_pronunciation else "",
                source1=manual.get("source1") or "",
                source2=manual.get("source2") or "",
                cefr=identity.cefr,
                idioms=manual.get("idioms") or "",
                tags=manual.get("tags") or f"Source::{manual.get('source1') or 'Oxford'} CEFR::{identity.cefr} CEFR::oxford",
                synonyms=manual.get("synonyms") or "",
                antonyms=manual.get("antonyms") or "",
                cambridge_url=cambridge_url(resolved_word),
                oxford_pos_urls=oxford_link_index.aligned_urls(
                    resolved_word,
                    pos_parts,
                    semantic_source_ids_by_guid.get((row.get("guid") or "").strip(), set()),
                ),
            )
            manual_payload_by_guid[card.guid] = manual
            guid_to_relation_specs[card.guid] = []
            cards.append(card)
            continue

        word_lower = identity.word.lower()
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
        reviewed_source_ids = semantic_source_ids_by_guid.get(
            (row.get("guid") or "").strip(), set()
        )
        for pos in resolved_pos_parts:
            sense_key = (resolved_word, pos, identity.cefr)
            if sense_key in senses_index:
                all_senses_for_row.extend(senses_index[sense_key])
                contributing_records.append(sense_source_record[sense_key])
                continue
            fallback_candidates = senses_index.get(
                (resolved_word, pos, "UNCLASSIFIED"), []
            )
            fallback_senses = _semantic_cefr_fallback_senses(
                fallback_candidates,
                semantic_source_ids=reviewed_source_ids,
                source_ids_by_sense=sense_source_ids,
                reviewed_cefr=identity.cefr,
            )
            all_senses_for_row.extend(fallback_senses)
            contributing_records.extend(
                sense_source_record_by_id[id(sense)]
                for sense in fallback_candidates
                if reviewed_source_ids & sense_source_ids.get(id(sense), set())
            )

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

        ipa = (
            _format_ipa_field(record.get("uk_ipa"), record.get("us_ipa"))
            if allow_legacy_pronunciation
            else ""
        )
        if allow_legacy_pronunciation and not ipa:
            for candidate_record in by_word.get(resolved_word, []):
                if candidate_record is record:
                    continue
                uk_ipa = candidate_record.get("uk_ipa")
                us_ipa = candidate_record.get("us_ipa")
                if uk_ipa or us_ipa:
                    ipa = _format_ipa_field(uk_ipa, us_ipa)
                    break

        uk_audio = (
            _resolve_audio_filename(resolved_word, row_pos, "uk", audio_files)
            if allow_legacy_pronunciation
            else ""
        )
        us_audio = (
            _resolve_audio_filename(resolved_word, row_pos, "us", audio_files)
            if allow_legacy_pronunciation
            else ""
        )
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
        if allow_legacy_pronunciation:
            for accent in ("uk", "us"):
                url = (record.get("audio") or {}).get(accent) or ""
                if "cambridge" in str(url).lower():
                    audio_source = "Cambridge"
                    break

        formatted_idioms = _format_idioms(
            record.get("idioms") or [],
            card_pos=resolved_pos_parts,
        )
        tags = _regenerate_tags(
            word=resolved_word,
            pos=resolved_pos,
            cefr=new_cefr,
            source1=source1,
            audio_source=audio_source,
            has_idioms=bool(formatted_idioms),
            oxford_lists=record.get("oxford_lists") or [],
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
            idioms=formatted_idioms,
            tags=tags,
            synonyms="",
            antonyms="",
            cambridge_url=cambridge_url(resolved_word),
            oxford_pos_urls=oxford_link_index.aligned_urls(
                resolved_word,
                resolved_pos_parts if resolved_pos_parts else pos_parts,
                semantic_source_ids_by_guid.get(guid, set()),
            ),
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
                ipa=(manual.get("ipa") or "") if allow_legacy_pronunciation else "",
                uk_audio=(manual.get("uk_audio") or "") if allow_legacy_pronunciation else "",
                us_audio=(manual.get("us_audio") or "") if allow_legacy_pronunciation else "",
                source1=manual.get("source1") or "",
                source2=manual.get("source2") or "",
                idioms=manual.get("idioms") or "",
                tags=manual.get("tags") or card.tags,
                synonyms=manual.get("synonyms") or "",
                antonyms=manual.get("antonyms") or "",
            ))
        cards = restored_cards

    if semantic_registry_rows is not None:
        try:
            cards = apply_variant_idiom_ownership(cards, semantic_registry_rows)
            if apply_semantic_payload:
                cards = apply_semantic_registry(
                    cards,
                    semantic_registry_rows,
                    source_sense_pos_index,
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise BuildValidationError([
                BuildIssue(
                    severity="error",
                    code="semantic_registry_apply_failed",
                    message=str(exc),
                    source=semantic_registry_path,
                )
            ]) from exc
        if apply_semantic_payload:
            cards = [
                card._replace(synonyms="", antonyms="")
                if (
                    card.guid in manual_payload_by_guid
                    and validate_lexical_relation_metadata(
                        card.example,
                        card.synonyms,
                        card.antonyms,
                    )
                )
                else card
                for card in cards
            ]

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
            require_source_alignment=semantic_registry_rows is None,
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
    try:
        cards = apply_opal_tags(cards, opal_index)
    except ValueError as exc:
        raise BuildValidationError([
            BuildIssue(
                severity="error",
                code="opal_tag_resolution_failed",
                message=str(exc),
                source=paths.oxford_jsonl_path,
            )
        ]) from exc
    if collocation_registry_rows is not None:
        try:
            cards = apply_collocation_registry(cards, collocation_registry_rows)
        except (KeyError, TypeError, ValueError) as exc:
            raise BuildValidationError([
                BuildIssue(
                    severity="error",
                    code="collocation_registry_apply_failed",
                    message=str(exc),
                    source=collocation_registry_path,
                )
            ]) from exc
    if has_pronunciation_authorities:
        assert pronunciation_locks_path is not None
        assert headword_audio_manifest_path is not None
        cards = _apply_pronunciation_authorities(
            cards,
            source_records=source_records,
            locks_path=pronunciation_locks_path,
            manifest_path=headword_audio_manifest_path,
            audio_dir=paths.audio_dir,
        )
    registry_by_guid = {
        str(target.row.get("guid") or ""): target.row
        for target in inputs.targets
    }
    cards = [
        card._replace(
            tags=sync_idioms_feature_tag(
                sync_semantic_identity_tag(
                    card.tags,
                    registry_by_guid[card.guid],
                ),
                card.idioms,
            )
        )
        for card in cards
    ]
    cards, _ = plan_cards_example_audio(cards)
    # ProductionAnswer is derived only after semantic-registry, review,
    # relation, corpus, and audio transforms have completed.  This keeps the
    # field deterministic while ensuring every emitted card uses its final
    # displayed Word value (including reviewed identity changes).
    cards = apply_production_answers(cards)
    return _serialize_result(cards, counters=counters)
