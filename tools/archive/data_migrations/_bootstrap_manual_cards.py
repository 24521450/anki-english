"""One-shot bootstrap for data/review/manual_cards.jsonl from the current build.

This is an archive migration script, not a production path.
"""
from __future__ import annotations

import json
from collections import OrderedDict

from src.config import ProjectPaths
from src.deck_builder.build_issues import BuildIssue, BuildValidationError
from src.deck_builder.card_identity import (
    CardIdentity,
    normalize_cefr,
    normalize_word,
    primary_list_from_tags,
    reviewed_homonym_variant,
)
from src.deck_builder.manual_cards import (
    load_jsonl,
    serialize_manual_cards_rows,
    validate_manual_cards_or_raise,
)


def _load_ledger(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise BuildValidationError([
            BuildIssue("error", "invalid_ledger_shape", f"ledger {path} must be a JSON list")
        ])
    return data


def _identity_from_note(note: dict, ledger_pos: str) -> CardIdentity:
    list_name = primary_list_from_tags(note.get("tags"), canonical=True)
    variant = reviewed_homonym_variant(note.get("word"), note.get("cefr"), list_name, ledger_pos)
    return CardIdentity(
        word=normalize_word(note.get("word")),
        cefr=normalize_cefr(note.get("cefr")),
        list=list_name,
        variant=variant,
    )


def _build_row(note: dict, ledger_row: dict) -> dict:
    ledger_pos = (ledger_row.get("pos") or "").strip()
    identity = _identity_from_note(note, ledger_pos)
    return OrderedDict([
        ("word", identity.word),
        ("cefr", identity.cefr),
        ("list", identity.list),
        ("variant", identity.variant),
        ("definition", note.get("definition") or ""),
        ("example", note.get("example") or ""),
        ("collocations", note.get("collocations") or ""),
        ("wordfamily", note.get("wordfamily") or ""),
        ("ipa", note.get("ipa") or ""),
        ("uk_audio", note.get("uk_audio") or ""),
        ("us_audio", note.get("us_audio") or ""),
        ("source1", note.get("source1") or ""),
        ("source2", note.get("source2") or ""),
        ("idioms", note.get("idioms") or ""),
        ("provenance", OrderedDict([
            ("source", "manual_card_fills"),
            ("ledger_pos", ledger_pos),
        ])),
    ])


def _bootstrap_manual_cards_rows(notes_jsonl_path, ledger_path) -> list[dict]:
    notes = load_jsonl(notes_jsonl_path)
    notes_by_key = {
        (normalize_word(note.get("word")).lower(), normalize_cefr(note.get("cefr"))): note
        for note in notes
    }
    rows = []
    seen = set()
    for ledger_row in _load_ledger(ledger_path):
        key = (
            normalize_word(ledger_row.get("word")).lower(),
            normalize_cefr(ledger_row.get("cefr")),
        )
        note = notes_by_key.get(key)
        if note is None:
            raise BuildValidationError([
                BuildIssue("error", "manual_note_missing", f"no built note found for manual ledger row {key}")
            ])
        row = _build_row(note, ledger_row)
        identity = (row["word"], row["cefr"], row["list"], row["variant"])
        if identity in seen:
            raise BuildValidationError([
                BuildIssue("error", "duplicate_manual_identity", f"duplicate manual card identity {identity}")
            ])
        seen.add(identity)
        rows.append(row)
    return rows


def main() -> int:
    paths = ProjectPaths()
    rows = _bootstrap_manual_cards_rows(paths.anki_notes_jsonl, paths.manual_card_fills)
    validate_manual_cards_or_raise(rows)
    paths.manual_cards.write_text(
        serialize_manual_cards_rows(rows),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
