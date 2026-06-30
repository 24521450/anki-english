"""Generate JSON Schema (draft 2020-12) for the ielts-deck record schema v2.

Source of truth: the design decisions pinned in the Phase 3 grill + the
parser implementation in src/scraper/oxford.py and cambridge.py.

Output:
    data/schema/oxford_record.schema.json
    data/schema/cambridge_record.schema.json
"""
from __future__ import annotations

import json
import os
import sys

PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
OUT_DIR = os.path.join(PROJECT_ROOT, "data", "schema")
os.makedirs(OUT_DIR, exist_ok=True)

# CEFR levels per CONTEXT.md
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "UNCLASSIFIED"]
OXFORD_LIST_NAMES = ["Oxford 3000", "Oxford 5000"]

# Oxford 23 subject labels per data/oxford_labels.json (sample — extend as needed)
SUBJECT_LABELS = [
    "Art", "Business", "Colours and Shapes", "Difficult and Failure",
    "Education", "Geography", "Health", "History", "Language", "Law",
    "Mathematics and Measurement", "Medicine", "Money", "Music",
    "People", "Politics", "Religion and Festivals", "Science",
    "Sport", "Technology", "Time", "Travel", "War and conflict",
]

# 12 register labels from oxford_labels.json
REGISTER_LABELS = [
    "formal", "informal", "slang", "specialist", "British English",
    "American English", "North American English", "old-fashioned",
    "old use", "dialect", "saying", "trademark",
]

# POS values observed in Oxford HTML (including compound forms)
POS_VALUES = [
    "noun", "verb", "adjective", "adverb", "preposition", "pronoun",
    "determiner", "conjunction", "number", "exclamation", "modal",
    "abbreviation", "phrasal verb", "linking verb", "definite article",
    "ordinal number", "prefix", "suffix", "combining form",
    "adjective,adverb", "determiner,pronoun", "exclamation,noun",
    "adjective,pronoun", "pronoun,determiner", "adverb,preposition",
    "preposition,adverb", "preposition,conjunction", "determiner,adjective",
    "noun,determiner", "determiner,ordinal_number",
    "determiner,pronoun,adverb", "adverb,pronoun,conjunction",
    "number,determiner", "conjunction,adverb", "adjective,adverb",
    "pronoun,adverb,adjective", "adverb,pronoun",
    "adverb,noun", "adjective,noun", "noun,verb",
]

# Oxford verb form names. All 8 are OPTIONAL because Oxford's verb_forms
# table is incomplete in the wild: e.g. `comprise` (transitive) has no
# -ing form, `game` (newer verb) has no third-person-s. We accept whatever
# Oxford exposes, and the Anki builder handles missing forms gracefully
# (renders "—" or omits the row).
#
# Core 5 (root, thirdps, past, pastpart, prespart) appear on regular verbs.
# Modal 3 (neg, short, rareshortform) appear only on modals.
VERB_FORMS = ["root", "thirdps", "past", "pastpart", "prespart",
              "neg", "short", "rareshortform"]


# -----------------------------------------------------------------------------
# Reusable sub-schemas
# -----------------------------------------------------------------------------

EXAMPLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text", "cf"],
    "properties": {
        "text": {"type": ["string", "null"], "description": "Example sentence text"},
        "cf": {"type": ["string", "null"], "description": "Collocation frame (e.g. 'abandon somebody'). Nullable."},
    },
}

COLLOCATION_BUCKET = {
    "type": "object",
    "description": "Buckets of collocations keyed by category (adverb / phrases / verb + head / etc.)",
    "additionalProperties": {
        "type": "array",
        "items": {"type": "string"},
    },
}

TOPIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "cefr"],
    "properties": {
        "name": {"type": "string"},
        "cefr": {
            "type": ["string", "null"],
            "enum": CEFR_LEVELS + [None],
            "description": "Per-topic CEFR. Nullable: Oxford sometimes tags a topic without a level.",
        },
    },
}

