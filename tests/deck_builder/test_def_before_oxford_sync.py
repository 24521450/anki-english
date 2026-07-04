import json
from collections import defaultdict

from src.config import ProjectPaths
from src.deck_builder.build_support import lookup_gloss, _load_audit_overrides
from src.deck_builder.simplify_senses import simplify_record


PATHS = ProjectPaths()
FIX_STATUS = "def_before_oxford_sync_20260701"

EXPECTED = {
    ("curse", "noun", "UNCLASSIFIED"): (
        "a rude or offensive word or phrase that some people use when they are very angry|"
        "a word or phrase that has a magic power to make something bad happen|"
        "something that causes harm or evil|"
        "menstruation (= the process or time of menstruating)"
    ),
    ("overlap", "noun", "UNCLASSIFIED"): (
        "a shared area of interest, knowledge, responsibility, etc.|"
        "the amount by which one thing covers another thing|"
        "a period of time in which two events or activities happen together"
    ),
    ("overlap", "verb", "UNCLASSIFIED"): (
        "if one thing overlaps another, or the two things overlap, part of one thing covers part of the other|"
        "to make two or more things overlap|"
        "if two events overlap or overlap each other, the second one starts before the first one has finished|"
        "to cover part of the same area of interest, knowledge, responsibility, etc."
    ),
    ("sterile", "adjective", "UNCLASSIFIED"): (
        "not able to produce children or young animals|"
        "completely clean and free from bacteria|"
        "not producing any useful result|"
        "not having individual personality, imagination or new ideas|"
        "not good enough to produce crops"
    ),
    ("superficially", "adverb", "UNCLASSIFIED"): (
        "in a way that appears to be true, real or important until you look at it more carefully|"
        "not carefully or completely; in a way that only considers what is obvious|"
        "not seriously or to a great degree; in a way that only affects the surface|"
        "in a way that is not serious or important and lacks any depth of understanding or feeling"
    ),
    ("meantime", "adverb", "C1"): "in the period of time between two times or events",
}


def _audit_rows():
    return [
        json.loads(line)
        for line in PATHS.deck_audit_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_def_before_rows_match_current_oxford_senses():
    rows = _audit_rows()
    by_key = {}
    for row in rows:
        key = (row["word"], row["pos"], row["cefr"])
        by_key.setdefault(key, []).append(row)

    for key, expected in EXPECTED.items():
        assert len(by_key.get(key, [])) == 1, key
        row = by_key[key][0]
        assert row["def_before"] == expected
        assert row["fix_status"] == FIX_STATUS


def test_expected_definitions_are_derived_from_current_oxford_source():
    records_by_word = defaultdict(list)
    for line in PATHS.oxford_jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records_by_word[record["word"].lower()].append(record)

    for (word, pos, cefr), expected in EXPECTED.items():
        texts = []
        for record in records_by_word[word]:
            for sense in simplify_record(record):
                if sense.pos == pos and (sense.cefr or "UNCLASSIFIED") == cefr:
                    if sense.text and sense.text not in texts:
                        texts.append(sense.text)

        assert "|".join(texts) == expected


def test_overlap_combined_audit_row_was_split():
    overlap_rows = [
        row for row in _audit_rows()
        if row["word"] == "overlap" and row["cefr"] == "UNCLASSIFIED"
    ]

    assert {row["pos"] for row in overlap_rows} == {"noun", "verb"}
    assert all(row["pos"] != "noun, verb" for row in overlap_rows)


def test_overlap_split_keeps_combined_card_gloss_stable():
    glosses, _, _ = _load_audit_overrides(PATHS.deck_audit_jsonl)

    gloss = lookup_gloss(
        glosses,
        "overlap",
        "noun, verb",
        "UNCLASSIFIED",
        "overlap",
        ["noun", "verb"],
        "UNCLASSIFIED",
    )

    assert gloss == "intersect"
