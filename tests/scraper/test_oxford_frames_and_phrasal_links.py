from __future__ import annotations

import json

import jsonschema

from src.scraper.merge import merge_word_records
from src.scraper.oxford import parse_oxford
from src.scraper.rebuild_command import merge_oxford_records_from_file
from tools import ci_hydrate_parser_fixtures as fixture_catalog


def _parse_inline(senses: str, aside: str = "") -> dict:
    return parse_oxford(
        f"""
        <html><head><meta charset="utf-8"><link rel="canonical"
          href="https://www.oxfordlearnersdictionaries.com/definition/english/contend"></head>
        <body><div class="entry"><div class="top-container">
          <div class="top-g"><div class="webtop">
            <h1 class="headword">contend</h1><span class="pos">verb</span>
          </div></div>
          <ol class="senses_multiple">{senses}</ol>
        </div>{aside}</div></body></html>
        """.encode()
    )


def _definitions(record: dict) -> list[dict]:
    return record["pos_data"][0]["definitions"]


def test_direct_sense_frame_is_raw_supporting_evidence_and_safe_example_default():
    definition = _definitions(_parse_inline("""
      <li class="sense" sensenum="1">
        <span class="cf"> contend   (for somebody) </span>
        <span class="def">compete for something</span>
        <ul class="examples"><li><span class="x">They contended for power.</span></li></ul>
      </li>
    """))[0]

    assert definition["sense_frames"] == ["contend (for somebody)"]
    assert definition["examples"] == [
        {"text": "They contended for power.", "cf": "contend (for somebody)"}
    ]
    assert definition["collocation_evidence"] == [{
        "text": "contend (for somebody)",
        "source": "oxford",
        "origin": "oxford_sense_cf",
        "evidence_kind": "supporting",
        "example_index": None,
        "example_text": None,
        "container_index": 1,
        "item_index": None,
        "category": None,
        "truncated": False,
        "full_entry_url": None,
    }]


def test_nested_example_frame_wins_over_direct_sense_frame():
    definition = _definitions(_parse_inline("""
      <li class="sense" sensenum="1">
        <span class="cf">contend for something</span>
        <span class="def">compete for something</span>
        <ul class="examples"><li>
          <span class="cf">contend with somebody</span>
          <span class="x">She contended with the champion.</span>
        </li></ul>
      </li>
    """))[0]

    assert definition["sense_frames"] == ["contend for something"]
    assert definition["examples"][0]["cf"] == "contend with somebody"


def test_ambiguous_direct_frames_and_structural_headers_do_not_inherit():
    definition = _definitions(_parse_inline("""
      <li class="sense" sensenum="1">
        <span class="cf">+ noun</span>
        <span class="cf"> (+ adjective) </span>
        <span class="cf">contend for something</span>
        <span class="cf">contend against somebody</span>
        <span class="cf">contend for something</span>
        <span class="def">compete for something</span>
        <ul class="examples"><li><span class="x">They contended for power.</span></li></ul>
      </li>
    """))[0]

    assert definition["sense_frames"] == [
        "contend for something",
        "contend against somebody",
    ]
    assert definition["examples"][0]["cf"] is None
    frame_evidence = [
        row for row in definition["collocation_evidence"]
        if row["origin"] == "oxford_sense_cf"
    ]
    assert [row["text"] for row in frame_evidence] == [
        "contend for something",
        "contend against somebody",
        "contend for something",
    ]
    assert [row["container_index"] for row in frame_evidence] == [1, 2, 3]


def test_sense_frame_inheritance_never_leaks_across_senses():
    definitions = _definitions(_parse_inline("""
      <li class="sense" sensenum="1">
        <span class="cf">contend that…</span><span class="def">argue</span>
        <ul class="examples"><li><span class="x">I contend that it is true.</span></li></ul>
      </li>
      <li class="sense" sensenum="2">
        <span class="cf">contend for something</span><span class="def">compete</span>
        <ul class="examples"><li><span class="x">They contended for power.</span></li></ul>
      </li>
    """))

    assert [definition["examples"][0]["cf"] for definition in definitions] == [
        "contend that…",
        "contend for something",
    ]