DEFINITION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "n", "sensenum_local", "text", "register_tags", "cefr", "topics",
        "collocations", "examples", "is_phrase", "is_idiom",
    ],
    "properties": {
        "n": {"type": "integer", "minimum": 1, "description": "1-based counter within pos_data entry"},
        "sensenum_local": {
            "type": ["string", "null"],
            "description": "Oxford's literal sensenum attribute on <li class='sense'>. Nullable for idioms/phrasal.",
        },
        "text": {"type": ["string", "null"], "description": "Definition text"},
        "register_tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Sense-level register tags (e.g. ['informal', 'slang'])",
        },
        "cefr": {
            "type": ["string", "null"],
            "enum": CEFR_LEVELS + [None],
            "description": "CEFR level for this sense (nullable)",
        },
        "topics": {
            "type": "array",
            "items": TOPIC_SCHEMA,
        },
        "collocations": COLLOCATION_BUCKET,
        "examples": {
            "type": "array",
            "items": EXAMPLE_SCHEMA,
        },
        "is_phrase": {"type": "boolean", "description": "True if phrasal verb. Not implemented in v2 (always false)."},
        "is_idiom": {"type": "boolean", "description": "True if idiom (detected via span.idm-g ancestor walk)"},
    },
}

POS_SECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["pos", "register_tags", "definitions"],
    "properties": {
        "pos": {"type": "string", "description": "POS label (e.g. 'noun', 'verb', 'adjective,adverb')"},
        "register_tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "POS-level register tags (rare; not implemented in v2)",
        },
        "definitions": {
            "type": "array",
            "items": DEFINITION_SCHEMA,
        },
    },
}

IDIOM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["phrase", "pos", "text", "register_tags", "cefr"],
    "properties": {
        "phrase": {"type": "string", "description": "Idiom phrase as it appears on Oxford page"},
        "pos": {"type": ["string", "null"], "description": "POS of the idiom (if derivable)"},
        "text": {"type": ["string", "null"], "description": "Idiom definition (not extracted in v2)"},
        "register_tags": {"type": "array", "items": {"type": "string"}},
        "cefr": {"type": ["string", "null"], "enum": CEFR_LEVELS + [None]},
    },
}

AUDIO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["uk", "us"],
    "properties": {
        "uk": {
            "type": ["string", "null"],
            "description": "UK pronunciation audio URL. Oxford: data-src-mp3 on .sound.audio_play_button. Cambridge: <source> child of <audio> with uk_pron in src.",
        },
        "us": {
            "type": ["string", "null"],
            "description": "US pronunciation audio URL. Same selector logic as uk.",
        },
    },
}


# -----------------------------------------------------------------------------
# Top-level schemas
# -----------------------------------------------------------------------------

