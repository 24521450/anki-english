import json

from src.config import ProjectPaths


PATHS = ProjectPaths()
FIX_STATUS = "def_before_cefr_sync_20260701"


def _jsonl_rows(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_seed_cefr_rows_are_explicitly_provenanced():
    rows = _jsonl_rows(PATHS.deck_audit_jsonl)
    by_key = {(row["word"], row["pos"], row["cefr"]): row for row in rows}
    expected_keys = {
        ("hook", "noun", "C1"),
        ("hook", "verb", "B2"),
        ("premier", "noun", "C1"),
        ("sake", "noun", "C1"),
    }

    assert all(by_key[key]["cefr_source"] == "oxford_5000_seed" for key in expected_keys)
    assert ("hook", "noun", "B2") not in by_key
    assert ("hook", "verb", "C1") not in by_key
    assert ("strip", "noun, verb", "C2") not in by_key
    assert by_key[("strip", "noun", "C2")]["fix_status"] == FIX_STATUS


def test_corrected_cards_preserve_guids_and_homonym_metadata():
    cards = _jsonl_rows(PATHS.anki_notes_jsonl)
    by_key = {(card["word"], card["pos"], card["cefr"]): card for card in cards}

    assert by_key[("hook", "noun", "C1")]["guid"] == "@n{6Y[D5$2"
    assert by_key[("hook", "verb", "B2")]["guid"] == "QxkMg}&{Mf"
    assert by_key[("premier", "noun", "C1")]["guid"] == ":-6ZC8^&Jv"

    sake = by_key[("sake", "noun", "C1")]
    assert sake["guid"] == "cU3J}]?X.%"
    assert sake["ipa"] == "/ˈsɑːki/"
    assert sake["uk_audio"] == "[sound:cambridge_uk_sake_noun_2.mp3]"
    assert sake["us_audio"] == "[sound:cambridge_us_sake_noun_2.mp3]"
    assert sake["idioms"] == ""

    strip = by_key[("strip", "noun", "C2")]
    assert strip["guid"] == "I_w2q^IJck"
    assert strip["definition"] == (
        "sports uniform (đồng phục thi đấu)|shop street (phố thương mại)"
    )
    assert "take clothes off" not in strip["definition"]


def test_converse_homonyms_are_separate_cards():
    cards = _jsonl_rows(PATHS.anki_notes_jsonl)
    converse = {
        (card["pos"], card["cefr"]): card
        for card in cards
        if card["word"] == "converse"
    }

    assert set(converse) == {
        ("verb", "UNCLASSIFIED"),
        ("adjective, noun", "UNCLASSIFIED"),
    }

    verb = converse[("verb", "UNCLASSIFIED")]
    assert verb["guid"] == "hu-nITV:EB"
    assert verb["ipa"] == "UK: /kənˈvɜːs/ | US: /kənˈvɜːrs/"
    assert verb["definition"] == "talk with sb (trò chuyện/đàm thoại)"
    assert verb["example"] == "She conversed with the Romanians in French."
    assert verb["source2"] == "AWL"
    assert verb["uk_audio"] == "[sound:cambridge_uk_converse_verb.mp3]"
    assert verb["us_audio"] == "[sound:cambridge_us_converse_verb.mp3]"

    nominal = converse[("adjective, noun", "UNCLASSIFIED")]
    assert nominal["guid"] == "dI;xOQZ.Jd"
    assert nominal["ipa"] == "UK: /ˈkɒnvɜːs/ | US: /ˈkɑːnvɜːrs/"
    assert nominal["definition"] == "opposite of a fact or statement (điều ngược lại/mặt trái)"
    assert nominal["example"].startswith("the converse effect|")
    assert nominal["source2"] == "AWL"
    assert nominal["uk_audio"] == "[sound:cambridge_uk_converse_adjective_noun.mp3]"
    assert nominal["us_audio"] == "[sound:cambridge_us_converse_adjective_noun.mp3]"


def test_manual_fills_only_cover_missing_oxford_rows():
    rows = json.loads(PATHS.manual_card_fills.read_text(encoding="utf-8"))
    blocked_keys = {
        ("hook", "noun", "C1"),
        ("hook", "verb", "B2"),
        ("premier", "noun", "C1"),
        ("sake", "noun", "C1"),
        ("strip", "noun, verb", "C2"),
    }

    keys = {(row["word"], row["pos"], row["cefr"]) for row in rows}
    assert keys.isdisjoint(blocked_keys)
    assert {row["source"] for row in rows} == {"missing_oxford_5000"}


def test_oxford_5000_seed_levels_remain_source_preserved():
    text = PATHS.oxford_5000_md.read_text(encoding="utf-8")

    assert "| **hook** | v. | B2 |  |" in text
    assert "| **hook** | n. | C1 |  |" in text
    assert "| **premier** | n. | C1 |  |" in text
    assert "| **sake** | n. | C1 |  |" in text
