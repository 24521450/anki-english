"""Pure support helpers for Anki note building."""
from __future__ import annotations

from src.deck_builder.audit_overrides import (
    load_audit_overrides as _load_audit_overrides,
    lookup_gloss,
)
from src.deck_builder.audio_resolution import (
    audio_dir_filenames as _audio_dir_filenames,
    resolve_audio_filename as _resolve_audio_filename,
)
from src.deck_builder.build_metadata import (
    deck_for_source as _deck_for_source,
    merge_collocations_dicts as _merge_collocations_dicts,
    new_guid as _new_guid,
    regenerate_tags as _regenerate_tags,
    source_label as _source_label,
)
from src.deck_builder.formatting import (
    format_audio as _format_audio,
    format_collocations as _format_collocations,
    format_examples as _format_examples,
    format_idioms as _format_idioms,
    format_ipa as _format_ipa,
    format_ipa_field as _format_ipa_field,
    format_wordfamily as _format_wordfamily,
    normalize_ipa as _normalize_ipa,
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

parse_vocab_list = _parse_vocab_list
resolve_audio_filename = _resolve_audio_filename
