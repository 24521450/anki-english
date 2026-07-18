"""Structured Oxford/Cambridge collocation provenance regressions."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from src.scraper.cambridge import parse_cambridge
from src.scraper.merge import merge_word_records
from src.scraper.oxford import parse_oxford
from tools import ci_hydrate_parser_fixtures as fixture_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_KEYS = {
    "text",
    "source",
    "origin",
    "evidence_kind",
    "example_index",
    "example_text",
    "container_index",
    "item_index",
    "category",
    "truncated",
    "full_entry_url",
}


def _definition(record: dict) -> dict:
    return record["pos_data"][0]["definitions"][0]


def _evidence(
    text: str,
    *,
    origin: str,
    evidence_kind: str,
    source: str = "oxford",
    example_index: int | None = None,
    example_text: str | None = None,
    container_index: int | None = None,
    item_index: int | None = None,
    category: str | None = None,
    truncated: bool = False,
    full_entry_url: str | None = None,
) -> dict:
    return {
        "text": text,
        "source": source,
        "origin": origin,
        "evidence_kind": evidence_kind,
        "example_index": example_index,
        "example_text": example_text,
        "container_index": container_index,
        "item_index": item_index,
        "category": category,
        "truncated": truncated,
        "full_entry_url": full_entry_url,
    }


def test_oxford_curriculum_example_frames_are_example_linked_evidence():
    fixture = fixture_catalog.special_fixture("curriculum-collocation-evidence")
    record = parse_oxford(
        fixture_catalog.special_fixture_path(fixture["id"]).read_bytes(),
        source_files=[fixture["filename"]],
    )
    evidence = _definition(record)["collocation_evidence"]
    example_linked = [
        item for item in evidence if item["origin"] == "oxford_example_cf"
    ]

    assert [item["text"] for item in example_linked] == [
        "on the curriculum",
        "in the curriculum",
    ]
    assert [item["example_index"] for item in example_linked] == [2, 3]
    assert [item["example_text"] for item in example_linked] == [
        "Spanish is on the curriculum.",
        "Spanish is in the curriculum.",
    ]
    assert all(item["source"] == "oxford" for item in example_linked)
    assert all(item["evidence_kind"] == "example_linked" for item in example_linked)
    assert all(set(item) == EVIDENCE_KEYS for item in evidence)


def test_oxford_snippet_evidence_keeps_category_truncation_and_full_entry_url():
    fixture = fixture_catalog.special_fixture("curriculum-collocation-evidence")
    record = parse_oxford(
        fixture_catalog.special_fixture_path(fixture["id"]).read_bytes(),
        source_files=[fixture["filename"]],
    )
    evidence = _definition(record)["collocation_evidence"]
    snippet = [
        item for item in evidence if item["origin"] == "oxford_collocations_snippet"
    ]

    broad = next(item for item in snippet if item["text"] == "broad")
    assert broad["category"] == "adjective"
    assert broad["truncated"] is True
    assert broad["full_entry_url"] == (
        "https://www.oxfordlearnersdictionaries.com/definition/collocations/curriculum"
    )

    complete_phrase = next(
        item for item in snippet if item["text"] == "areas of the curriculum"
    )
    assert complete_phrase["category"] == "phrases"
    assert complete_phrase["truncated"] is False


def test_oxford_repeated_snippet_category_is_an_order_preserving_union():
    record = parse_oxford(
        b"""
        <html><head><link rel="canonical"
          href="https://www.oxfordlearnersdictionaries.com/definition/english/adhere"></head>
        <body><h1 class="headword">adhere</h1><div class="top-container">
          <div class="top-g"><span class="pos">verb</span></div>
          <ol class="sense_single"><li class="sense" sensenum="1">
            <span class="def">to stick firmly to something</span>
            <span class="unbox" unbox="snippet">
              <span class="box_title">Oxford Collocations Dictionary</span>
              <span class="body">
                <span class="unbox">adverb</span>
                <ul><li>properly</li><li>well</li></ul>
                <span class="unbox">adverb</span>
                <ul><li>closely</li><li>firmly</li><li>...</li></ul>
                <span class="xref_to_full_entry"><a class="Ref"
                  href="https://www.oxfordlearnersdictionaries.com/definition/collocations/adhere">full entry</a></span>
              </span>
            </span>
          </li></ol>
        </div></body></html>
        """
    )
    definition = _definition(record)

    assert definition["collocations"]["adverb"] == [
        "properly",
        "well",
        "closely",
        "firmly",
    ]
    snippet = [
        item
        for item in definition["collocation_evidence"]
        if item["origin"] == "oxford_collocations_snippet"
    ]
    assert [item["text"] for item in snippet] == [
        "properly",
        "well",
        "closely",
        "firmly",
    ]
    assert [item["container_index"] for item in snippet] == [1, 1, 2, 2]
    assert [item["truncated"] for item in snippet] == [False, False, True, True]


def test_cambridge_dexamp_pairing_distinguishes_example_bare_and_grammar_evidence():
    record = parse_cambridge(
        b"""
        <html><body>
          <span class="headword">violation</span><span class="pos dpos">noun</span>
          <div class="dsense_b">
            <div class="ddef_d">an action that breaks a rule</div>
            <span class="dexamp">
              <span class="lu dlu">flagrant violation</span>
              <span class="eg deg">The takeover was a flagrant violation of the treaty.</span>
            </span>
            <span class="dexamp"><span class="lu dlu">violation of</span></span>
            <span class="cl">violation of</span>
          </div>
        </body></html>
        """
    )
    definition = _definition(record)

    assert definition["examples"] == [
        {
            "text": "The takeover was a flagrant violation of the treaty.",
            "cf": None,
        }
    ]
    assert definition["collocations"] == {
        "collocations": ["flagrant violation", "violation of"]
    }

    evidence = definition["collocation_evidence"]
    assert evidence == [
        _evidence(
            "flagrant violation",
            source="cambridge",
            origin="cambridge_example_lu",
            evidence_kind="example_linked",
            example_index=1,
            example_text="The takeover was a flagrant violation of the treaty.",
            container_index=1,
            item_index=1,
        ),
        _evidence(
            "violation of",
            source="cambridge",
            origin="cambridge_bare_lu",
            evidence_kind="supporting",
            container_index=2,
            item_index=1,
        ),
        _evidence(
            "violation of",
            source="cambridge",
            origin="cambridge_grammar_cl",
            evidence_kind="supporting",
            container_index=1,
        ),
    ]


def test_merge_unions_distinct_evidence_without_losing_same_surface_origins():
    shared = _evidence(
        "on the curriculum",
        origin="oxford_example_cf",
        evidence_kind="example_linked",
        example_index=1,
        example_text="Spanish is on the curriculum.",
        container_index=1,
    )
    supporting = _evidence(
        "on the curriculum",
        origin="oxford_collocations_snippet",
        evidence_kind="supporting",
        container_index=1,
        item_index=1,
        category="preposition",
    )

    def record(source_file: str, evidence: list[dict]) -> dict:
        return {
            "word": "curriculum",
            "homonym_index": None,
            "source": "oxford",
            "source_url": None,
            "source_files": [source_file],
            "pos": ["noun"],
            "register_tags": [],
            "oxford_lists": [],
            "oxford_badge": None,
            "opal": None,
            "awl": None,
            "audio": {"uk": None, "us": None},
            "see_also": [],
            "pos_data": [
                {
                    "pos": "noun",
                    "source_url": None,
                    "register_tags": [],
                    "definitions": [
                        {
                            "n": 1,
                            "sensenum_local": "1",
                            "text": "the subjects in a course",
                            "register_tags": [],
                            "domain": None,
                            "cefr": "B1",
                            "topics": [],
                            "collocations": {},
                            "collocation_evidence": evidence,
                            "examples": [],
                            "is_phrase": False,
                            "is_idiom": False,
                            "synonyms": [],
                            "antonyms": [],
                        }
                    ],
                }
            ],
            "verb_forms": None,
            "idioms": [],
        }

    merged = merge_word_records(
        [
            record("oxford_curriculum_(noun).html", [shared]),
            record("oxford_curriculum_1_(noun).html", [shared, supporting]),
        ]
    )

    assert _definition(merged)["collocation_evidence"] == [shared, supporting]


def test_source_schemas_require_structured_collocation_evidence():
    for name in ("oxford_record.schema.json", "cambridge_record.schema.json"):
        schema = json.loads((PROJECT_ROOT / "data" / "schema" / name).read_text("utf-8"))
        definition_schema = schema["properties"]["pos_data"]["items"]["properties"][
            "definitions"
        ]["items"]

        assert "collocation_evidence" in definition_schema["required"]
        evidence_schema = definition_schema["properties"]["collocation_evidence"]
        assert evidence_schema["type"] == "array"
        assert set(evidence_schema["items"]["required"]) == EVIDENCE_KEYS


def test_source_schemas_reject_downgrading_example_linked_origins_to_supporting():
    cases = (
        (
            "oxford_record.schema.json",
            _evidence(
                "on the curriculum",
                origin="oxford_example_cf",
                evidence_kind="supporting",
                example_index=1,
                example_text="Spanish is on the curriculum.",
                container_index=1,
            ),
        ),
        (
            "cambridge_record.schema.json",
            _evidence(
                "flagrant violation",
                source="cambridge",
                origin="cambridge_example_lu",
                evidence_kind="supporting",
                example_index=1,
                example_text="This was a flagrant violation of the treaty.",
                container_index=1,
                item_index=1,
            ),
        ),
    )

    for schema_name, invalid_item in cases:
        schema = json.loads(
            (PROJECT_ROOT / "data" / "schema" / schema_name).read_text("utf-8")
        )
        evidence_item_schema = schema["properties"]["pos_data"]["items"][
            "properties"
        ]["definitions"]["items"]["properties"]["collocation_evidence"]["items"]

        assert not jsonschema.Draft202012Validator(evidence_item_schema).is_valid(
            invalid_item
        )