def _common_record_schema(source_value: str) -> dict:
    """Schema body shared by Oxford and Cambridge. Only the const for `source` differs.

    Per project decision (Phase 3 grill), Oxford and Cambridge are kept as separate
    files in the JSONL output (data/oxford_full.jsonl vs data/cambridge_full.jsonl),
    so we use 2 separate schema files, each with `source: const <value>`.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://ielts-deck.local/schemas/{source_value}_record.v2.json",
        "title": f"{source_value.capitalize()} Dictionary Record (Schema v2)",
        "description": "Schema for a single word record produced by the ielts-deck "
                       f"{source_value.capitalize()} parser. One record per (word) at the JSONL "
                       "top level. Multi-POS is nested under pos_data.",
        "type": "object",
        "additionalProperties": False,
        "required": ([
            "$schema", "word", "homonym_index", "source", "source_url", "source_files",
            "pos", "register_tags", "oxford_lists", "oxford_badge", "opal", "awl",
            "audio", "see_also", "pos_data", "verb_forms", "idioms",
        ] if source_value == "oxford" else [
            # Cambridge: no oxford_badge (Oxford-only field), no homonym_index
            # (Cambridge uses different markup; v2 doesn't model it)
            "$schema", "word", "homonym_index", "source", "source_url", "source_files",
            "pos", "register_tags", "oxford_lists", "opal", "awl",
            "audio", "see_also", "pos_data", "verb_forms", "idioms",
        ]),
        "properties": {
            "$schema": {
                "type": "string",
                "description": "URI of this schema (self-describing record)",
            },
            "word": {
                "type": ["string", "null"],
                "description": "Headword. Null only on synthetic records.",
            },
            "homonym_index": {
                "type": ["integer", "null"],
                "minimum": 1,
                "description": "Oxford homonym index (1, 2, 3...) for words with distinct etymologies sharing the same spelling. Null for non-homonyms. Display as superscript: bass¹. The merge step groups by (word, homonym_index) — bass1 and bass2 are NOT merged.",
            },
            "source": {
                "type": "string",
                "const": source_value,
                "description": f"Always '{source_value}'. Two separate schemas ensure this invariant.",
            },
            "source_url": {
                "type": ["string", "null"],
                "description": "Oxford/Cambridge URL the record was scraped from. Null when generated from cache (caller fills in).",
            },
            "source_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of cache filenames that contributed to this record (for traceability).",
            },
            "pos": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top-level POS labels declared on the page (usually 1, can be multiple for multi-POS words).",
            },
            "register_tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top-level (word-wide) register tags. Always [] in v2 (no source exposes word-level register in the parsed HTML).",
            },
            "oxford_lists": {
                "type": "array",
                "items": {"type": "string", "enum": OXFORD_LIST_NAMES},
                "description": "Oxford 3000/5000 list membership. Empty for Cambridge (always []).",
            },
            **({
                "oxford_badge": {
                    "type": ["string", "null"],
                    "enum": CEFR_LEVELS + [None],
                    "description": "Word-level CEFR badge from Oxford 3000/5000 top-of-page span (ox3ksym_* / ox5ksym_*). Distinct from per-sense def.cefr — this is Oxford's tier endorsement for the whole word.",
                },
            } if source_value == "oxford" else {}),
            "opal": {
                "type": ["string", "null"],
                "description": "OPAL word list designation (e.g. 'OPAL spoken', 'OPAL written'). Oxford-only; not implemented in v2 (cross-ref phase).",
            },
            "awl": {
                "type": ["string", "null"],
                "description": "Academic Word List designation. Oxford-only; not implemented in v2 (cross-ref phase).",
            },
            "audio": AUDIO_SCHEMA,
            "see_also": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Related headwords from SEE ALSO section. Oxford: span.xrefs + span.xh. Cambridge: .xref.",
            },
            "pos_data": {
                "type": "array",
                "items": POS_SECTION_SCHEMA,
                "description": "One entry per POS section. Each contains all senses for that POS.",
            },
            "verb_forms": {
                "oneOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        # All 8 verb_form keys are optional — Oxford's
                        # verb_forms_table is incomplete (e.g. `comprise`
                        # transitive has no -ing form, `game` has no 3ps).
                        "properties": {f: {"type": "string"} for f in VERB_FORMS},
                        "description": "Oxford only: parsed from <table class='verb_forms_table'>. All keys optional — Oxford exposes whatever forms it has. Core 5 (root, thirdps, past, pastpart, prespart) appear on regular verbs; 3 modal keys (neg, short, rareshortform) appear on modals only.",
                    },
                ],
            },
            "idioms": {
                "type": "array",
                "items": IDIOM_SCHEMA,
                "description": "Top-level idiom phrases (extracted via span.idm-g for Oxford). Cambridge does not have this section.",
            },
            # Build-layer flags. Populated by merge.py for records that have
            # neither pos_data nor idioms (e.g. Oxford phrasal-verb redirects
            # like 'deprive' / 'derive' / 'devote' / 'rely' which link out to
            # a separate phrasal-verb page). The Anki builder MUST check
            # `_skip: true` and skip these records.
            #
            # Underscore prefix marks these as internal build-layer metadata,
            # not part of the source-data contract.
            "_skip": {
                "type": "boolean",
                "description": "Build-layer flag: when true, the Anki builder must skip this record (no extractable senses). Set by merge.py when both pos_data and idioms are empty.",
            },
            "_skip_reason": {
                "type": "string",
                "description": "Human-readable explanation of why _skip was set (e.g. 'phrasal-verb-redirect: no extractable senses').",
            },
        },
    }


def main() -> int:
    ox_schema = _common_record_schema("oxford")
    cam_schema = _common_record_schema("cambridge")

    # Source-specific note in title-level description, NOT in field descriptions:
    # bug notes belong in ADR/CHANGELOG, not in schema contract. See docs/adr/0002-multi-pos-merge-bug.md.
    # Register tags note: also bug-tracker worthy, not schema-worthy. See ADR-0003 (TBD).

    ox_path = os.path.join(OUT_DIR, "oxford_record.schema.json")
    cam_path = os.path.join(OUT_DIR, "cambridge_record.schema.json")
    with open(ox_path, "w", encoding="utf-8") as f:
        json.dump(ox_schema, f, indent=2, ensure_ascii=False)
    with open(cam_path, "w", encoding="utf-8") as f:
        json.dump(cam_schema, f, indent=2, ensure_ascii=False)

    print(f"Wrote {ox_path}")
    print(f"Wrote {cam_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
