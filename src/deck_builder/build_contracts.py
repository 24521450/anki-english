"""Shared build contracts for registry build, validation, and publishing."""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple


POS_NORM = {
    'n': 'noun', 'v': 'verb', 'adj': 'adjective', 'adv': 'adverb',
    'prep': 'preposition', 'pron': 'pronoun', 'det': 'determiner',
    'conj': 'conjunction', 'num': 'number', 'modal': 'modal',
    'predet': 'predeterminer', 'aux': 'auxiliary', 'exclam': 'exclamation',
    'abbr': 'abbreviation', 'exclamation': 'exclamation',
    'phrasal v': 'phrasal verb', 'phrasal verb': 'phrasal verb',
    'indefinite article': 'indefinite article', 'definite article': 'definite article',
    'number': 'number',
}

DEF_SEPARATOR = '|'
EX_SEP = '|'
COLL_SEPARATOR = '|'
MAX_IDIOMS_PER_CARD = 2
MAX_IDIOM_EXAMPLES_PER_IDIOM = 1

CANONICAL_TXT_HEADER: tuple[str, ...] = (
    "#separator:tab",
    "#html:true",
    "#guid column:1",
    "#notetype column:2",
    "#deck column:3",
    "#tags column:17",
)


class BuildNotesPaths(NamedTuple):
    oxford_jsonl_path: Path
    deck_audit_jsonl_path: Path
    gamma_verdicts_path: Path
    oxford_3000_md: Path
    oxford_5000_md: Path
    awl_md: Path
    audio_dir: Path
    card_registry_path: Path
    manual_cards_path: Path
    review_overrides_path: Path | None = None
    synonym_example_overrides_path: Path | None = None
    antonym_example_overrides_path: Path | None = None
    sense_label_overrides_path: Path | None = None
    semantic_registry_path: Path | None = None


class BuiltCard(NamedTuple):
    """One Anki note, encoded as the canonical TXT row.

    ``production_answer`` is appended after the established fields so the
    first 26 columns remain byte/position compatible with prior artifacts.
    """

    guid: str
    notetype: str
    deck: str
    word: str
    pos: str
    ipa: str
    definition: str
    example: str
    collocations: str
    wordfamily: str
    uk_audio: str
    us_audio: str
    source1: str
    source2: str
    cefr: str
    idioms: str
    tags: str
    synonyms: str
    antonyms: str
    example_audio_uk: str = ""
    example_audio_us: str = ""
    idiom_example_audio_uk: str = ""
    idiom_example_audio_us: str = ""
    definition_vi: str = ""
    cambridge_url: str = ""
    oxford_pos_urls: str = ""
    # Canonical answer used by Anki's native ``{{type:ProductionAnswer}}``
    # comparison on the sibling Vietnamese-to-English card.
    production_answer: str = ""

    def to_tsv(self) -> str:
        return '\t'.join([
            self.guid, self.notetype, self.deck, self.word, self.pos, self.ipa,
            self.definition, self.example, self.collocations, self.wordfamily,
            self.uk_audio, self.us_audio, self.source1, self.source2, self.cefr,
            self.idioms, self.tags, self.synonyms, self.antonyms,
            self.example_audio_uk, self.example_audio_us,
            self.idiom_example_audio_uk, self.idiom_example_audio_us,
            self.definition_vi,
            self.cambridge_url, self.oxford_pos_urls,
            self.production_answer,
        ])

    def to_dict(self) -> dict:
        return {
            'guid': self.guid,
            'notetype': self.notetype,
            'deck': self.deck,
            'word': self.word,
            'pos': self.pos,
            'ipa': self.ipa,
            'definition': self.definition,
            'example': self.example,
            'collocations': self.collocations,
            'wordfamily': self.wordfamily,
            'uk_audio': self.uk_audio,
            'us_audio': self.us_audio,
            'source1': self.source1,
            'source2': self.source2,
            'cefr': self.cefr,
            'idioms': self.idioms,
            'tags': self.tags,
            'synonyms': self.synonyms,
            'antonyms': self.antonyms,
            'example_audio_uk': self.example_audio_uk,
            'example_audio_us': self.example_audio_us,
            'idiom_example_audio_uk': self.idiom_example_audio_uk,
            'idiom_example_audio_us': self.idiom_example_audio_us,
            'definition_vi': self.definition_vi,
            'cambridge_url': self.cambridge_url,
            'oxford_pos_urls': self.oxford_pos_urls,
            'production_answer': self.production_answer,
        }


CARD_FIELDS: tuple[str, ...] = BuiltCard._fields


class BuildNotesResult(NamedTuple):
    built_cards: list[BuiltCard]
    jsonl_text: str
    txt_text: str
    type_a_count: int
    type_b_count: int
    type_c_count: int
    dup_emit_skip_count: int
    unclassified_drop_count: int
    built_cards_count: int
    missing_in_jsonl_count: int


def serialize_jsonl(cards) -> str:
    return "\n".join(json.dumps(card.to_dict(), ensure_ascii=False) for card in cards) + "\n"


def serialize_txt(cards) -> str:
    return "\n".join([*CANONICAL_TXT_HEADER, *(card.to_tsv() for card in cards)]) + "\n"
