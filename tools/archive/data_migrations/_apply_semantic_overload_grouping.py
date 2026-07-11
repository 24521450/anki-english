#!/usr/bin/env python3
"""Group the reviewed 2026-07-11 semantic-overload display senses."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.gloss_hygiene import normalize_gloss


FIX_STATUS = "semantic_overload_grouped_20260711"


@dataclass(frozen=True, slots=True)
class Grouping:
    guid: str
    word: str
    pos: str
    cefr: str
    definition: str
    example: str
    collocations: str
    owner: str

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.word, self.pos, self.cefr)


GROUPINGS: tuple[Grouping, ...] = (
    Grouping(
        "wLmSHlp*-o", "appreciation", "noun", "C1",
        "enjoyment, recognition, or understanding (sự đánh giá cao/hiểu rõ)|"
        "gratitude (sự cảm kích)|rise in value (sự tăng giá)",
        "She shows little appreciation of good music.<br><br>"
        "I had no appreciation of the problems they faced.|"
        "I would like to express my appreciation and thanks to you all.|"
        "an appreciation in the value of the house",
        "appreciation of music/problems|show/express appreciation|"
        "in appreciation of sth|appreciation in value",
        "audit",
    ),
    Grouping(
        "d*.q=-dk0c", "clash", "noun", "C1",
        "fight, disagreement, or opposition (xung đột/trái ngược)|"
        "time conflict (trùng lịch)|metal noise (tiếng va chạm kim loại)",
        "Clashes broke out between police and demonstrators.<br><br>"
        "a clash of interests/opinions/cultures|"
        "a clash in the timetable/schedule|a clash of cymbals/swords",
        "clash between/with sb|clash over sth|clash of interests/opinions/cultures|"
        "timetable/schedule clash|clash of cymbals/swords",
        "audit",
    ),
    Grouping(
        '"b#<%hLUOt*"', "critical", "adjective", "B2",
        "giving judgments or disapproval (phê bình/chỉ trích)|"
        "very important for what happens next (then chốt)|"
        "serious and dangerous (nguy kịch)",
        "You should just ignore any critical comments.<br><br>"
        "His latest film attracted enthusiastic critical comment from cinema-goers.|"
        "Industry leaders are working together to address this critical issue.|"
        "One of the victims of the fire remains in a critical condition.",
        "critical comment/attitude/report/analysis/review|critical issue/role/factor|"
        "critical condition/stage",
        "review",
    ),
    Grouping(
        "M*)7h:drS?", "gut", "noun", "C1",
        "intestines or belly (ruột/bụng)|[informal]courage (gan/dũng khí)|"
        "instinctive feeling (linh cảm)",
        "It can take up to 72 hours for food to pass through the gut.<br><br>"
        "He had a bit of a gut on him, but otherwise he was quite skinny.|"
        "He doesn't have the guts to walk away from a well-paid job.|"
        "I had a feeling in my guts that something was wrong.",
        "pass through gut|beer gut|have guts|gut feeling/instinct",
        "audit",
    ),
    Grouping(
        "l$|6.M@.<A", "harsh", "adjective", "C1",
        "cruel, severe, difficult, or unpleasant (khắc nghiệt/nghiêm khắc)|"
        "too strong or ugly (chói/gắt)|unpleasant to hear (chói tai)",
        "The punishment was harsh and unfair.<br><br>a harsh winter/wind/climate|"
        "harsh colours|‘Stop it!’ she said in a harsh voice.",
        "harsh punishment/criticism/words|harsh winter/conditions|"
        "harsh light/colours|harsh voice",
        "audit",
    ),
    Grouping(
        "IciJO]*6Jw", "humanity", "noun", "C1",
        "all people or human nature (nhân loại/nhân tính)|kindness (lòng nhân đạo)|"
        "arts subjects (nhân văn học)",
        "He was found guilty of crimes against humanity.<br><br>"
        "The story was used to emphasize the humanity of Jesus.|"
        "The judge was praised for his courage and humanity.|"
        "The college offers a wide range of courses in the arts and humanities.",
        "crimes against humanity|common humanity|humanity and compassion|arts and humanities",
        "audit",
    ),
    Grouping(
        '"ctz#yxNYg."', "identification", "noun", "C1",
        "identifying sb/sth or proof of identity (sự nhận dạng/giấy tờ tùy thân)|"
        "feeling connected (sự đồng cảm/gắn bó)|"
        "linking one thing with another (sự liên hệ)",
        "The identification of the crash victims was a long and difficult task.<br><br>"
        "Can I see some identification, please?|"
        "her emotional identification with the play’s heroine|"
        "the voters’ identification of the Democrats with high taxes",
        "identification of victims/problems|show/ask for identification|photo identification|"
        "identification with sb|identification of A with B",
        "audit",
    ),
    Grouping(
        "hE-|%ml%t*", "pop", "verb", "C1",
        "short sound or burst|[informal]move quickly|appear suddenly",
        "the sound of corks popping<br><br>"
        "She jumped as someone popped a balloon behind her.|"
        "I'll pop over and see you this evening.|"
        "He popped his head around the door and said hello.<br><br>"
        "The window opened and a dog's head popped out.",
        "",
        "audit",
    ),
    Grouping(
        "si$OijE.g9", "provision", "noun", "C1",
        "supply of needed things, including food/drink "
        "(sự cung cấp/lương thực dự trữ)|preparation for future (sự chuẩn bị)|"
        "legal condition (điều khoản)",
        "housing provision<br><br>We have enough provisions to last us two weeks.|"
        "He had already made provisions for (= planned for the financial future of) "
        "his wife and children before the accident.|"
        "The same provisions apply to foreign-owned companies.",
        "provision of healthcare/housing|stock up on provisions|make provision for sth|"
        "provisions of law/lease",
        "audit",
    ),
    Grouping(
        '"j>(#&<;AW0"', "sterile", "adjective", "UNCLASSIFIED",
        "unable to produce young, crops, or useful results "
        "(vô sinh/cằn cỗi/vô ích)|free from bacteria (vô trùng)|"
        "cold and lacking character (lạnh lẽo/thiếu sức sống)",
        "sterile soil<br><br>We need to focus on solving the problem rather than "
        "continuing the sterile debate on how it came about.|sterile bandages|"
        "The room felt cold and sterile.",
        "sterile male/female/soil|become sterile|sterile debate/argument/discussion|"
        "sterile bandages/needle/equipment|keep sth sterile|"
        "sterile room/office/environment",
        "review",
    ),
)

KEEP_GUIDS = {"B7[0+R><3N", "ka@NZF]8Qa"}
LEDGER_WORDS = {"appreciation", "harsh", "sterile"}


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _index(rows: list[dict], key_fn) -> dict:
    result = {}
    for row in rows:
        key = key_fn(row)
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = row
    return result


def validate_preconditions(paths: ProjectPaths) -> None:
    if len(GROUPINGS) != 10 or len(KEEP_GUIDS) != 2:
        raise ValueError("semantic-overload manifest must contain 10 repairs and 2 keeps")
    cards = _index(load_jsonl(paths.anki_notes_jsonl), lambda row: row.get("guid"))
    audit = _index(
        load_jsonl(paths.deck_audit_jsonl),
        lambda row: (row.get("word"), row.get("pos"), row.get("cefr")),
    )
    reviews = _index(
        load_jsonl(paths.non_oxford_non_c2_overrides),
        lambda row: row.get("guid"),
    )
    for grouping in GROUPINGS:
        card = cards.get(grouping.guid)
        if not card or (
            card.get("word"), card.get("pos"), card.get("cefr")
        ) != grouping.identity:
            raise ValueError(f"built identity drift for {grouping.guid!r}")
        if len((card.get("definition") or "").split("|")) != 4:
            raise ValueError(f"expected four pre-migration senses for {grouping.word}")
        if grouping.owner == "audit" and grouping.identity not in audit:
            raise ValueError(f"missing audit owner for {grouping.identity!r}")
        if grouping.owner == "review" and grouping.guid not in reviews:
            raise ValueError(f"missing review owner for {grouping.guid!r}")

    for guid in KEEP_GUIDS:
        card = cards.get(guid)
        if not card or len((card.get("definition") or "").split("|")) != 4:
            raise ValueError(f"reviewed keep drift for {guid!r}")


def prepare_updates(paths: ProjectPaths) -> tuple[dict, dict, dict]:
    audit_updates = {}
    review_updates = {}
    by_identity = {grouping.identity: grouping for grouping in GROUPINGS}
    by_guid = {grouping.guid: grouping for grouping in GROUPINGS}

    for row in load_jsonl(paths.deck_audit_jsonl):
        key = (row.get("word"), row.get("pos"), row.get("cefr"))
        grouping = by_identity.get(key)
        if not grouping or grouping.owner != "audit":
            continue
        new = dict(row)
        hygiene = normalize_gloss(grouping.definition)
        new.update({
            "gloss_after": hygiene.gloss,
            "separator": hygiene.separator,
            "rule_applied": "trimmed_multisense",
            "gloss_word_count": hygiene.gloss_word_count,
            "gate_status": "pass",
            "fix_status": FIX_STATUS,
            "example_after": grouping.example,
            "collocations_after": grouping.collocations,
        })
        audit_updates[key] = new

    for row in load_jsonl(paths.non_oxford_non_c2_overrides):
        guid = row.get("guid")
        grouping = by_guid.get(guid)
        if not grouping or grouping.owner != "review":
            continue
        new = dict(row)
        new.update({
            "Definition": grouping.definition,
            "Example": grouping.example,
            "Collocations": grouping.collocations,
            "fix_status": FIX_STATUS,
        })
        review_updates[guid] = new

    ledger_updates = {}
    grouping_by_word = {grouping.word: grouping for grouping in GROUPINGS}
    for row in load_jsonl(paths.antonym_loop_decisions):
        word = row.get("word")
        if word not in LEDGER_WORDS:
            continue
        grouping = grouping_by_word[word]
        if (row.get("pos"), row.get("cefr")) != (grouping.pos, grouping.cefr):
            raise ValueError(f"lexical decision identity drift for {word}")
        new = dict(row)
        new["old_definition"] = grouping.definition
        ledger_updates[(word, grouping.pos, grouping.cefr)] = new

    if (len(audit_updates), len(review_updates), len(ledger_updates)) != (8, 2, 3):
        raise ValueError(
            "unexpected update counts: "
            f"audit={len(audit_updates)} review={len(review_updates)} "
            f"ledger={len(ledger_updates)}"
        )
    return audit_updates, review_updates, ledger_updates


def rewrite_jsonl(path: Path, updates: dict, key_fn) -> None:
    output = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = key_fn(row)
        if key in updates:
            output.append(json.dumps(updates[key], ensure_ascii=False, separators=(",", ":")))
            seen.add(key)
        else:
            output.append(line)
    if seen != set(updates):
        raise ValueError(f"missing updates in {path}: {set(updates) - seen}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    paths = ProjectPaths(args.root)
    validate_preconditions(paths)
    audit_updates, review_updates, ledger_updates = prepare_updates(paths)
    print("Validated semantic-overload batch: 10 grouped, 2 reviewed keeps.")
    if not args.apply:
        print("Dry-run only; pass --apply to mutate canonical inputs.")
        return 0
    rewrite_jsonl(
        paths.deck_audit_jsonl,
        audit_updates,
        lambda row: (row.get("word"), row.get("pos"), row.get("cefr")),
    )
    rewrite_jsonl(
        paths.non_oxford_non_c2_overrides,
        review_updates,
        lambda row: row.get("guid"),
    )
    rewrite_jsonl(
        paths.antonym_loop_decisions,
        ledger_updates,
        lambda row: (row.get("word"), row.get("pos"), row.get("cefr")),
    )
    print("Applied canonical grouping.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
