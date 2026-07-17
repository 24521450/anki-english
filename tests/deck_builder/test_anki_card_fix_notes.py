from __future__ import annotations

import json
import re
from collections import Counter

from src.config import ProjectPaths
from src.deck_builder.semantic_registry import render_registry_idiom_fields
from src.deck_builder.synonym_annotator import strip_synonym_annotations
from tools._detect_lexical_loops import detect_loops


PATHS = ProjectPaths()
SEMANTIC_FIELDS = {"definition", "example", "idioms"}


def _load_jsonl(path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _cards_by_guid() -> dict[str, dict]:
    return {row["guid"]: row for row in _load_jsonl(PATHS.anki_notes_jsonl)}


def _semantic_registry_by_guid() -> dict[str, dict]:
    return {row["guid"]: row for row in _load_jsonl(PATHS.semantic_registry)}


def _render_registry_definition(registry_row: dict) -> str:
    return "|".join(
        f"{sense['definition_en']} ({sense['definition_vi']})"
        for sense in registry_row["senses"]
    )


def _render_registry_example(registry_row: dict) -> str:
    return "|".join(
        "<br><br>".join(sense["examples"])
        for sense in registry_row["senses"]
    )


def _relation_terms(card: dict) -> list[str]:
    terms: list[str] = []
    for field in ("synonyms", "antonyms"):
        for group in re.split(r"\||<br\s*/?><br\s*/?>", card.get(field) or ""):
            terms.extend(term.strip() for term in group.split(",") if term.strip())
    return terms


def _without_layered_relation_annotations(text: str, card: dict) -> str:
    return strip_synonym_annotations(text, _relation_terms(card))


def _assert_registry_semantics(card: dict, registry_row: dict | None = None) -> None:
    if registry_row is None:
        registry_row = _semantic_registry_by_guid()[card["guid"]]

    assert (card["word"], card["pos"], card["cefr"]) == (
        registry_row["word"],
        registry_row["pos"],
        registry_row["cefr"],
    )
    assert card["definition"] == _render_registry_definition(registry_row)

    # ADR 0011 owns the base Example payload. Lexical-relation annotations are
    # deliberately layered later, so compare both sides with only those known
    # annotations removed; natural parentheticals remain significant.
    actual_example = _without_layered_relation_annotations(card["example"], card)
    expected_example = _without_layered_relation_annotations(
        _render_registry_example(registry_row), card
    )
    assert actual_example == expected_example
    expected_idioms, _ = render_registry_idiom_fields(registry_row.get("idioms") or [])
    assert card["idioms"] == expected_idioms


def _cards_by_identity() -> dict[tuple[str, str, str], dict]:
    rows = _load_jsonl(PATHS.anki_notes_jsonl)
    return {(row["word"], row["pos"], row["cefr"]): row for row in rows}


def _without_register_tags(definition: str) -> str:
    return "|".join(
        re.sub(r"^(?:\[[^]]+\])+", "", chunk)
        for chunk in definition.split("|")
    )


def _antonym_loop_decisions() -> list[dict]:
    return _load_jsonl(PATHS.antonym_loop_decisions)


def test_generated_semantics_match_the_promoted_semantic_registry():
    cards = _cards_by_guid()
    registry = _semantic_registry_by_guid()

    assert set(cards) == set(registry)
    for guid, registry_row in registry.items():
        _assert_registry_semantics(cards[guid], registry_row)


def test_anki_card_fix_notes_are_applied_to_generated_cards():
    cards = _cards_by_identity()
    expected = {
        ("forth", "adverb", "C1"): {
            "collocations": "set/go forth",
        },
        ("interim", "adjective", "C1"): {
            "definition": "temporary until replaced (tạm thời/lâm thời)",
        },
        ("manipulation", "noun", "C1"): {
            "definition": "dishonest control (sự thao túng)|skilled handling (thao tác/xử lý)",
        },
        ("thought-provoking", "adjective", "C1"): {
            "definition": "make people think deeply (gợi suy tư/đáng suy ngẫm)",
        },
        ("stroke", "noun", "B2"): {
            "definition": "hit with bat/racket (cú đánh)|single successful act (nước đi/khoảnh khắc bất chợt)",
            "collocations": "stroke a ball|beautiful/powerful stroke|a stroke of luck/genius/inspiration|a bold stroke",
        },
        ("contender", "noun", "C1"): {
            "definition": "possible winner (ứng viên có khả năng thắng/đối thủ nặng ký)",
        },
        ("accordance", "noun", "C1"): {
            "definition": "",
            "example": "",
            "idioms": (
                "in accordance with something :: as required by or according "
                "to :: in accordance with legal requirements"
            ),
        },
        ("dramatically", "adverb", "B2"): {
            "example": (
                "Prices have fallen dramatically.|The opera does not compare musically "
                "or dramatically with the composer's best work."
            ),
        },
        ("cutting", "noun", "C1"): {
            "definition": "newspaper piece removed (bài báo cắt ra)",
            "example": "newspaper/press cuttings",
            "collocations": "newspaper/press cutting|keep/save cuttings",
        },
        ("unveil", "verb", "C1"): {
            "example": (
                "The Queen unveiled a plaque to mark the official opening of the hospital."
                "<br><br>They will be unveiling (reveal) their new models at the Motor Show."
            ),
        },
        ("consistency", "noun", "C1"): {
            "definition": "same level or standard over time (sự ổn định/nhất quán)|thickness (độ đặc)",
        },
        ("guilt", "noun", "C1"): {
            "definition": (
                "feeling bad about doing sth wrong (cảm giác tội lỗi)|"
                "criminal responsibility (tội trạng)|"
                "blame or responsibility (trách nhiệm)"
            ),
        },
        ("counter", "verb", "C1"): {
            "definition": "argue against sth (phản bác)|act against bad effects (chống lại/khắc chế)",
        },
        ("coup", "noun", "C1"): {
            "definition": "sudden illegal takeover (đảo chính)|impressive achievement (thành công lớn/ngoạn mục)",
        },
        ("outrage", "noun, verb", "C1"): {
            "definition": (
                "extreme anger or an act that causes it (sự phẫn nộ/điều gây phẫn nộ)|"
                "make sb very angry (làm phẫn nộ)"
            ),
            "example": (
                "The judge's remarks caused public outrage.<br><br>"
                "No one has yet claimed responsibility for this latest terrorist outrage (atrocity).|"
                "He was outraged at the way he had been treated."
            ),
        },
        ("trail", "noun", "C1"): {
            "guid": "DPe6!OKrwD",
            "definition": "track or path (dấu vết/đường mòn)",
            "example": "a trail of blood",
            "collocations": "trail of blood/destruction|forest/tourist trail",
        },
        ("trail", "verb", "C1"): {
            "guid": "3GalxBKT!y",
            "definition": "drag behind (kéo lê)|walk behind slowly (lẽo đẽo theo)|be losing (bị dẫn trước)",
            "example": (
                "A jeep trailing a cloud of dust was speeding in my direction.|"
                "The kids trailed around after us while we shopped for clothes.|"
                "United were trailing 2–0 at half-time."
            ),
            "collocations": "trail behind/after sb|trail by points",
        },
        ("sensation", "noun", "C1"): {
            "example": (
                "a tingling/burning sensation<br><br>"
                "She seemed to have lost all sensation (feeling) in her arms.|"
                "He had the eerie sensation of being watched.|"
                "News of his arrest caused a sensation."
            ),
        },
        ("torture", "noun, verb", "C1"): {
            "guid": "D$)~Bq72HS",
            "definition": (
                "extreme pain or suffering (sự tra tấn/cực hình)|"
                "cause extreme pain or suffering (tra tấn/giày vò)"
            ),
            "example": (
                "Many of the refugees have suffered torture.<br><br>"
                "The interview was sheer torture from start to finish.|"
                "He spent his life tortured (torment) by the memories of his childhood."
            ),
            "collocations": (
                "use/suffer torture|mental/physical torture|sheer torture|"
                "torture prisoner/suspect"
            ),
        },
        ("bow", "noun, verb", "C1"): {
            "guid": "M[dNo,3q=f",
            "ipa": "/baʊ/",
            "definition": "bend head/body (cúi đầu/cúi chào)",
            "example": (
                "She gave a slight bow of her head in greeting.<br><br>"
                "He bowed low to the assembled crowd."
            ),
            "collocations": "give/make/take a bow|bow your head|bow to sb|bow low/down",
        },
        ("bow", "noun", "C1"): {
            "guid": "V3*Opcns6`",
            "ipa": "UK: /bəʊ/ | US: /boʊ/",
            "definition": "arrow weapon (cung)|loop knot (nơ)|violin stick (vĩ kéo đàn)",
            "example": (
                "He was armed with a bow and arrow.|to tie your shoelaces in a bow|"
                "She drew the bow across the strings."
            ),
            "collocations": "bow and arrow|draw/aim a bow|tie sth in a bow|violin bow",
        },
        ("hint", "noun", "C1"): {
            "guid": "l8^bnn+PFB",
            "definition": "indirect suggestion (gợi ý/ám chỉ)|small amount (chút)|practical advice (mẹo)",
            "example": (
                "He gave a broad hint (= one that was obvious) that he was thinking of retiring.|"
                "a hint (suggestion, trace) of a smile|handy hints (tip) on saving money"
            ),
            "collocations": "give/drop hint|hint of smile/sadness|handy/useful hints",
        },
        ("hint", "verb", "C1"): {
            "guid": "|w4lhA2z`Y",
            "definition": "suggest indirectly (ám chỉ)",
            "example": "What are you hinting at?",
            "collocations": "hint at sth",
        },
        ("rally", "noun", "C1"): {
            "guid": "\"b3wpN/#H?F\"",
            "definition": "support meeting (cuộc mít tinh)|road race (đua rally)",
            "example": "to attend/hold a rally|the Monte Carlo rally",
            "collocations": "hold/attend a rally|peace/protest rally|Monte Carlo rally",
        },
        ("rally", "verb", "C1"): {
            "guid": "288vg%/Y.O",
            "definition": "come together/support (tập hợp ủng hộ)|recover/increase again (phục hồi)",
            "example": (
                "The cabinet rallied behind the Prime Minister.|"
                "The company's shares had rallied (recover) slightly by the close of trading."
            ),
            "collocations": "rally behind/to sb|shares/market rally",
        },
        ("reverse", "adjective, noun, verb", "C1"): {
            "definition": (
                "opposite/backwards direction or order (ngược/đảo chiều)|"
                "make sth opposite or go backwards (đảo ngược/lùi lại)"
            ),
            "example": (
                "to travel in the reverse direction|"
                "The Court of Appeal reversed (revoke) the decision.<br><br>"
                "He reversed around the corner."
            ),
            "collocations": "reverse direction/order|reverse a decision/trend|reverse roles/order|reverse around/into sth",
        },
        ("trap", "noun, verb", "B2"): {
            "definition": (
                "device or trick for catching sb/sth (bẫy)|"
                "make sb/sth unable to escape or move (mắc kẹt/kẹp)"
            ),
            "example": (
                "a fox with its leg in a trap<br><br>"
                "She had set a trap for him and he had walked straight into it.|"
                "Help! I'm trapped!<br><br>I trapped my coat in the car door."
            ),
            "collocations": "set/lay trap|walk into a trap|be trapped in/inside sth|trap finger/coat",
        },
            ("twist", "noun, verb", "C1"): {
                "definition": (
                    "turn or bend sth (xoay hoặc vặn)|unexpected change (bước ngoặt)|"
                    "bend in path or body part (khúc quanh hoặc chỗ bong gân)"
            ),
            "example": (
                "She gave the lid another twist and it came off.|"
                "The story has taken another twist.|"
                "The car followed the twists and turns of the mountain road.<br><br>"
                "She fell and twisted her ankle."
            ),
            "collocations": "twist lid/knob/wire|twist in story/case|twists and turns|twist ankle/wrist",
        },
        ("grin", "noun, verb", "C1"): {
            "definition": "wide smile (nụ cười rộng/cười toe)|smile widely (cười toe/cười rộng)",
            "example": "She gave a broad grin.|They grinned with delight when they heard our news.",
        },
        ("prejudice", "noun", "C1"): {
            "definition": "unfair dislike or preference (định kiến/thiên kiến)",
        },
        ("philosophical", "adjective", "C1"): {
            "definition": "related to philosophy (thuộc triết học)|calm about difficulty (điềm nhiên/bình thản)",
        },
        ("saint", "noun", "C1"): {
            "definition": "holy or exceptionally good person (vị thánh/người đức hạnh)",
            "example": "St John<br><br>She's a saint to go on living with that man.",
        },
        ("extract", "noun", "B2"): {
            "ipa": "UK: /ˈekstrækt/ | US: /ˈekstrækt/",
        },
        ("domain", "noun", "C1"): {
            "definition": "field or area (lĩnh vực)",
            "example": "Financial matters are her domain.",
            "collocations": "domain of sth|outside domain of sth",
        },
        ("horizon", "noun", "C1"): {
            "definition": (
                "line where sky meets land/sea (đường chân trời)|"
                "limit of knowledge or experience (tầm nhìn/tầm hiểu biết)"
            ),
        },
        ("glory", "noun", "C1"): {
            "definition": "great praise and honour (vinh quang/sự tôn vinh)|great beauty (vẻ đẹp rực rỡ)",
            "example": (
                "Olympic glory in the 100 metres<br><br>"
                "‘Glory to God in the highest’|"
                "The city was spread out beneath us in all its glory."
            ),
        },
        ("dawn", "noun", "C1"): {
            "definition": "first light of day (bình minh)|beginning of sth (sự khởi đầu)",
        },
        ("derive from", "phrasal verb, verb", "B2"): {
            "guid": "dyWb^v=0``",
            "example": (
                "The word ‘politics’ is derived from a Greek word meaning ‘city’.|"
                "He derived great pleasure from painting."
            ),
        },
        ("variable", "adjective, noun", "C1"): {
            "definition": "able or likely to change (biến động/không cố định)|changing factor (biến số)",
            "example": (
                "variable (fluctuating) temperatures|With so many variables (constant), "
                "it is difficult to calculate the cost."
            ),
            "collocations": "variable temperatures/quality|independent/dependent variable",
        },
        ("implement", "verb", "B2"): {
            "definition": "put decision into action (triển khai/thực hiện)",
        },
        ("deprive of", "phrasal verb", "C1"): {
            "guid": "8VcO1&GtcB",
            "definition": (
                "prevent sb from having sth important "
                "(tước đoạt/làm cho ai đó thiếu thốn cái gì)"
            ),
        },
        ("adhere", "verb", "C1"): {
            "guid": "fP[g=pH}gT",
            "definition": "stick to sth (dính vào)",
            "example": "Once in the bloodstream, the bacteria adhere to the surface of the red cells.",
            "collocations": "adhere to a surface/skin|adhere firmly",
        },
        ("adhere to", "phrasal verb", "C1"): {
            "guid": "WPrL$@Wp65",
            "definition": "follow or obey rules/beliefs (tuân thủ)",
            "example": "Staff should adhere strictly to the safety guidelines.",
            "collocations": "adhere to rules/principles/guidelines|adhere strictly/closely to sth|adhere to a diet/method",
        },
        ("grip", "noun, verb", "C1"): {
            "guid": "L`OT<jad(1",
            "definition": (
                "hold or control (sự nắm chặt/kiểm soát)|understanding (sự nắm bắt)|"
                "surface hold or strong effect (độ bám/cuốn hút)"
            ),
            "example": (
                "Keep a tight grip (grasp) on the rope.<br><br>"
                "The home team took a firm grip on the game.|"
                "I couldn't get a grip (grasp) on what was going on.|"
                "These tyres give the bus better grip in slippery conditions.<br><br>"
                "The book grips you from start to finish."
            ),
            "collocations": "firm/tight grip|grip on power/game|get a grip on sth|good/better grip|grip reader/viewer",
        },
    }

    for identity, fields in expected.items():
        assert identity in cards, f"missing corrected card: {identity}"
        for field, value in fields.items():
            if field in SEMANTIC_FIELDS:
                # ADR 0011/0015 supersede the legacy fix-note semantic
                # literals; production semantics must match the promoted row.
                _assert_registry_semantics(cards[identity])
                continue
            assert cards[identity][field] == value, f"{identity} field {field}"

    assert ("counter (argue against)", "verb", "C1") not in cards
    assert ("derive", "phrasal verb, verb", "B2") not in cards
    assert ("deprive", "phrasal verb, verb", "C1") not in cards
    assert ("absence of", "noun", "C1") not in cards
    assert ("trail", "noun, verb", "C1") not in cards
    assert ("hint", "noun, verb", "C1") not in cards
    assert ("rally", "noun, verb", "C1") not in cards
    assert ("torture", "noun", "C1") not in cards
    assert ("torture", "verb", "C1") not in cards


def test_exact_headword_in_gloss_review_cards_are_rewritten():
    cards = _cards_by_identity()
    expected = {
        ("communist", "adjective", "C1"): (
            "related to communism (thuộc cộng sản)|run by a Marxist party (do Đảng Cộng sản lãnh đạo)"
        ),
        ("compound", "noun", "B2"): (
            "combined thing (vật ghép)|chemical substance (hợp chất)|word made of smaller words (từ ghép)"
        ),
        ("democratic", "adjective", "B2"): (
            "based on elected rule or equal participation (dân chủ)|related to the US party (thuộc Đảng Dân chủ Mỹ)"
        ),
        ("elbow", "noun", "B2"): "arm joint (khuỷu tay)|part of clothing at arm joint (phần khuỷu áo)",
        ("explosive", "adjective, noun", "C1"): (
            "able to burst or blasting substance (dễ nổ/chất nổ)|likely to cause anger/violence (dễ bùng nổ)"
        ),
        ("federal", "adjective", "B2"): "related to central government (thuộc liên bang)",
        ("fibre", "noun", "C1"): "dietary roughage (chất xơ)|thin thread in material/body (sợi)",
        ("gear", "noun", "C1"): "vehicle speed setting (số xe)|equipment or clothes (đồ/dụng cụ)",
        ("guilt", "noun", "C1"): (
            "feeling bad about doing sth wrong (cảm giác tội lỗi)|"
            "criminal responsibility (tội trạng)|blame or responsibility (trách nhiệm)"
        ),
        ("hook", "verb", "B2"): "fasten to sth (móc/gắn)",
        ("horn", "noun", "C1"): "animal hard growth (sừng)|vehicle warning device (còi)",
        ("kidney", "noun", "C1"): "blood-filtering organ or meat (thận)",
        ("liver", "noun", "C1"): "large body organ or meat (gan)",
        ("operator", "noun", "B2"): (
            "machine user (người vận hành)|business runner (nhà điều hành)|"
            "telephone service worker (tổng đài viên)"
        ),
        ("pump", "noun, verb", "C1"): (
            "machine for moving liquid/gas (máy bơm)|move liquid/gas mechanically (bơm)"
        ),
        ("racist", "adjective, noun", "B2"): (
            "racially unfair/prejudiced (phân biệt chủng tộc)|"
            "person with racial prejudice (người phân biệt chủng tộc)"
        ),
        ("receiver", "noun", "B2"): "phone handset (ống nghe)|signal pickup device (bộ thu tín hiệu)",
        ("separation", "noun", "C1"): "being apart (sự tách biệt/xa cách)|legal split (ly thân)",
        ("spare", "verb", "C1"): (
            "make available (dành ra)|save sb from sth (giúp tránh/tha)|"
            "make every effort (không tiếc công sức)"
        ),
        ("standing", "adjective", "C1"): "from upright position (ở tư thế đứng)|permanent (thường trực/lâu dài)",
        ("stem", "noun, verb", "C1"): "plant stalk (thân cây)|stop flow/growth (ngăn chặn)",
        ("total", "verb", "C1"): "reach an amount (lên tới)|add up (cộng lại)",
        ("whip", "verb", "C1"): (
            "hit with lash (quất roi)|move/pull suddenly (vụt/kéo phắt)|beat food fast (đánh bông)"
        ),
    }

    for identity in expected:
        assert identity in cards
        _assert_registry_semantics(cards[identity])


def test_exact_headword_leftover_cards_are_rewritten():
    cards = _cards_by_identity()
    expected = {
        ("bat", "verb", "C1"): "hit ball in a sport (\u0111\u00e1nh b\u00f3ng)",
        ("jet", "noun", "B2"): "fast aircraft (m\u00e1y bay ph\u1ea3n l\u1ef1c)",
        ("top", "verb", "C1"): (
            "exceed an amount (v\u01b0\u1ee3t qu\u00e1)|be first (\u0111\u1ee9ng \u0111\u1ea7u)|"
            "cover with sth above (ph\u1ee7/\u0111\u1eb7t l\u00ean tr\u00ean)"
        ),
    }

    for identity in expected:
        assert identity in cards
        _assert_registry_semantics(cards[identity])


def test_approved_word_family_loop_review_cards_are_rewritten():
    cards = _cards_by_identity()
    expected = {
        ("voting", "noun", "B2"): "choosing in an election (việc bỏ phiếu)",
        ("villager", "noun", "C1"): "person from a small community (dân làng)",
        ("validate", "verb", "C2"): "make legally accepted (công nhận hợp pháp)",
    }

    for identity in expected:
        assert identity in cards
        _assert_registry_semantics(cards[identity])
        definition = _without_register_tags(cards[identity]["definition"])
        assert "word_family_loop" not in detect_loops(identity[0], definition)


def test_antonym_loop_decision_ledger_is_batched_and_complete():
    decisions = _antonym_loop_decisions()
    guards = [(r["word"], r["pos"], r["cefr"]) for r in decisions]
    batches = Counter(r["batch"] for r in decisions)
    decision_counts = Counter(r["decision"] for r in decisions)

    assert len(decisions) == 119
    assert len(guards) == len(set(guards))
    assert decision_counts == {"keep_basic_negation": 104, "repair_gloss": 15}
    assert set(batches) == {f"batch_{i:02d}" for i in range(1, 13)} | {"sense_grouping_review"}
    assert all(count <= 10 for count in batches.values())
    assert batches["batch_12"] == 8
    assert batches["sense_grouping_review"] == 1

    for row in decisions:
        if row["decision"] == "repair_gloss":
            assert row["new_definition"]
        else:
            assert row["decision"] == "keep_basic_negation"
            assert not row["new_definition"]


def test_antonym_loop_repairs_are_applied_to_generated_cards():
    cards = _cards_by_identity()
    expected = {
        ("allegation", "noun", "C1"): "accusation without proof (cáo buộc chưa chứng minh)",
        ("assumption", "noun", "B2"): "belief without proof (giả định)",
        ("guerrilla", "noun", "C1"): "fighter outside regular army (du kích)",
        ("hypothesis", "noun", "B2"): "idea or explanation to test (giả thuyết)",
        ("imbalance", "noun", "UNCLASSIFIED"): "lack of balance causing problems (sự mất cân bằng)",
        ("inability", "noun", "C1"): "lack of ability (không có khả năng)",
        ("interference", "noun", "C1"): "involvement in others' affairs (sự can thiệp)",
        ("metaphor", "noun", "B2"): "comparison used as image (ẩn dụ)",
        ("outsider", "noun", "C1"): "person not in a group (người ngoài)",
        ("partial", "adjective", "C1"): "only part of sth (một phần/không hoàn chỉnh)",
        ("partially", "adverb", "C1"): "only partly (một phần)",
        ("reluctance", "noun", "UNCLASSIFIED"): "feeling of not wanting to do sth (sự miễn cưỡng/ngần ngại)",
        ("short-sighted", "adjective", "C2"): (
            "able to see only near things (cận thị)|thinking only about now (thiển cận)"
        ),
        ("unfounded", "adjective", "UNCLASSIFIED"): "lacking facts or evidence (vô căn cứ)",
        ("uninhabitable", "adjective", "UNCLASSIFIED"): "too dangerous to live in (không thể ở được)",
    }

    for identity in expected:
        word = identity[0]
        assert identity in cards
        _assert_registry_semantics(cards[identity])
        definition = _without_register_tags(cards[identity]["definition"])
        assert "antonym_loop" not in detect_loops(word, definition)


def test_five_legacy_review_signals_use_registry_content_after_cutover():
    cards = _cards_by_identity()
    decisions = {
        (row["word"], row["pos"], row["cefr"]): row
        for row in _antonym_loop_decisions()
    }
    expected = {
        ("exploitation", "noun", "C1"),
        ("fake", "adjective", "B2"),
        ("intolerance", "noun", "C2"),
        ("spam", "noun", "C1"),
        ("violation", "noun", "C1"),
    }

    for identity in expected:
        decision = decisions[identity]
        assert decision["decision"] == "keep_basic_negation"
        assert decision["new_definition"] == ""
        # The decision ledger remains historical evidence, but ADR 0011 now
        # owns the generated semantic payload.
        _assert_registry_semantics(cards[identity])


# Superseded by the registry-owned variant test appended below; retained as a
# historical snapshot while the legacy semantic literals are phased out.
def _legacy_test_proposition_semantic_variant_split_is_applied():
    rows = [
        json.loads(line)
        for line in PATHS.anki_notes_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [
        row
        for row in rows
        if row["word"] == "proposition" and row["cefr"] == "C1"
    ]
    by_guid = {row["guid"]: row for row in rows}

    assert set(by_guid) == {"e/a@jzBur]", "pR0pLawF1%"}

    primary = by_guid["e/a@jzBur]"]
    assert primary["deck"] == "English Academic Vocabulary::Oxford::Oxford 5000"
    assert primary["pos"] == "noun"
    assert primary["definition"] == "suggested idea/plan (đề xuất)|thing to deal with (vấn đề)"
    assert primary["example"] == (
        "I'd like to put a business proposition to you.|"
        "Getting a work permit in the UK is not always a simple proposition (matter)."
    )

    secondary = by_guid["pR0pLawF1%"]
    assert secondary["deck"] == "English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses"
    assert secondary["pos"] == "noun"
    assert secondary["definition"] == (
        "[politics]vote law proposal (dự luật trưng cầu)|"
        "[formal]opinion statement (mệnh đề/luận điểm)"
    )
    assert secondary["example"] == (
        "How did you vote on Proposition 8?|"
        "Her assessment is based on the proposition that power corrupts."
    )
    assert "SecondarySense" in secondary["tags"].split()


def test_awl_cefr_rescue_cards_are_applied():
    cards = _cards_by_identity()
    expected = {
        ("immigrate", "verb", "C1"): (
            "imm1GrAt3C1",
            "come to live permanently in another country (nhập cư)",
        ),
        ("offset", "verb", "C2"): (
            "offs3tC2vB",
            "balance or reduce an opposing cost/effect (bù đắp/cân bằng)",
        ),
        ("percent", "adjective, adverb", "B1"): (
            "p3rc3ntB1x",
            "amount out of every 100 (phần trăm)",
        ),
        ("restrain", "verb", "C1"): (
            "i/Mobs,`g1",
            "control or limit sb/sth (kiềm chế, khống chế hoặc hạn chế)",
        ),
        ("tense", "adjective", "C1"): (
            "tens3AdjC1",
            "nervous, worried, and unable to relax (căng thẳng)",
        ),
    }

    assert ("restrain", "verb", "UNCLASSIFIED") not in cards
    for identity, (guid, _legacy_definition) in expected.items():
        row = cards[identity]
        assert row["guid"] == guid
        _assert_registry_semantics(row)
        assert row["deck"] == "English Academic Vocabulary::AWL 50 Academic Words"
        assert "AWL_Coxhead" in row["tags"].split()


# Superseded by the registry-owned equate test appended below; retain only the
# historical fixture for traceability.
def _legacy_test_equate_uses_the_learner_gloss_for_equating_two_things():
    card = _cards_by_identity()[("equate", "verb", "C2")]

    assert card["guid"] == "Qmol/ya1&P"
    assert card["definition"] == (
        "think two things are the same or equally important (đánh đồng)"
    )
    assert card["collocations"] == (
        "equate A with B|equate success with money|wrongly/often equate sth with sth"
    )


def test_forth_keeps_only_the_two_priority_idioms():
    card = _cards_by_identity()[("forth", "adverb", "C1")]

    assert card["guid"] == "iYka_pH9Jw"
    assert card["idioms"].split("$$") == [
        "and so forth :: used at the end of a list to show that it continues in the same way :: "
        "We discussed everything—when to go, what to see and so on.",
        "back and forth :: repeatedly between two places :: "
        "ferries sailing back and forth between the islands",
    ]
    assert "from that day/time forth" not in card["idioms"]
    assert "idioms" in card["tags"].split()


# Superseded by the registry-owned alignment test appended below; retained as
# a historical fixture while the legacy snapshot is phased out.
def _legacy_test_concede_groups_the_two_admit_senses():
    card = _cards_by_identity()[("concede", "verb", "C1")]

    assert card["guid"] == "C!}?S?hfm_"
    assert card["definition"] == (
        "admit sth / defeat (thừa nhận / chấp nhận thua)|"
        "give up or allow sth (nhượng bộ/cho phép)"
    )
    assert card["example"] == (
        "‘Not bad,’ she conceded grudgingly.<br><br>He refused to concede defeat.|"
        "The government had been forced to concede the point."
    )
    assert card["example"].count("|") == 1


def _legacy_test_current_antonym_loop_candidates_are_reviewed_keeps():
    cards = _cards_by_identity()
    decisions = {
        (r["word"], r["pos"], r["cefr"]): r
        for r in _antonym_loop_decisions()
    }

    current_antonym_loop_cards = [
        (identity, row)
        for identity, row in cards.items()
        if "antonym_loop" in detect_loops(row["word"], row["definition"])
    ]

    assert len(current_antonym_loop_cards) == 95
    for identity, row in current_antonym_loop_cards:
        decision = decisions.get(identity)
        assert decision is not None
        assert decision["decision"] == "keep_basic_negation"
        assert _without_register_tags(row["definition"]) == _without_register_tags(decision["old_definition"])


def test_same_sense_examples_use_double_breaks_only():
    cards = _cards_by_identity()
    target_identities = {
        ("unveil", "verb", "C1"),
        ("outrage", "noun, verb", "C1"),
        ("sensation", "noun", "C1"),
        ("torture", "noun, verb", "C1"),
        ("bow", "noun, verb", "C1"),
        ("reverse", "adjective, noun, verb", "C1"),
        ("trap", "noun, verb", "B2"),
        ("twist", "noun, verb", "C1"),
        ("grip", "noun, verb", "C1"),
        ("saint", "noun", "C1"),
        ("glory", "noun", "C1"),
    }

    for identity in target_identities:
        example = cards[identity]["example"]
        assert "<br><br>" in example
        assert example.replace("<br><br>", "").find("<br>") == -1


def test_concede_uses_registry_sense_alignment():
    card = _cards_by_identity()[("concede", "verb", "C1")]
    registry_row = _semantic_registry_by_guid()[card["guid"]]

    assert card["guid"] == "C!}?S?hfm_"
    _assert_registry_semantics(card, registry_row)
    assert len(registry_row["senses"]) == 3
    assert len(card["definition"].split("|")) == len(registry_row["senses"])
    assert len(card["example"].split("|")) == len(registry_row["senses"])


def test_current_antonym_loop_candidates_are_registry_owned():
    cards = _cards_by_identity()
    current_antonym_loop_cards = [
        row
        for row in cards.values()
        if "antonym_loop" in detect_loops(row["word"], row["definition"])
    ]

    # ADR 0011 supersedes the fixed legacy candidate count and old gloss
    # snapshots. Every currently detected candidate must use promoted content.
    assert current_antonym_loop_cards
    for row in current_antonym_loop_cards:
        _assert_registry_semantics(row)


def test_proposition_semantic_variant_split_uses_registry_payload():
    rows = [
        row
        for row in _load_jsonl(PATHS.anki_notes_jsonl)
        if row["word"] == "proposition" and row["cefr"] == "C1"
    ]
    by_guid = {row["guid"]: row for row in rows}

    assert set(by_guid) == {"e/a@jzBur]", "pR0pLawF1%"}
    primary = by_guid["e/a@jzBur]"]
    assert primary["deck"] == "English Academic Vocabulary::Oxford::Oxford 5000"
    assert primary["pos"] == "noun"
    _assert_registry_semantics(primary)

    secondary = by_guid["pR0pLawF1%"]
    assert secondary["deck"] == "English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses"
    assert secondary["pos"] == "noun"
    _assert_registry_semantics(secondary)
    assert "SecondarySense" in secondary["tags"].split()


def test_stack_c2_verb_keeps_only_verb_owned_idiom():
    card = _cards_by_guid()["DAL,%7`QPB"]

    assert card["word"] == "stack"
    assert card["pos"] == "verb"
    assert card["idioms"].startswith("stack it :: ")
    assert "blow your top" not in card["idioms"]


def test_equate_uses_registry_payload_and_learner_collocations():
    card = _cards_by_identity()[("equate", "verb", "C2")]

    assert card["guid"] == "Qmol/ya1&P"
    _assert_registry_semantics(card)
    assert card["collocations"] == (
        "equate A with B|equate success with money|wrongly/often equate sth with sth"
    )
