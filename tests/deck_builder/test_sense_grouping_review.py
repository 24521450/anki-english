import json
from pathlib import Path

from tools.archive.data_migrations._apply_sense_grouping_review import REPAIRS


ROOT = Path(__file__).resolve().parents[2]


def _rows(path: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_temporal_variants_and_retirements_are_built_as_reviewed():
    cards = _rows("data/build/anki_notes.jsonl")
    by_guid = {row["guid"]: row for row in cards}

    assert "blK!z$J^4}" not in by_guid
    assert "OZZPa?0t@2" not in by_guid
    assert by_guid["fxDIz0`1%."]["definition"] == (
        "[formal]worldly, not spiritual (thuộc thế tục)|"
        "[formal]related to time (thuộc thời gian)"
    )
    assert "SenseVariant::general_formal" in by_guid["fxDIz0`1%."]["tags"]
    assert by_guid["t3mpAnat01"]["definition"] == (
        "[anatomy]near the temple (thuộc thái dương)"
    )
    assert "SenseVariant::anatomy" in by_guid["t3mpAnat01"]["tags"]
    assert by_guid["t3mpAnat01"]["deck"] == "English Academic Vocabulary::TED YT"
    assert by_guid["t3mpAnat01"]["uk_audio"]
    assert by_guid["t3mpAnat01"]["us_audio"]


def test_grouped_examples_stay_inside_their_definition_chunk():
    cards = {row["word"]: row for row in _rows("data/build/anki_notes.jsonl")}
    assert cards["accessible"]["example"].count("<br><br>") == 1
    assert cards["mortality"]["definition"].count("|") == 1
    assert cards["mortality"]["example"].count("|") == 1
    assert cards["retention"]["definition"].count("|") == 1
    assert cards["transcribe"]["definition"].count("|") == 1
    assert cards["breach"]["example"].split("|")[0] == (
        "a breach of contract<br><br>The company breached the agreement."
    )


def test_reviewed_keeps_remain_active():
    by_guid = {row["guid"]: row for row in _rows("data/build/anki_notes.jsonl")}
    for guid in {
        "5h{~9ioTEb", "/xUiXso]~Q", "D0tq!F6I2+",
        "Hd?Kj:WO(B", "NQD8xUt1~7", "s>o7[6qaNE",
    }:
        assert guid in by_guid


def test_grouping_collocations_match_canonical_owners():
    cards = {row["guid"]: row for row in _rows("data/build/anki_notes.jsonl")}
    audit = {
        (row["word"], row["pos"], row["cefr"]): row
        for row in _rows("data/curated/deck_audit.jsonl")
    }
    reviews = {
        row["guid"]: row
        for row in _rows("data/review/non_oxford_non_c2_overrides.jsonl")
    }

    for repair in REPAIRS:
        identity = (repair.word, cards[repair.guid]["pos"], cards[repair.guid]["cefr"])
        owner = audit[identity] if repair.owner == "audit" else reviews[repair.guid]
        expected = (
            owner.get("collocations_after")
            if repair.owner == "audit"
            else owner.get("Collocations")
        )
        assert cards[repair.guid]["collocations"] == expected, repair.word
