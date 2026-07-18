"""Stable machine-readable contract for the generated EAVM note type."""
from __future__ import annotations

from importlib.metadata import version


PACKAGER_CONTRACT_SCHEMA_VERSION = 2
EAVM_MODEL_NAME = "English Academic Vocabulary Model"
EAVM_MODEL_ID = 1607392819
EAVM_JSON_TO_FIELD: tuple[tuple[str, str], ...] = (
    ("word", "Word"),
    ("pos", "PartOfSpeech"),
    ("ipa", "IPA"),
    ("definition", "Definition"),
    ("example", "Example"),
    ("collocations", "Collocations"),
    ("wordfamily", "WordFamily"),
    ("uk_audio", "AudioUK"),
    ("us_audio", "AudioUS"),
    ("source1", "AudioSource"),
    ("source2", "Source"),
    ("cefr", "CEFRLevel"),
    ("idioms", "Idioms"),
    ("synonyms", "Synonyms"),
    ("antonyms", "Antonyms"),
    ("example_audio_uk", "ExampleAudioUK"),
    ("example_audio_us", "ExampleAudioUS"),
    ("idiom_example_audio_uk", "IdiomExampleAudioUK"),
    ("idiom_example_audio_us", "IdiomExampleAudioUS"),
    ("definition_vi", "DefinitionVI"),
    ("cambridge_url", "CambridgeURL"),
    ("oxford_pos_urls", "OxfordPOSURLs"),
    ("production_answer", "ProductionAnswer"),
    ("sense_pos", "SensePOS"),
    ("idiom_meaning_vi", "IdiomMeaningVI"),
    ("collocation_sources", "CollocationSources"),
)
EAVM_FIELD_NAMES: tuple[str, ...] = tuple(
    field_name for _, field_name in EAVM_JSON_TO_FIELD
)
EAVM_TEMPLATE_NAMES = ("Recognition", "Production (VI -> EN)")
EAVM_REQUIREMENTS_BY_FIELD: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (0, "any", ("Word",)),
    (1, "all", ("DefinitionVI", "Example", "ProductionAnswer")),
)


def packager_contract_payload(*, genanki_version: str | None = None) -> dict:
    """Return the JSON-ready package contract bound into release provenance."""

    return {
        "schema_version": PACKAGER_CONTRACT_SCHEMA_VERSION,
        "generator": {
            "name": "genanki",
            "version": genanki_version or version("genanki"),
        },
        "model": {
            "id": EAVM_MODEL_ID,
            "name": EAVM_MODEL_NAME,
            "json_to_field": [list(pair) for pair in EAVM_JSON_TO_FIELD],
        },
        "templates": list(EAVM_TEMPLATE_NAMES),
        "requirements": [
            {
                "template_ordinal": ordinal,
                "mode": mode,
                "fields": list(fields),
            }
            for ordinal, mode, fields in EAVM_REQUIREMENTS_BY_FIELD
        ],
    }
