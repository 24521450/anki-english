import hashlib
import json
from pathlib import Path

from tools.archive.data_migrations._apply_vietnamese_gloss_precision_review import REPAIRS


ROOT = Path(__file__).resolve().parents[2]
UNCHANGED_CONTENT_SHA256 = {
    "vV~Qxd}bCU": "9c6ec06acbf7bab55a0ced8fa6fad853759049e5797f22ea286a9f57f01bb9c5",
    "LK-&12E9p`": "d3242e48fcbd5c20ca63bfed51864407c7fae8b9b31313f158ae89b74247498d",
    "I%>-ZZz|RF": "a47349861e2acef5c147e2e158cc01b971091f087477d4c8cf23396b98468f5e",
    "Ee?9B>!{wW": "f5c08641314369ddee25baf0f53e9a1c9d35a48a629bde5ad4e5cd22a321143a",
    "i/Mobs,`g1": "a8ed7881fdb048b89c6852f2109e7475c1f1d2431381ac2d538a865728c94177",
    "u$noUa&2=.": "be9009226c1a3283e0a2a569f96b5c9e45e5b3d48942c0187b1475ae22b7f5ff",
    "NQD8xUt1~7": "306d23d6ba86d6383c51efac984b7fb9fe8510501972c7ebb52561aa6d10b786",
    "_6Lky<ae`R": "d7961b6890d6378dea0987eb19dec10072e5c1f04a50668e245c1405f69d3ac9",
    "oz,$owM6W5": "ae3edb7ab6735b82ea4605cec9ed8866ab63cd87731b078caa77041287b09c77",
    '"j>(#&<;AW0"': "c9a8b6e41d2e032b710f10b9e4025b4d714eb0d4307faa634594121059d0e681",
    ")3<x>19pDQ": "822d53e280d0fa53a0583ab0ad1cbbbf9640a8e4c9d68c7ae57190c3ef1088a3",
    "vyZB3_Nz>K": "7ee6e2092958f7d64358f67ce245ff93ff09d2403fca4e40e6d990a3b9862a8a",
}


def _rows(path: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_repaired_definitions_match_their_canonical_owner_payloads():
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
        card = cards[repair.guid]
        assert card["definition"] == repair.new_definition
        owner = audit[repair.identity] if repair.owner == "audit" else reviews[repair.guid]
        content_hash = hashlib.sha256(
            (card["example"] + "\0" + card["collocations"]).encode()
        ).hexdigest()
        assert content_hash == UNCHANGED_CONTENT_SHA256[repair.guid]
        assert owner["vietnamese_gloss_precision_status"] == (
            "vietnamese_gloss_precision_review_20260711"
        )


def test_vietnamese_precision_decisions_are_removed_after_repairs():
    decisions = _rows("data/review/quality_audit_decisions_20260711.jsonl")
    repaired_guids = {repair.guid for repair in REPAIRS}
    assert not [
        row for row in decisions
        if row.get("issue_type") == "vietnamese_gloss_precision_review"
        and row.get("guid") in repaired_guids
    ]
