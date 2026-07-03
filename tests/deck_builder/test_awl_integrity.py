from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.awl_integrity import (
    AwlIntegrityPaths,
    audit_awl,
    parse_awl_rows,
    parse_cambridge_pos_cefr,
    split_pos,
)


def test_split_pos_normalizes_phrasal_verb():
    assert split_pos("n., phrasal v.") == ("noun", "phrasal verb")


def test_cambridge_parser_scopes_cefr_to_pos_and_dictionary():
    html = b"""
    <div class="entry-body__el"><div class="cid" id="cald4-1"></div>
      <div class="pos-header"><span class="pos dpos">adjective</span></div>
      <span class="epp-xref">B2</span></div>
    <div class="entry-body__el"><div class="cid" id="cald4-2"></div>
      <div class="pos-header"><span class="pos dpos">verb</span></div></div>
    <div class="entry-body__el"><div class="cid" id="cbed-1"></div>
      <div class="pos-header"><span class="pos dpos">verb</span></div>
      <span class="epp-xref">C1</span></div>
    """
    assert parse_cambridge_pos_cefr(html) == {
        "adjective": {"B2"},
        "verb": {"UNCLASSIFIED"},
    }


def test_production_awl_is_source_clean_and_preserves_official_sublists():
    project = ProjectPaths()
    result = audit_awl(AwlIntegrityPaths(
        project.awl_md,
        project.oxford_jsonl,
        project.awl_cambridge_fallbacks,
        None,
    ))
    assert result.errors == ()
    assert result.corrections == ()
    assert result.headword_count == 570
    assert result.rows_before == result.rows_after == 668

    rows = parse_awl_rows(project.awl_md.read_text(encoding="utf-8"))
    assert len({row.raw_line for row in rows}) == len(rows)
    sublists: dict[int, set[str]] = {}
    for row in rows:
        sublists.setdefault(row.sublist, set()).add(row.word.lower())
    assert {key: len(value) for key, value in sublists.items()} == {
        1: 60, 2: 60, 3: 60, 4: 60, 5: 60,
        6: 60, 7: 60, 8: 60, 9: 60, 10: 30,
    }


def test_production_regression_rows_are_split_by_cefr_and_source():
    project = ProjectPaths()
    rows = parse_awl_rows(project.awl_md.read_text(encoding="utf-8"))
    actual = {
        (row.word.lower(), row.pos, row.cefr, row.note)
        for row in rows
    }
    assert ("abstract", ("adjective",), "B2", "") in actual
    assert ("abstract", ("verb",), "UNCLASSIFIED", "") in actual
    assert ("comprehensive", ("adjective",), "B2", "") in actual
    assert ("comprehensive", ("noun",), "C2", "") in actual
    assert ("contrary", ("adjective",), "C1", "") in actual
    assert ("percent", ("noun",), "UNCLASSIFIED", "Cambridge") in actual
    assert (
        "percent", ("adjective", "adverb"), "B1", "Cambridge"
    ) in actual
    assert (
        "notwithstanding", ("adverb", "preposition"), "C1", "Cambridge"
    ) in actual
    assert (
        "notwithstanding", ("conjunction",), "UNCLASSIFIED", ""
    ) in actual
