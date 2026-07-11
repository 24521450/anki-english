#!/usr/bin/env python3
"""Apply the reviewed 2026-07-11 sense-grouping decisions."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from src.config import ProjectPaths
from src.deck_builder.gloss_hygiene import normalize_gloss


FIX_STATUS = "sense_grouping_review_20260711"
RETIRED_GUIDS = {"blK!z$J^4}", "OZZPa?0t@2"}
UNCHANGED_KEEP_GUIDS = {
    "5h{~9ioTEb", "/xUiXso]~Q", "D0tq!F6I2+",
    "Hd?Kj:WO(B", "NQD8xUt1~7", "s>o7[6qaNE",
}


@dataclass(frozen=True, slots=True)
class Repair:
    guid: str
    word: str
    owner: str
    definition: str
    groups: tuple[tuple[int, ...], ...]
    example: str | None = None
    collocations: str | None = None


def R(guid, word, owner, definition, groups, example=None, collocations=None):
    return Repair(guid, word, owner, definition, tuple(tuple(x) for x in groups), example, collocations)


REPAIRS: tuple[Repair, ...] = (
    # Previously confirmed errors.
    R("A5Qf4PnHc~", "accessible", "audit", "easy to reach, use, or understand (dễ tiếp cận, sử dụng hoặc hiểu)", ((0, 1),)),
    R("v|KhBdI7YW", "barrier", "review", "thing that blocks or separates (rào cản/vật ngăn cách)", ((0, 1),)),
    R("T_O[&1kqgj", "cheer", "audit", "shout to show support or joy (tiếng reo hò/cổ vũ)", ((0, 1),)),
    R("EGfvQ,O0Ex", "conversion", "audit", "change to another form, use, or belief (sự chuyển đổi/cải đạo)", ((0, 1),)),
    R("xN5EPI^eD:", "corrosive", "review", "gradually causing physical or other damage (ăn mòn/hủy hoại dần)", ((0, 1),)),
    R("D=q[jvGK>:", "erode", "review", "gradually wear away or reduce sth (xói mòn/làm suy giảm)", ((0, 1),)),
    R("lQGcbzBEL6", "exploit", "audit", "use sb/sth for advantage, often unfairly (tận dụng hoặc bóc lột)", ((0, 1),)),
    R("ii5|!Y:am%", "extend", "review", "make sth longer, larger, longer-lasting, or wider in range (kéo dài, mở rộng hoặc gia hạn)", ((0, 1, 2),)),
    R('"g#O>ZU224s"', "fatal", "audit", "causing death, failure, or disaster (gây chết người hoặc thất bại nghiêm trọng)", ((0, 1),)),
    R("M+R`%<w:~e", "flesh", "audit", "soft tissue of a body or fruit (thịt cơ thể/thịt quả)", ((0, 1),)),
    R("guC:t$Wa&R", "handful", "audit", "small amount or number (một nắm/một số ít)", ((0, 1),)),
    R('"r`_r,m.#U]"', "implicate", "review", "show sb/sth may be involved in causing sth bad (cho thấy có liên quan/nguyên nhân)", ((0, 1),)),
    R("I$]g:$KZ^x", "inadequate", "audit", "not sufficient in quality, amount, or ability (không đủ/kém)", ((0, 1),)),
    R('"es7Z!#IsVU"', "malleability", "review", "[specialist]ability to be shaped or easily changed (tính dễ uốn/thay đổi)", ((0, 1),)),
    R("q}27BMm.K", "mortality", "review", "state of being mortal (tính hữu hạn của đời người)|death rate or number of deaths (tỉ lệ/số ca tử vong)", ((0,), (1, 2))),
    R("hvagsZ]s>N", "opacity", "review", "quality of blocking light or being hard to understand (độ đục/sự mù mờ)", ((0, 1),)),
    R("z+v`@4q`|d", "persist", "audit", "continue despite difficulty or over time (kiên trì/tồn tại kéo dài)", ((0, 1),)),
    R("eIck0vDS71", "regulate", "audit", "control by rules or adjustment (quản lý/điều chỉnh)", ((0, 1),)),
    R("bLFX$65T|u", "retention", "review", "keeping sth or holding liquid/heat (sự giữ lại/giữ nước hoặc nhiệt)|ability to remember (khả năng ghi nhớ)", ((0, 1), (2,))),
    R("Id{{%Tk$<J", "stationary", "review", "not moving or changing (đứng yên/ổn định)", ((0, 1),)),
    R("pyVvx3L9Hu", "supercharged", "review", "made much more powerful than usual (được tăng lực/cực mạnh)", ((0, 1),)),
    R("m=R7psxD}c", "susceptible", "review", "easily physically or emotionally affected (dễ bị ảnh hưởng/xiêu lòng)|[formal]able to allow sth (có thể được)", ((0, 1), (2,))),
    R("V>-bjI<%(k", "trace", "audit", "find sth or its origin by careful search (truy tìm/truy nguồn)", ((0, 1),)),
    R("LD:NA=zzJA", "transcribe", "review", "write speech, data, or sounds down (chép lại/phiên âm)|arrange music for another instrument (chuyển soạn nhạc)", ((0, 1), (2,))),
    # Decisions recorded in design/sense_grouping_review.md.
    R("obxExIEKPe", "abstract", "audit", "abstract, not concrete or realistic (trừu tượng)", ((0, 1),)),
    R("soo&vtobWv", "anticipate", "audit", "expect and prepare (lường trước/dự đoán)|look forward to (mong đợi)", ((0, 1), (2,))),
    R("z,EGH`_O--", "breach", "audit", "violation/break an agreement (vi phạm)|break in relations (rạn nứt quan hệ)", ((0,), (1,)), "a breach of contract<br><br>The company breached the agreement.|a breach in relations"),
    R("vTq3[%A]Fr", "calculation", "audit", "using numbers (tính toán)|careful judgement (sự cân nhắc)", ((0,), (1,))),
    R("HnKNSSxR,Y", "carve", "audit", "cut shapes or words (chạm/khắc)|slice cooked meat (thái thịt)", ((0, 1), (2,)), "a carved doorway<br><br>They carved their initials on the desk.|Who's going to carve the turkey?"),
    R("Qf_tGCt0*,", "casualty", "audit", "person killed or injured (người thương vong)|victim of an event (nạn nhân)|emergency department (khoa cấp cứu)", ((0,), (1,), (2,))),
    R("AcaWR/tKSq", "charter", "audit", "rights/principles document (hiến chương)|founding permission (giấy phép thành lập)", ((0,), (1,))),
    R("oBMT-S8z`o", "contemplate", "audit", "consider doing sth (cân nhắc)|think deeply (suy ngẫm)|look carefully (ngắm nhìn)", ((0,), (1,), (1,)), "You're too young to be contemplating retirement.|She lay in bed, contemplating.|She contemplated him in silence.", "contemplate retirement/move/change<br><br>contemplate doing sth|contemplate your future|contemplate sb/sth in silence"),
    R("^9}nTPVuab", "crown", "audit", "royal headpiece (vương miện)|royal power (vương quyền)", ((0,), (1,)), "The crown was placed upon the new monarch's head.|land owned by the Crown<br><br>He gave up the crown."),
    R("Imny}3?tcm", "crush", "audit", "damage by pressing (ép/nghiền nát)|force into a small space (nhét vào chỗ chật)", ((0,), (1,))),
    R("$|_`hdAC|%", "denial", "audit", "reject the truth (phủ nhận/chối bỏ)|refuse a right (tước quyền)", ((0, 2), (1,))),
    R("K!*J?]x%.I", "distort", "audit", "change shape, sound or facts (làm/bóp méo)", ((0, 1),)),
    R("odm-*w)do.", "grocery", "audit", "food and household shop (tiệm tạp hóa)|food and household goods (hàng tạp hóa)", ((0,), (1,))),
    R('"Pi(3#rt}m@"', "linear", "audit", "in a line or series (theo đường thẳng/tuyến tính)", ((0, 1),)),
    R("Yx2{ya%fL7", "modest", "audit", "small or limited (nhỏ/vừa phải)|doesn't show off (khiêm tốn)", ((0,), (1,))),
    R("],rh8tuEgo", "neutral", "audit", "not taking sides (trung lập)|not strong or emotional (trung tính)", ((0,), (1,))),
    R("qk(Z~KPIVm", "oblivion", "review", "unconsciousness (mất ý thức)|being forgotten (sự lãng quên)|complete destruction (hủy diệt hoàn toàn)", ((0,), (1,), (2,))),
    R("kqXu~zWpmX", "prevail", "audit", "be common (phổ biến)|finally succeed (thắng thế)", ((0,), (1,))),
    R("Ix&&{f]Rfd", "query", "audit", "question or doubt (câu hỏi/thắc mắc)|question mark (dấu hỏi)", ((0,), (1,))),
    R('"LMrC=NK#x2"', "slash", "audit", "cut violently (rạch/chém)|reduce a lot (cắt giảm mạnh)", ((0,), (1,))),
    R("qY[R!q3,p[", "tighten", "audit", "make or become tight (siết/căng chặt)|make stricter (thắt chặt)", ((0, 2), (1,))),
    R('"2#7u*>aPi"', "vacuum", "audit", "empty space or gap (chân không/khoảng trống)", ((0, 1),)),
)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def grouped(value: str, groups: tuple[tuple[int, ...], ...]) -> str:
    chunks = value.split("|")
    if max(i for group in groups for i in group) >= len(chunks):
        raise ValueError(f"cannot group {value!r} with {groups!r}")
    return "|".join("<br><br>".join(chunks[i] for i in group) for group in groups)


def validate_preconditions(paths: ProjectPaths) -> dict[str, dict]:
    cards = {row["guid"]: row for row in load_jsonl(paths.anki_notes_jsonl)}
    if len(REPAIRS) != 46 or len({r.guid for r in REPAIRS}) != 46:
        raise ValueError("sense-grouping manifest must contain 46 unique repairs")
    for repair in REPAIRS:
        card = cards.get(repair.guid)
        if not card or card.get("word") != repair.word:
            raise ValueError(f"built-card drift for {repair.guid!r}/{repair.word}")
        if len(card.get("definition", "").split("|")) < max(i for g in repair.groups for i in g) + 1:
            raise ValueError(f"sense-count drift for {repair.word}")
    for guid in RETIRED_GUIDS | UNCHANGED_KEEP_GUIDS | {"fxDIz0`1%."}:
        if guid not in cards:
            raise ValueError(f"missing reviewed GUID {guid!r}")
    return cards


def update_owner_rows(paths: ProjectPaths, cards: dict[str, dict]) -> None:
    by_guid = {r.guid: r for r in REPAIRS}
    audit_repairs = {(r.word, cards[r.guid]["pos"], cards[r.guid]["cefr"]): r for r in REPAIRS if r.owner == "audit"}
    audit_rows = load_jsonl(paths.deck_audit_jsonl)
    seen = set()
    for row in audit_rows:
        key = (row.get("word"), row.get("pos"), row.get("cefr"))
        repair = audit_repairs.get(key)
        if not repair:
            continue
        card = cards[repair.guid]
        hygiene = normalize_gloss(repair.definition)
        row.update({
            "gloss_after": hygiene.gloss, "separator": hygiene.separator,
            "rule_applied": "reviewed_sense_grouping", "gloss_word_count": hygiene.gloss_word_count,
            "gate_status": "pass", "fix_status": FIX_STATUS,
            "example_after": repair.example or grouped(card["example"], repair.groups),
            "collocations_after": repair.collocations or card["collocations"],
        })
        seen.add(key)
    if seen != set(audit_repairs):
        raise ValueError(f"missing audit owners: {set(audit_repairs) - seen}")
    dump_jsonl(paths.deck_audit_jsonl, audit_rows)

    review_rows = load_jsonl(paths.non_oxford_non_c2_overrides)
    output = []
    seen_guids = set()
    for row in review_rows:
        guid = row.get("guid")
        if guid in RETIRED_GUIDS or guid == "fxDIz0`1%.":
            continue
        repair = by_guid.get(guid)
        if repair and repair.owner == "review":
            card = cards[guid]
            updates = {
                "Definition": repair.definition,
                "Example": repair.example or grouped(card["example"], repair.groups),
                "Collocations": repair.collocations or card["collocations"],
            }
            if repair.word in {"mortality", "retention"}:
                updates["sense_grouping_status"] = FIX_STATUS
            else:
                updates["fix_status"] = FIX_STATUS
            row.update(updates)
            seen_guids.add(guid)
        output.append(row)
    expected = {r.guid for r in REPAIRS if r.owner == "review"}
    if seen_guids != expected:
        raise ValueError(f"missing review owners: {expected - seen_guids}")
    dump_jsonl(paths.non_oxford_non_c2_overrides, output)


def update_registry_and_manual(paths: ProjectPaths, cards: dict[str, dict]) -> None:
    registry = load_jsonl(paths.card_registry)
    original_temporal = None
    for row in registry:
        if row.get("guid") in RETIRED_GUIDS:
            row["status"] = "retired"
        if row.get("guid") == "fxDIz0`1%.":
            row["variant"] = "general_formal"
            original_temporal = row
    if original_temporal is None:
        raise ValueError("missing temporal registry row")
    if any(row.get("guid") == "t3mpAnat01" for row in registry):
        raise ValueError("temporal anatomy GUID already exists")
    anatomy_registry = dict(original_temporal)
    anatomy_registry.update({"variant": "anatomy", "guid": "t3mpAnat01"})
    registry.append(anatomy_registry)
    dump_jsonl(paths.card_registry, registry)

    by_guid = {r.guid: r for r in REPAIRS}
    manual = load_jsonl(paths.manual_cards)
    for row in manual:
        target = next((r for r in REPAIRS if r.word == row.get("word") and r.word in {"mortality", "retention"}), None)
        if target:
            card = cards[target.guid]
            row.update({
                "definition": target.definition,
                "example": grouped(card["example"], target.groups),
                "collocations": card["collocations"],
                "synonyms": "|".join("" for _ in target.groups),
                "antonyms": "|".join("" for _ in target.groups),
            })

    temporal = cards["fxDIz0`1%."]
    base = {
        "word": "temporal", "cefr": "UNCLASSIFIED", "list": "NO_LIST",
        "wordfamily": temporal.get("wordfamily", ""), "ipa": temporal["ipa"],
        "uk_audio": temporal["uk_audio"], "us_audio": temporal["us_audio"],
        "source1": temporal["source1"], "source2": temporal["source2"],
        "idioms": temporal.get("idioms", ""),
        "provenance": {"source": "manual_card_fills", "cefr_source": "Oxford", "review_batch": FIX_STATUS, "ledger_pos": "adjective"},
    }
    general = dict(base)
    general.update({
        "variant": "general_formal",
        "definition": "[formal]worldly, not spiritual (thuộc thế tục)|[formal]related to time (thuộc thời gian)",
        "example": "|".join(temporal["example"].split("|")[:2]),
        "collocations": "temporal power/authority/matters|temporal dimension/order/sequence<br><br>spatial and temporal",
        "synonyms": "|", "antonyms": "|",
        "tags": temporal["tags"] + " SenseVariant::general_formal",
    })
    anatomy = dict(base)
    anatomy.update({
        "variant": "anatomy", "definition": "[anatomy]near the temple (thuộc thái dương)",
        "example": temporal["example"].split("|")[2], "collocations": "temporal lobe/bone/artery",
        "synonyms": "", "antonyms": "", "tags": temporal["tags"] + " SenseVariant::anatomy",
    })
    manual = [row for row in manual if row.get("word") != "temporal"] + [general, anatomy]
    dump_jsonl(paths.manual_cards, manual)


def update_decision_ledgers(paths: ProjectPaths) -> None:
    definitions = {r.word: r.definition for r in REPAIRS}
    rows = load_jsonl(paths.antonym_loop_decisions)
    expected = {"abstract", "inadequate", "modest", "neutral", "stationary"}
    seen = set()
    for row in rows:
        word = row.get("word")
        if word in expected:
            row["old_definition"] = definitions[word]
            seen.add(word)
    if seen != expected:
        raise ValueError(f"missing antonym decisions: {expected - seen}")
    if any(row.get("word") == "oblivion" for row in rows):
        raise ValueError("oblivion antonym-loop decision already exists")
    rows.append({
        "word": "oblivion", "pos": "noun", "cefr": "UNCLASSIFIED",
        "old_definition": definitions["oblivion"], "decision": "keep_basic_negation",
        "new_definition": "",
        "reason": "The detector only matches the un- prefix; unconsciousness is the basic accurate noun.",
        "batch": "sense_grouping_review", "reviewed_at": "20260711",
    })
    dump_jsonl(paths.antonym_loop_decisions, rows)


def add_sense_label_override(paths: ProjectPaths) -> None:
    path = paths.root / "data" / "review" / "sense_label_overrides.jsonl"
    rows = load_jsonl(path)
    if any(row.get("guid") == "xN5EPI^eD:" for row in rows):
        raise ValueError("corrosive sense-label override already exists")
    rows.append({
        "guid": "xN5EPI^eD:", "word": "corrosive", "pos": "adjective",
        "cefr": "UNCLASSIFIED", "source_definition": "tending to damage something gradually",
        "definition_chunk": "gradually causing physical or other damage (ăn mòn/hủy hoại dần)",
        "action": "skip",
        "reason": "The grouped physical and figurative senses do not share the formal source label.",
    })
    dump_jsonl(path, rows)


def add_breach_relation_overrides(paths: ProjectPaths) -> None:
    path = paths.synonym_example_overrides
    rows = load_jsonl(path)
    additions = (
        ("a breach of contract", "The curated noun example has no source synonym annotation."),
        ("The company breached the agreement.", "The curated learner-facing verb example has no source synonym annotation."),
    )
    existing = {(row.get("guid"), row.get("original_example")) for row in rows}
    for example, reason in additions:
        if ("z,EGH`_O--", example) in existing:
            raise ValueError(f"breach relation override already exists for {example!r}")
        rows.append({
            "guid": "z,EGH`_O--", "word": "breach", "pos": "noun, verb", "cefr": "C1",
            "original_example": example, "action": "skip", "reason": reason,
        })
    dump_jsonl(path, rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--repair-applied-collocations", action="store_true")
    args = parser.parse_args(argv)
    paths = ProjectPaths(args.root)
    if args.repair_applied_collocations:
        restore_applied_collocations(paths)
        print("Restored pre-batch collocations and exact-source metadata.")
        return 0
    cards = validate_preconditions(paths)
    print("Validated sense-grouping review: 46 repairs, 6 keeps, 2 retirements, 1 split.")
    if not args.apply:
        print("Dry-run only; pass --apply to mutate canonical inputs.")
        return 0
    update_owner_rows(paths, cards)
    update_registry_and_manual(paths, cards)
    update_decision_ledgers(paths)
    add_sense_label_override(paths)
    add_breach_relation_overrides(paths)
    print("Applied canonical sense-grouping decisions.")
    return 0


def restore_applied_collocations(paths: ProjectPaths) -> None:
    """Repair a partial 2026-07-11 run that grouped non-aligned collocation cells."""
    snapshot = paths.root / "data" / "build" / "English Academic Vocabulary.txt"
    old_by_guid = {}
    for line in snapshot.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if len(cells) >= 9:
            old_by_guid[cells[0]] = cells[8]
    missing = {repair.guid for repair in REPAIRS} - set(old_by_guid)
    if missing:
        raise ValueError(f"pre-batch export lacks repair GUIDs: {sorted(missing)!r}")

    audit_by_identity = {
        (repair.word, repair.guid): old_by_guid[repair.guid]
        for repair in REPAIRS if repair.owner == "audit"
    }
    cards = {row["guid"]: row for row in load_jsonl(paths.anki_notes_jsonl)}
    audit_rows = load_jsonl(paths.deck_audit_jsonl)
    for row in audit_rows:
        matches = [
            collocations for (word, guid), collocations in audit_by_identity.items()
            if word == row.get("word") and cards.get(guid, {}).get("pos") == row.get("pos")
            and cards.get(guid, {}).get("cefr") == row.get("cefr")
        ]
        if matches:
            row["collocations_after"] = matches[0]
    dump_jsonl(paths.deck_audit_jsonl, audit_rows)

    review_rows = load_jsonl(paths.non_oxford_non_c2_overrides)
    review_guids = {repair.guid: repair for repair in REPAIRS if repair.owner == "review"}
    for row in review_rows:
        repair = review_guids.get(row.get("guid"))
        if not repair:
            continue
        row["Collocations"] = old_by_guid[repair.guid]
        if repair.word in {"mortality", "retention"}:
            row["fix_status"] = "exact_source_cefr_rescue_20260710"
            row["sense_grouping_status"] = FIX_STATUS
    dump_jsonl(paths.non_oxford_non_c2_overrides, review_rows)

    manual_rows = load_jsonl(paths.manual_cards)
    manual_guid_by_word = {repair.word: repair.guid for repair in REPAIRS}
    for row in manual_rows:
        guid = manual_guid_by_word.get(row.get("word"))
        if guid and row.get("word") in {"mortality", "retention"}:
            row["collocations"] = old_by_guid[guid]
    dump_jsonl(paths.manual_cards, manual_rows)


if __name__ == "__main__":
    raise SystemExit(main())