def test_contend_fixtures_preserve_main_link_and_target_page_identity():
    main_fixture = fixture_catalog.special_fixture(
        "contend-sense-frames-and-phrasal-link"
    )
    target_fixture = fixture_catalog.special_fixture("contend-with-target-identity")
    main = parse_oxford(
        fixture_catalog.special_fixture_path(main_fixture["id"]).read_bytes(),
        source_files=[main_fixture["filename"]],
    )
    target = parse_oxford(
        fixture_catalog.special_fixture_path(target_fixture["id"]).read_bytes(),
        source_files=[target_fixture["filename"]],
    )

    assert main["phrasal_verb_links"] == [{
        "phrase": "contend with",
        "url": "https://www.oxfordlearnersdictionaries.com/definition/english/contend-with",
    }]
    assert target["word"] == "contend with"
    assert target["pos_data"][0]["source_url"] == (
        "https://www.oxfordlearnersdictionaries.com/definition/english/contend-with"
    )

    schema = json.loads(
        (fixture_catalog.PROJECT_ROOT / "data/schema/oxford_record.schema.json")
        .read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(main)
    jsonschema.Draft202012Validator(schema).validate(target)


def test_phrasal_link_extraction_is_authoritative_canonical_and_deduped():
    record = _parse_inline("""
      <li class="sense"><span class="def">argue</span></li>
    """, aside="""
      <aside class="phrasal_verb_links"><ul class="pvrefs">
        <li><a href="https://www.oxfordlearnersdictionaries.com/definition/english/contend-with#entry">contend with</a></li>
        <li><a href="https://www.oxfordlearnersdictionaries.com/definition/english/contend-with#other">contend with</a></li>
        <li><a href="https://example.com/definition/english/contend-against">bad host</a></li>
      </ul></aside>
      <aside><ul class="pvrefs"><li>
        <a href="https://www.oxfordlearnersdictionaries.com/definition/english/leak">leak</a>
      </li></ul></aside>
    """)

    assert record["phrasal_verb_links"] == [{
        "phrase": "contend with",
        "url": "https://www.oxfordlearnersdictionaries.com/definition/english/contend-with",
    }]


def test_merge_unions_raw_frames_and_exact_phrase_target_identities():
    first = _parse_inline("""
      <li class="sense" sensenum="1">
        <span class="cf">contend that…</span><span class="def">argue</span>
      </li>
    """)
    second = _parse_inline("""
      <li class="sense" sensenum="1">
        <span class="cf">contend something</span><span class="def">argue</span>
      </li>
    """)
    first["phrasal_verb_links"] = [{
        "phrase": "contend with",
        "url": "https://www.oxfordlearnersdictionaries.com/definition/english/contend-with",
    }]
    second["phrasal_verb_links"] = [
        first["phrasal_verb_links"][0],
        {
            "phrase": "contend against",
            "url": "https://www.oxfordlearnersdictionaries.com/definition/english/contend-against",
        },
    ]

    merged = merge_word_records([first, second])

    assert _definitions(merged)[0]["sense_frames"] == [
        "contend that…",
        "contend something",
    ]
    assert merged["phrasal_verb_links"] == [
        first["phrasal_verb_links"][0],
        second["phrasal_verb_links"][1],
    ]


def test_production_rebuild_keeps_phrase_pages_independent(tmp_path):
    fixtures = [
        fixture_catalog.special_fixture("contend-sense-frames-and-phrasal-link"),
        fixture_catalog.special_fixture("contend-with-target-identity"),
    ]
    records = [
        parse_oxford(
            fixture_catalog.special_fixture_path(item["id"]).read_bytes(),
            source_files=[item["filename"]],
        )
        for item in fixtures
    ]
    input_path = tmp_path / "oxford-per-file.jsonl"
    output_path = tmp_path / "oxford.jsonl"
    second_output_path = tmp_path / "oxford-second.jsonl"
    input_path.write_text(
        "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
    )

    merge_oxford_records_from_file(str(input_path), str(output_path))
    merge_oxford_records_from_file(str(input_path), str(second_output_path))

    merged = [json.loads(line) for line in output_path.read_text("utf-8").splitlines()]
    assert output_path.read_bytes() == second_output_path.read_bytes()
    assert [row["word"] for row in merged] == ["contend", "contend with"]
    assert all(
        not (row.get("_skip_reason") or "").startswith("folded-into-main-word")
        for row in merged
    )
