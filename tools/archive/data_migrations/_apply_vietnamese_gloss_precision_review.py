#!/usr/bin/env python3
"""Rewrite the reviewed 2026-07-11 Vietnamese gloss precision queue."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.gloss_hygiene import normalize_gloss


FIX_STATUS = "vietnamese_gloss_precision_review_20260711"
ISSUE_TYPE = "vietnamese_gloss_precision_review"
PRIOR_FIX_STATUS = {
    "attribution": "non_oxford_non_c2_review_20260701",
    "clerk": "gloss_review_log_20260630",
    "lean": "non_oxford_non_c2_review_20260701",
    "replacement": "p4_word_family_loop_complete_20260708",
    "restrain": "card_improvement_user_notes_20260710",
    "scratch": "gloss_review_log_20260630",
    "seize": "gloss_review_log_20260630",
    "sibling": "gloss_review_log_20260630",
    "solicitor": "gloss_review_log_20260630",
    "sterile": "semantic_overload_grouped_20260711",
    "strip (remove clothes/a layer)": "gloss_review_log_20260630",
    "twist": "p4_multi_pos_review_20260708",
}


@dataclass(frozen=True, slots=True)
class Repair:
    guid: str
    word: str
    pos: str
    cefr: str
    owner: str
    old_definition: str
    new_definition: str

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.word, self.pos, self.cefr)


REPAIRS: tuple[Repair, ...] = (
    Repair(
        "vV~Qxd}bCU", "attribution", "noun", "UNCLASSIFIED", "review",
        "saying sth was caused/done/created by sb/sth (quy nguyên nhân/ghi công/gán trách nhiệm)",
        "saying sth was caused/done/created by sb/sth (sự quy cho hoặc quy kết)",
    ),
    Repair(
        "LK-&12E9p`", "clerk", "noun", "B2", "audit",
        "shop/hotel/office worker (nhân viên bán hàng/khách sạn/văn phòng)",
        "shop/hotel/office worker (nhân viên cửa hàng, khách sạn hoặc văn phòng)",
    ),
    Repair(
        "I%>-ZZz|RF", "lean", "verb", "B2", "review",
        "bend or rest at an angle (ngả/dựa/nghiêng)",
        "bend or rest at an angle (nghiêng hoặc dựa)",
    ),
    Repair(
        "Ee?9B>!{wW", "replacement", "noun", "C1", "audit",
        "substitute thing/person/action (sự/thứ/người thay thế)",
        "substitute thing/person/action (sự thay thế hoặc người/vật thay thế)",
    ),
    Repair(
        "i/Mobs,`g1", "restrain", "verb", "C1", "review",
        "control or limit sb/sth (kiềm chế/khống chế/hạn chế)",
        "control or limit sb/sth (kiềm chế, khống chế hoặc hạn chế)",
    ),
    Repair(
        "u$noUa&2=.", "scratch", "noun, verb", "B2", "audit",
        "mark or cut (vết xước)|rub/cut with nails or sharp sth (gãi/cào/xước)",
        "mark or cut (vết xước)|rub/cut with nails or sharp sth (gãi hoặc cào xước)",
    ),
    Repair(
        "NQD8xUt1~7", "seize", "verb", "C1", "audit",
        "take by force (chộp/chiếm/bắt)|take goods officially (tịch thu)|use a chance quickly (nắm lấy cơ hội)",
        "take by force (chộp, chiếm hoặc bắt giữ)|take goods officially (tịch thu)|use a chance quickly (nắm lấy cơ hội)",
    ),
    Repair(
        "_6Lky<ae`R", "sibling", "noun", "B2", "audit",
        "brother or sister (anh/chị/em ruột)",
        "brother or sister (anh chị em ruột)",
    ),
    Repair(
        "oz,$owM6W5", "solicitor", "noun", "C1", "audit",
        "lawyer for advice, documents and court (luật sư tư vấn/giấy tờ/toà án)",
        "lawyer for advice, documents and court (luật sư tư vấn, soạn giấy tờ và đại diện)",
    ),
    Repair(
        '"j>(#&<;AW0"', "sterile", "adjective", "UNCLASSIFIED", "review",
        "unable to produce young, crops, or useful results (vô sinh/cằn cỗi/vô ích)|free from bacteria (vô trùng)|cold and lacking character (lạnh lẽo/thiếu sức sống)",
        "unable to produce young, crops, or useful results (vô sinh, cằn cỗi hoặc vô ích)|free from bacteria (vô trùng)|cold and lacking character (lạnh lẽo, thiếu sức sống)",
    ),
    Repair(
        ")3<x>19pDQ", "strip (remove clothes/a layer)", "verb", "C1", "audit",
        "remove clothes/layers/things (cởi/bóc/tước bỏ)",
        "remove clothes/layers/things (cởi hoặc loại bỏ)",
    ),
    Repair(
        "vyZB3_Nz>K", "twist", "noun, verb", "C1", "audit",
        "turn or bend sth (xoay/vặn)|unexpected change (bước ngoặt)|bend in path or body part (khúc quanh/bong/gập)",
        "turn or bend sth (xoay hoặc vặn)|unexpected change (bước ngoặt)|bend in path or body part (khúc quanh hoặc chỗ bong gân)",
    ),
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rewrite_jsonl(path: Path, updates: dict, key_fn, *, drop_keys=frozenset()) -> None:
    output: list[str] = []
    seen: set = set()
    dropped: set = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = key_fn(row)
        if key in drop_keys:
            dropped.add(key)
            continue
        if key in updates:
            output.append(json.dumps(updates[key], ensure_ascii=False))
            seen.add(key)
        else:
            output.append(line)
    if seen != set(updates):
        raise ValueError(f"missing updates in {path}: {set(updates) - seen}")
    if dropped != set(drop_keys):
        raise ValueError(f"missing removals in {path}: {set(drop_keys) - dropped}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")


def validate_preconditions(paths: ProjectPaths) -> None:
    if len(REPAIRS) != 12 or len({repair.guid for repair in REPAIRS}) != 12:
        raise ValueError("Vietnamese gloss manifest must contain 12 unique repairs")
    cards = {row["guid"]: row for row in load_jsonl(paths.anki_notes_jsonl)}
    for repair in REPAIRS:
        card = cards.get(repair.guid)
        if not card:
            raise ValueError(f"missing built GUID {repair.guid!r}")
        actual = (card.get("word"), card.get("pos"), card.get("cefr"), card.get("definition"))
        expected = (*repair.identity, repair.old_definition)
        if actual != expected:
            raise ValueError(f"built-card drift for {repair.word}: {actual!r} != {expected!r}")


def prepare_owner_updates(paths: ProjectPaths) -> tuple[dict, dict]:
    audit_rows = load_jsonl(paths.deck_audit_jsonl)
    audit_by_key = {
        (row.get("word"), row.get("pos"), row.get("cefr")): row
        for row in audit_rows
    }
    review_rows = load_jsonl(paths.non_oxford_non_c2_overrides)
    review_by_guid = {row.get("guid"): row for row in review_rows}
    audit_updates: dict = {}
    review_updates: dict = {}
    for repair in REPAIRS:
        if repair.owner == "audit":
            row = dict(audit_by_key.get(repair.identity) or {})
            if row.get("gloss_after") != repair.old_definition:
                raise ValueError(f"audit owner drift for {repair.word}")
            hygiene = normalize_gloss(repair.new_definition)
            row.update({
                "gloss_after": hygiene.gloss,
                "separator": hygiene.separator,
                "gloss_word_count": hygiene.gloss_word_count,
                "gate_status": "pass",
                "vietnamese_gloss_precision_status": FIX_STATUS,
            })
            audit_updates[repair.identity] = row
        else:
            row = dict(review_by_guid.get(repair.guid) or {})
            if row.get("Definition") != repair.old_definition:
                raise ValueError(f"review owner drift for {repair.word}")
            row.update({
                "Definition": repair.new_definition,
                "vietnamese_gloss_precision_status": FIX_STATUS,
            })
            review_updates[repair.guid] = row
    if (len(audit_updates), len(review_updates)) != (8, 4):
        raise ValueError("expected 8 audit-owned and 4 review-owned repairs")
    return audit_updates, review_updates


def prepare_manual_update(paths: ProjectPaths) -> dict:
    rows = load_jsonl(paths.manual_cards)
    key = ("restrain", "C1", "AWL", "")
    matches = [row for row in rows if (row.get("word"), row.get("cefr"), row.get("list"), row.get("variant") or "") == key]
    if len(matches) != 1 or matches[0].get("definition") != next(r.old_definition for r in REPAIRS if r.word == "restrain"):
        raise ValueError("restrain manual payload drift")
    row = dict(matches[0])
    row["definition"] = next(r.new_definition for r in REPAIRS if r.word == "restrain")
    provenance = dict(row.get("provenance") or {})
    provenance["review_batch"] = FIX_STATUS
    row["provenance"] = provenance
    return {key: row}


def prepare_ledger_updates(paths: ProjectPaths) -> dict:
    definitions = {repair.word: repair.new_definition for repair in REPAIRS}
    updates = {}
    for row in load_jsonl(paths.antonym_loop_decisions):
        word = row.get("word")
        if word not in {"sterile", "twist"}:
            continue
        new = dict(row)
        new["old_definition"] = definitions[word]
        updates[(row.get("word"), row.get("pos"), row.get("cefr"))] = new
    if len(updates) != 2:
        raise ValueError("missing sterile/twist lexical decision rows")
    return updates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--repair-applied-status", action="store_true")
    args = parser.parse_args(argv)
    paths = ProjectPaths(args.root)
    if args.repair_applied_status:
        repair_applied_status(paths)
        print("Restored prior fix_status values and recorded Vietnamese precision status.")
        return 0
    validate_preconditions(paths)
    audit_updates, review_updates = prepare_owner_updates(paths)
    manual_updates = prepare_manual_update(paths)
    ledger_updates = prepare_ledger_updates(paths)
    print("Validated Vietnamese gloss precision batch: 12 repairs.")
    if not args.apply:
        print("Dry-run only; pass --apply to mutate canonical inputs.")
        return 0
    rewrite_jsonl(
        paths.deck_audit_jsonl, audit_updates,
        lambda row: (row.get("word"), row.get("pos"), row.get("cefr")),
    )
    rewrite_jsonl(
        paths.non_oxford_non_c2_overrides, review_updates,
        lambda row: row.get("guid"),
    )
    rewrite_jsonl(
        paths.manual_cards, manual_updates,
        lambda row: (row.get("word"), row.get("cefr"), row.get("list"), row.get("variant") or ""),
    )
    rewrite_jsonl(
        paths.antonym_loop_decisions, ledger_updates,
        lambda row: (row.get("word"), row.get("pos"), row.get("cefr")),
    )
    decision_keys = {(ISSUE_TYPE, repair.guid) for repair in REPAIRS}
    rewrite_jsonl(
        paths.root / "data" / "review" / "quality_audit_decisions_20260711.jsonl",
        {}, lambda row: (row.get("issue_type"), row.get("guid")), drop_keys=decision_keys,
    )
    print("Applied 12 Vietnamese gloss precision repairs.")
    return 0


def repair_applied_status(paths: ProjectPaths) -> None:
    audit_rows = load_jsonl(paths.deck_audit_jsonl)
    audit_words = {repair.word for repair in REPAIRS if repair.owner == "audit"}
    audit_updates = {}
    for row in audit_rows:
        if row.get("word") not in audit_words:
            continue
        new = dict(row)
        new["fix_status"] = PRIOR_FIX_STATUS[row["word"]]
        new["vietnamese_gloss_precision_status"] = FIX_STATUS
        audit_updates[(row.get("word"), row.get("pos"), row.get("cefr"))] = new
    review_words = {repair.word for repair in REPAIRS if repair.owner == "review"}
    review_updates = {}
    for row in load_jsonl(paths.non_oxford_non_c2_overrides):
        if row.get("word") not in review_words:
            continue
        new = dict(row)
        new["fix_status"] = PRIOR_FIX_STATUS[row["word"]]
        new["vietnamese_gloss_precision_status"] = FIX_STATUS
        review_updates[row.get("guid")] = new
    if (len(audit_updates), len(review_updates)) != (8, 4):
        raise ValueError("could not restore all 12 owner statuses")
    rewrite_jsonl(
        paths.deck_audit_jsonl, audit_updates,
        lambda row: (row.get("word"), row.get("pos"), row.get("cefr")),
    )
    rewrite_jsonl(
        paths.non_oxford_non_c2_overrides, review_updates,
        lambda row: row.get("guid"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
