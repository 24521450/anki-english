"""One-shot script: tag 13 duplicate cards with `delete` + merge POS for kept cards.

Per plan (2026-06-20):
- 13 dup `(word, pos, cefr)` keys exist in anki_notes.jsonl + anki_notes.txt from a pre-existing build_notes Type A POS remap bug.
- For each dup pair:
  - Keep the card with the FULL definition (def from jsonl, not the short gloss
    from filled.json inject).
  - Tag the GLOSS card with `delete` so the user can filter and delete it in
    Anki.
  - Where applicable, MERGE the POS of the deleted card into the kept card
    (e.g. phrasal verb + verb becomes "phrasal verb, verb") so the card still
    matches both original vocab_list target keys.

Workflow:
  1. python -m tools.tag_duplicates_for_deletion    # this script
  2. (user) Import anki_notes.txt into Anki
  3. (user) Filter for `delete` tag, delete those cards in Anki
  4. (user) Export deck back to anki_notes.txt
  5. python -m tools.build_notes                    # verify no dups re-created
  6. python -m tools._inject_missing_cards          # verify inject doesn't recreate dups

Run: python -m tools.tag_duplicates_for_deletion

Idempotent: re-running on an already-tagged deck just no-ops the tag step
(delete tag is already present, POS already updated).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.config import ProjectPaths

paths = ProjectPaths()
ROOT = paths.root
JSONL_PATH = paths.anki_notes_jsonl
TXT_PATH = paths.anki_notes_txt

# (word, pos, cefr, keep_guid, delete_guid, new_pos_for_kept_card_or_None)
#
# keep_guid: GUID of the card to KEEP (full def from jsonl). May have its POS
#   field updated to new_pos_for_kept_card.
# delete_guid: GUID of the card to TAG with `delete`. Its def is the short
#   gloss from filled.json; Anki user filters for `delete` tag and deletes it.
# new_pos_for_kept_card:
#   None = keep current POS
#   "phrasal verb, verb" = merge: kept card now carries both POS labels so it
#     stays matched against both source vocab_list keys (e.g. deprive at verb
#     AND phrasal verb POS in the vocab list).
#
# GUIDs verified against current deck (2026-06-20). If the deck is rebuilt
# before this script runs, GUIDs change — re-verify with _check_dup_keys.py
# helper before re-running.
ACTIONS = [
    # (word, pos, cefr, keep_guid, delete_guid, new_pos)
    ("accuse", "verb", "C1", "[]Z+nC[^t0", "7]pYDUt#0?", None),
    ("deprive", "phrasal verb", "C1", "8VcO1&GtcB", "`9)m^(uZGV", "phrasal verb, verb"),
    ("derive", "phrasal verb", "B2", "dyWb^v=0``", "[#*1^8kM$y", "phrasal verb, verb"),
    ("devote", "phrasal verb", "B2", "d0+rK3^u+.", "*{^rL8`hX7", "phrasal verb, verb"),
    ("downtown", "adjective", "B2", "1@?w:Me2(:", "j5Fn*hz?bO", "adjective, noun"),
    ("full-time", "adjective", "B2", "V[(*[^OCYi", "VER2Gs8>9i", "adjective, adverb"),
    ("mainland", "adjective", "C1", "K_[xKnI.vU", "m:WI)CI|3O", "adjective, noun"),
    ("meantime", "adverb", "C1", "N|.UFNN`SW", "U-x>X6Ov1U", "adverb, noun"),
    ("nursing", "noun", "B2", "_m[}),)MM.", "3K#[YZ.>$i", "noun, adjective"),
    ("part-time", "adjective", "B2", "&;tpjv4mxi", "-u0.aRI{VD", "adjective, adverb"),
    ("proceeding", "noun", "C1", ":#6S8]_#y_", ";A[7qjs@7o", None),
    ("solo", "adjective", "C1", "%nP=oVYMv%", "k94QY!IFm(", "adjective, noun"),
    ("worship", "noun", "C1", ",qqw,<G4mQ", "h9T>`6{Ge&", "noun, verb"),
]


def _add_delete_tag(tags_str: str) -> str:
    """Append 'delete' to a tags string (space-separated tokens). Idempotent."""
    tokens = tags_str.split() if tags_str else []
    if "delete" not in tokens:
        tokens.append("delete")
    return " ".join(tokens)


def tag_jsonl() -> tuple[int, int, int, list[str]]:
    """Apply actions to anki_notes.jsonl.

    Returns: (kept_updated_count, deleted_tagged_count, missing_count, warnings)
    """
    cards: list[dict] = []
    with JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cards.append(json.loads(line))

    guid_to_card = {c["guid"]: c for c in cards}
    kept_updated = 0
    deleted_tagged = 0
    missing = 0
    warnings: list[str] = []

    for word, pos, cefr, keep_guid, delete_guid, new_pos in ACTIONS:
        delete_card = guid_to_card.get(delete_guid)
        keep_card = guid_to_card.get(keep_guid)

        if delete_card is None:
            missing += 1
            warnings.append(
                f"MISSING delete_guid {delete_guid!r} for ({word}|{pos}|{cefr})"
            )
            continue
        if keep_card is None:
            missing += 1
            warnings.append(
                f"MISSING keep_guid {keep_guid!r} for ({word}|{pos}|{cefr})"
            )
            continue

        # Tag delete card with 'delete'
        old_tags = delete_card.get("tags", "")
        new_tags = _add_delete_tag(old_tags)
        if new_tags != old_tags:
            delete_card["tags"] = new_tags
            deleted_tagged += 1

        # Update keep card POS if requested
        if new_pos is not None and keep_card.get("pos") != new_pos:
            keep_card["pos"] = new_pos
            kept_updated += 1

    # Write back (atomic-ish: write to .tmp then replace)
    tmp_path = JSONL_PATH.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    tmp_path.replace(JSONL_PATH)

    return kept_updated, deleted_tagged, missing, warnings


def tag_txt() -> tuple[int, int, int, list[str]]:
    """Apply actions to anki_notes.txt (17-col tab-separated).

    txt schema (per build_notes.BuiltCard.to_tsv):
      idx 0: guid, 1: notetype, 2: deck, 3: word, 4: pos, 5: ipa,
      idx 6: definition, 7: example, 8: collocations, 9: wordfamily,
      idx 10: uk_audio, 11: us_audio, 12: source1, 13: source2,
      idx 14: cefr, 15: idioms, 16: tags

    Returns: (kept_updated_count, deleted_tagged_count, missing_count, warnings)
    """
    lines = TXT_PATH.read_text(encoding="utf-8").splitlines()
    header_lines: list[str] = []
    body_lines: list[str] = []
    for line in lines:
        if line.startswith("#") or not line.strip():
            header_lines.append(line)
        else:
            body_lines.append(line)

    kept_updated = 0
    deleted_tagged = 0
    missing = 0
    warnings: list[str] = []

    new_body: list[str] = []
    for line in body_lines:
        parts = line.split("\t")
        if len(parts) < 17:
            new_body.append(line)
            continue
        guid = parts[0]

        # Find action for this guid (loop because small N)
        applied = False
        for word, pos, cefr, keep_guid, delete_guid, new_pos in ACTIONS:
            if guid == delete_guid:
                # Tag delete card
                old_tags = parts[16]
                new_tags = _add_delete_tag(old_tags)
                if new_tags != old_tags:
                    parts[16] = new_tags
                    deleted_tagged += 1
                applied = True
                break
            elif guid == keep_guid and new_pos is not None:
                if parts[4] != new_pos:
                    parts[4] = new_pos
                    kept_updated += 1
                applied = True
                break

        if not applied:
            # No action for this row, but verify it doesn't match a guid we
            # expected to find — that would mean the deck changed since the
            # script was written. We don't flag if it's just a non-dup row.
            pass

        new_body.append("\t".join(parts))

    # Cross-check: warn for any action whose GUIDs weren't seen in the txt
    seen_guids = set()
    for line in body_lines:
        parts = line.split("\t")
        if len(parts) >= 17:
            seen_guids.add(parts[0])
    for word, pos, cefr, keep_guid, delete_guid, _new_pos in ACTIONS:
        if keep_guid not in seen_guids:
            missing += 1
            warnings.append(
                f"MISSING keep_guid {keep_guid!r} for ({word}|{pos}|{cefr}) in txt"
            )
        if delete_guid not in seen_guids:
            missing += 1
            warnings.append(
                f"MISSING delete_guid {delete_guid!r} for ({word}|{pos}|{cefr}) in txt"
            )

    new_txt = "\n".join(header_lines + new_body)
    if new_txt and not new_txt.endswith("\n"):
        new_txt += "\n"
    TXT_PATH.write_text(new_txt, encoding="utf-8")

    return kept_updated, deleted_tagged, missing, warnings


def main() -> int:
    print(f"Tagging script — applying 13 dup-pair actions")
    print(f"  jsonl: {JSONL_PATH}")
    print(f"  txt:   {TXT_PATH}")
    print()

    # Backup current files first (per AGENTS.md backup convention)
    ts = "20260620_215200"
    jsonl_bak = JSONL_PATH.with_suffix(f".jsonl.bak_pre_tag_{ts}")
    txt_bak = TXT_PATH.with_suffix(f".txt.bak_pre_tag_{ts}")
    if not jsonl_bak.exists():
        jsonl_bak.write_text(JSONL_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup: {jsonl_bak.name}")
    if not txt_bak.exists():
        txt_bak.write_text(TXT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup: {txt_bak.name}")
    print()

    # Apply to jsonl
    kept_j, deleted_j, missing_j, warns_j = tag_jsonl()
    print(f"anki_notes.jsonl:")
    print(f"  kept POS updated: {kept_j}")
    print(f"  delete-tagged:    {deleted_j}")
    print(f"  missing GUIDs:    {missing_j}")

    # Apply to txt
    kept_t, deleted_t, missing_t, warns_t = tag_txt()
    print(f"anki_notes.txt:")
    print(f"  kept POS updated: {kept_t}")
    print(f"  delete-tagged:    {deleted_t}")
    print(f"  missing GUIDs:    {missing_t}")

    all_warnings = warns_j + warns_t
    if all_warnings:
        print()
        print("WARNINGS:")
        for w in all_warnings:
            print(f"  {w}")

    print()
    print("NEXT STEPS (manual):")
    print("  1. Import anki_notes.txt into Anki")
    print("  2. Filter cards with tag 'delete', delete them")
    print("  3. Export deck back to anki_notes.txt")
    print("  4. Run python -m tools.build_notes")
    print("  5. Run python -m tools._inject_missing_cards")
    print("  6. Verify no duplicate (word, pos, cefr) keys re-appear")

    return 0 if not all_warnings else 1


if __name__ == "__main__":
    raise SystemExit(main())