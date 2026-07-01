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
    assert sake["uk_audio"] == "[sound:oxford_uk_sake.mp3]"
    assert sake["us_audio"] == "[sound:oxford_us_sake.mp3]"
    assert sake["idioms"] == ""

    strip = by_key[("strip", "noun", "C2")]
    assert strip["guid"] == "I_w2q^IJck"
    assert strip["definition"] == (
        "sports uniform (đồng phục thi đấu)|shop street (phố thương mại)"
    )
    assert "take clothes off" not in strip["definition"]


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
