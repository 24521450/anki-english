import json

from src.config import ProjectPaths
from src.deck_builder.audit_overrides import find_cross_cefr_override_examples
from src.deck_builder.card_identity import CardIdentity, normalize_list_name


def _jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_cross_cefr_override_example_is_rejected():
    records = {
        "integrity": [
            {
                "word": "integrity",
                "oxford_badge": "C1",
                "pos_data": [
                    {
                        "pos": "noun",
                        "definitions": [
                            {
                                "cefr": "C1",
                                "examples": [{"text": "personal integrity"}],
                            },
                            {
                                "cefr": None,
                                "examples": [{"text": "territorial integrity"}],
                            },
                        ],
                    }
                ],
            }
        ]
    }
    audit_rows = [
        {
            "word": "integrity",
            "pos": "noun",
            "cefr": "C1",
            "example_after": "personal integrity|territorial integrity",
        }
    ]

    issues = find_cross_cefr_override_examples(
        audit_rows,
        records,
        active_non_manual_cards={("integrity", "noun", "C1")},
    )

    assert len(issues) == 1
    assert issues[0]["word"] == "integrity"
    assert issues[0]["sense_cefr"] is None
    assert issues[0]["example"] == "territorial integrity"


def test_example_shared_with_allowed_sense_is_not_rejected():
    records = {
        "shared": [
            {
                "word": "shared",
                "oxford_badge": "C1",
                "pos_data": [
                    {
                        "pos": "noun",
                        "definitions": [
                            {"cefr": "C1", "examples": [{"text": "same example"}]},
                            {"cefr": None, "examples": [{"text": "same example"}]},
                        ],
                    }
                ],
            }
        ]
    }

    issues = find_cross_cefr_override_examples(
        [{"word": "shared", "pos": "noun", "cefr": "C1", "example_after": "same example"}],
        records,
        active_non_manual_cards={("shared", "noun", "C1")},
    )

    assert issues == []


def test_canonical_curated_examples_respect_source_sense_cefr():
    paths = ProjectPaths()
    records_by_word = {}
    for record in _jsonl(paths.oxford_jsonl):
        records_by_word.setdefault(record["word"].lower(), []).append(record)

    manual_keys = {
        CardIdentity(
            word=row["word"],
            cefr=row["cefr"],
            list=normalize_list_name(row["list"], canonical=True),
            variant=row.get("variant") or "",
        ).as_key()
        for row in _jsonl(paths.manual_cards)
    }
    active_non_manual_cards = set()
    for row in _jsonl(paths.card_registry):
        identity = CardIdentity(
            word=row["word"],
            cefr=row["cefr"],
            list=normalize_list_name(row["list"], canonical=True),
            variant=row.get("variant") or "",
        )
        if row.get("status") == "active" and identity.as_key() not in manual_keys:
            active_non_manual_cards.add((identity.word.lower(), row["pos"].lower(), identity.cefr))

    issues = find_cross_cefr_override_examples(
        _jsonl(paths.deck_audit_jsonl),
        records_by_word,
        active_non_manual_cards=active_non_manual_cards,
    )

    assert issues == []
