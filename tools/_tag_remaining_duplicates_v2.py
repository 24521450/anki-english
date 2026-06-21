import json
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
JSONL_PATH = ROOT / "data" / "anki_notes.jsonl"
TXT_PATH = ROOT / "English Academic Vocabulary.txt"

# Actions: (word, cefr, keep_guid, [delete_guids], new_pos_for_kept_card)
ACTIONS = [
    ("harbour", "UNCLASSIFIED", "m}g1cKg({G", ["E|VRlqHFaR"], "noun, verb"),
    ("converse", "UNCLASSIFIED", "hu-nITV:EB", ["K7zhEf@gQc"], "adjective, noun, verb"),
    ("yield", "C1", "@NbB`9?Tqc", ["B/1sP6b=Vp"], "noun, verb"),
    ("advocate", "C1", "km/DeO(0eI", ["jaiU{W!fpZ"], "noun, verb"),
    ("meantime", "C1", "N|.UFNN`SW", ["mNX:dYb0k|", "5}!i8CNalf"], "adverb, noun"),
    ("solo", "C1", "%nP=oVYMv%", ["o|(e_N7[{l", "sJl.,2f2(E"], "adjective, noun"),
    ("worship", "C1", ",qqw,<G4mQ", ["mHG-]^r0eD", "h,&:?dJ*WG"], "noun, verb"),
    ("devote", "B2", "d0+rK3^u+.", ["NF|MJ_CV/$", "?+L24(Wf/l"], "phrasal verb, verb"),
    ("downtown", "B2", "1@?w:Me2(:", ["lPPUE/./{Z", "7l*pR<!Ihr"], "adjective, adverb, noun"),
    ("deprive", "C1", "8VcO1&GtcB", ["&OYa%Gx-_p", "G|oDf_Z1He"], "phrasal verb, verb"),
    ("derive", "B2", "dyWb^v=0``", ["w/Kbqf!h5&", "158y|F:/DZ"], "phrasal verb, verb"),
    ("full-time", "B2", "V[(*[^OCYi", ["/!5`Byr<$;", ">6CfnozWw}"], "adjective, adverb"),
    ("nursing", "B2", "_m[}),)MM.", ["@u?S[yfQCH"], "noun, adjective"),
    ("part-time", "B2", "&;tpjv4mxi", ["1+vIQ`WS-j", "Y`Aa$3_<<+"], "adjective, adverb"),
    ("deposit", "C1", "b6cD1Ck8TE", ["We&|,]U3g{"], "noun, verb"),
    ("mainland", "C1", "K_[xKnI.vU", ["$3+OsHpm@0"], "adjective, noun"),
    ("accused", "C1", "sthZ48fq=K", ["R86K[VYA&/"], None),
]


def _add_delete_tag(tags_str: str) -> str:
    tokens = tags_str.split() if tags_str else []
    if "delete" not in tokens:
        tokens.append("delete")
    return " ".join(tokens)


def tag_jsonl():
    if not JSONL_PATH.exists():
        print("anki_notes.jsonl not found, skipping tag_jsonl")
        return
    
    cards = []
    with JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cards.append(json.loads(line))

    guid_to_card = {c["guid"]: c for c in cards}
    kept_updated = 0
    deleted_tagged = 0
    missing = 0

    for word, cefr, keep_guid, delete_guids, new_pos in ACTIONS:
        keep_card = guid_to_card.get(keep_guid)
        if keep_card and new_pos is not None:
            if keep_card.get("pos") != new_pos:
                keep_card["pos"] = new_pos
                kept_updated += 1
                print(f"Updated JSONL kept card {keep_guid} ({word}) POS to {new_pos}")
        
        for dg in delete_guids:
            del_card = guid_to_card.get(dg)
            if del_card:
                old_tags = del_card.get("tags", "")
                new_tags = _add_delete_tag(old_tags)
                if new_tags != old_tags:
                    del_card["tags"] = new_tags
                    deleted_tagged += 1
                    print(f"Tagged JSONL card {dg} ({word}) with 'delete'")
            else:
                missing += 1

    # Write back
    tmp_path = JSONL_PATH.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    tmp_path.replace(JSONL_PATH)

    print(f"JSONL: Kept POS updated: {kept_updated}, Delete tagged: {deleted_tagged}, Missing: {missing}")


def tag_txt():
    if not TXT_PATH.exists():
        print("TXT file not found, skipping tag_txt")
        return

    lines = TXT_PATH.read_text(encoding="utf-8").splitlines()
    header_lines = []
    body_lines = []
    for line in lines:
        if line.startswith("#") or not line.strip():
            header_lines.append(line)
        else:
            body_lines.append(line)

    kept_updated = 0
    deleted_tagged = 0
    missing = 0

    # Build action index
    keep_actions = {keep_guid: new_pos for _, _, keep_guid, _, new_pos in ACTIONS if new_pos is not None}
    delete_actions = {}
    for word, _, _, delete_guids, _ in ACTIONS:
        for dg in delete_guids:
            delete_actions[dg] = word

    new_body = []
    seen_delete_guids = set()
    seen_keep_guids = set()

    for line in body_lines:
        parts = line.split("\t")
        if len(parts) < 17:
            new_body.append(line)
            continue
        guid = parts[0]

        if guid in keep_actions:
            new_pos = keep_actions[guid]
            if parts[4] != new_pos:
                parts[4] = new_pos
                kept_updated += 1
                print(f"Updated TXT kept card {guid} ({parts[3]}) POS to {new_pos}")
            seen_keep_guids.add(guid)

        elif guid in delete_actions:
            old_tags = parts[16]
            new_tags = _add_delete_tag(old_tags)
            if new_tags != old_tags:
                parts[16] = new_tags
                deleted_tagged += 1
                print(f"Tagged TXT card {guid} ({parts[3]}) with 'delete'")
            seen_delete_guids.add(guid)

        new_body.append("\t".join(parts))

    # Check missing
    for _, _, keep_guid, delete_guids, _ in ACTIONS:
        if keep_guid not in seen_keep_guids:
            # We don't complain if new_pos is None, but let's check general presence
            pass
        for dg in delete_guids:
            if dg not in seen_delete_guids:
                missing += 1

    new_txt = "\n".join(header_lines + new_body) + "\n"
    TXT_PATH.write_text(new_txt, encoding="utf-8")

    print(f"TXT:   Kept POS updated: {kept_updated}, Delete tagged: {deleted_tagged}, Missing: {missing}")


def main():
    print("Tagging remaining 17 duplicate groups...")
    tag_jsonl()
    tag_txt()


if __name__ == "__main__":
    main()
