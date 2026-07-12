from __future__ import annotations
import pytest
from pathlib import Path
from src.deck_builder.build_contracts import BuiltCard, BuildNotesPaths
from src.deck_builder.build_issues import BuildValidationError
from src.config import ProjectPaths
from src.deck_builder.build_notes import build_notes
from src.deck_builder.synonym_annotator import (
    clean_for_matching,
    strip_synonym_annotations,
    is_already_annotated,
    matches_lemma,
    annotate_chunk_auto,
    annotate_card_examples,
    load_synonym_overrides,
)


def _card(
    word: str,
    pos: str,
    cefr: str,
    example: str,
    guid: str = "12345",
    deck: str = "Oxford",
    notetype: str = "EAVM",
) -> BuiltCard:
    """Helper: build a BuiltCard fixture with the new 19-col signature."""
    return BuiltCard(
        guid=guid, notetype=notetype, deck=deck, word=word, pos=pos, ipa="...",
        definition="...", example=example,
        collocations="...", wordfamily="...", uk_audio="...", us_audio="...",
        source1="Oxford", source2="Oxford", cefr=cefr, idioms="...", tags="...",
        synonyms="", antonyms="",
    )


def test_clean_for_matching():
    # Parentheses are preserved
    assert clean_for_matching("Fish are abundant (plentiful) in the lake.") == "fish are abundant (plentiful) in the lake."
    assert clean_for_matching("Some ‘quote’ and “another”") == "some 'quote' and \"another\""
    assert clean_for_matching("Some text (= if applicable)") == "some text (= if applicable)"


def test_strip_synonym_annotations():
    syns = ["plentiful", "obvious"]
    assert strip_synonym_annotations("Fish are abundant (plentiful) in the lake.", syns) == "Fish are abundant in the lake."
    assert strip_synonym_annotations("apparent (obvious) lack", syns) == "apparent lack"
    assert strip_synonym_annotations("apparent (something else) lack", syns) == "apparent (something else) lack"


def test_is_already_annotated():
    syns = ["plentiful", "obvious"]
    assert is_already_annotated("abundant (plentiful)", syns) is True
    assert is_already_annotated("apparent (clear, obvious)", syns) is True
    assert is_already_annotated("no annotation", syns) is False


def test_matches_lemma():
    assert matches_lemma("accumulated", "accumulate") is True
    assert matches_lemma("accumulating", "accumulate") is True
    assert matches_lemma("debts", "debt") is True
    assert matches_lemma("strange", "alien") is False


def test_annotate_chunk_auto_basic():
    assert annotate_chunk_auto("Fish are abundant in the lake.", "abundant", ["plentiful"]) == "Fish are abundant (plentiful) in the lake."
    assert annotate_chunk_auto("Debts accumulated.", "accumulate", ["amass"]) == "Debts accumulated (amass)."
    assert annotate_chunk_auto("Nothing matches.", "accumulate", ["amass"]) is None


def test_annotate_chunk_auto_particles_and_phrasals():
    # trigger off (set off)
    assert annotate_chunk_auto("Nuts can trigger off a violent allergic reaction.", "trigger", ["set off"]) == "Nuts can trigger off (set off) a violent allergic reaction."
    # teem down (pour) - note that pour has no particle down, so it does not extend!
    assert annotate_chunk_auto("The rain was teeming down.", "teem", ["pour"]) == "The rain was teeming (pour) down."
    # delve in (dig) - dig has no particle in, so it does not extend!
    assert annotate_chunk_auto("She delved in her handbag.", "delve", ["dig"]) == "She delved (dig) in her handbag."


def test_annotate_chunk_first_occurrence_only():
    # Should only insert after the first occurrence of the target word
    assert annotate_chunk_auto("He wanted to test the test.", "test", ["evaluate"]) == "He wanted to test (evaluate) the test."


def test_annotate_chunk_multiple_synonyms():
    assert annotate_chunk_auto("A crucial decision.", "crucial", ["critical", "essential"]) == "A crucial (critical, essential) decision."


def test_annotate_chunk_idempotency():
    syns = ["plentiful"]
    orig = "Fish are abundant (plentiful) in the lake."
    assert annotate_chunk_auto(orig, "abundant", syns) == orig


def test_annotate_card_examples_success():
    """Both synonym cells populated; metadata pipe-aligned with chunks."""
    card = _card(
        word="abundant", pos="adjective", cefr="B2",
        example="Fish are abundant in the lake.|an abundant supply",
    )
    specs = [
        {"text": "Fish are abundant in the lake.", "synonyms": ["plentiful"], "antonyms": []},
        {"text": "an abundant supply", "synonyms": ["rich"], "antonyms": []},
    ]
    annotated, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {}, {})
    assert not errors
    assert annotated == "Fish are abundant (plentiful) in the lake.|an abundant (rich) supply"
    assert syn_meta == "plentiful|rich"
    assert ant_meta == "|"


def test_annotate_card_examples_supports_double_break_within_one_sense():
    card = _card(
        word="outrage", pos="noun", cefr="C1",
        example=(
            "The remarks caused public outrage.<br><br>"
            "No one claimed responsibility for the terrorist outrage."
        ),
    )
    specs = [
        {"text": "The remarks caused public outrage.", "synonyms": [], "antonyms": []},
        {
            "text": "No one claimed responsibility for the terrorist outrage.",
            "synonyms": ["atrocity"],
            "antonyms": [],
        },
    ]

    annotated, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {}, {})

    assert not errors
    assert annotated == (
        "The remarks caused public outrage.<br><br>"
        "No one claimed responsibility for the terrorist outrage (atrocity)."
    )
    assert syn_meta == "atrocity"
    assert ant_meta == ""


def test_double_break_group_consumes_skip_override_for_unmapped_example():
    card = _card(
        guid='"j>(#&<;AW0"',
        word="sterile",
        pos="adjective",
        cefr="UNCLASSIFIED",
        example="sterile soil<br><br>a sterile debate",
    )
    specs = [
        {
            "text": "a sterile debate",
            "synonyms": ["fruitless"],
            "antonyms": [],
        }
    ]
    overrides = {
        card.guid: [{
            "guid": card.guid,
            "word": "sterile",
            "pos": "adjective",
            "cefr": "UNCLASSIFIED",
            "original_example": "sterile soil",
            "action": "skip",
            "reason": "custom learner example",
        }]
    }

    annotated, syn_meta, ant_meta, errors = annotate_card_examples(
        card, specs, overrides, {}
    )

    assert not errors
    assert annotated == "sterile soil<br><br>a sterile (fruitless) debate"
    assert syn_meta == "fruitless"
    assert ant_meta == ""


def test_annotate_card_examples_unmapped_without_override():
    card = _card(
        word="delve", pos="verb", cefr="UNCLASSIFIED",
        example="She delved in her handbag.|We need to delve deeper into the issue.",
    )
    specs = [
        {"text": "She delved in her handbag.", "synonyms": ["dig"], "antonyms": []},
    ]
    _, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {}, {})
    assert len(errors) == 1
    assert "Unresolved alignment" in errors[0]


def test_annotate_card_examples_skip_override():
    card = _card(
        word="delve", pos="verb", cefr="UNCLASSIFIED",
        example="She delved in her handbag.|We need to delve deeper into the issue.",
    )
    specs = [
        {"text": "She delved in her handbag.", "synonyms": ["dig"], "antonyms": []},
    ]
    overrides = {
        "12345": [
            {
                "guid": "12345",
                "word": "delve",
                "pos": "verb",
                "cefr": "UNCLASSIFIED",
                "original_example": "We need to delve deeper into the issue.",
                "action": "skip",
                "reason": "not in Oxford",
            }
        ]
    }
    annotated, _, _, errors = annotate_card_examples(card, specs, overrides, {})
    assert not errors
    assert annotated == "She delved (dig) in her handbag.|We need to delve deeper into the issue."


def test_annotate_card_examples_annotate_override():
    card = _card(
        word="cope", pos="verb", cefr="B2",
        example="I got to the stage where I wasn't coping any more.",
    )
    specs = [
        {"text": "I got to the stage where I wasn't coping any more.", "synonyms": ["manage"], "antonyms": []},
    ]
    overrides = {
        "12345": [
            {
                "guid": "12345",
                "word": "cope",
                "pos": "verb",
                "cefr": "B2",
                "original_example": "I got to the stage where I wasn't coping any more.",
                "action": "annotate",
                "source_example": "I got to the stage where I wasn't coping any more.",
                "annotated_example": "I got to the stage where I wasn't coping (manage) any more.",
            }
        ]
    }
    annotated, syn_meta, _, errors = annotate_card_examples(card, specs, overrides, {})
    assert not errors
    assert annotated == "I got to the stage where I wasn't coping (manage) any more."
    assert syn_meta == "manage"


def test_override_validations(tmp_path):
    # Test missing override file fails
    missing_file = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError):
        load_synonym_overrides(missing_file)

    # Test invalid jsonl fails
    bad_file = tmp_path / "bad.jsonl"
    bad_file.write_text("invalid json\n")
    with pytest.raises(ValueError):
        load_synonym_overrides(bad_file)

    # Test duplicate override fails
    dup_file = tmp_path / "dup.jsonl"
    dup_file.write_text(
        '{"guid": "123", "word": "w", "pos": "p", "cefr": "c", "original_example": "ex", "action": "skip", "reason": "r"}\n'
        '{"guid": "123", "word": "w", "pos": "p", "cefr": "c", "original_example": "ex", "action": "skip", "reason": "r"}\n'
    )
    with pytest.raises(ValueError):
        load_synonym_overrides(dup_file)


def test_override_identity_and_base_text_errors():
    card = _card(
        word="cope", pos="verb", cefr="B2",
        example="I wasn't coping any more.",
    )
    specs = [{"text": "I wasn't coping any more.", "synonyms": ["manage"], "antonyms": []}]

    # Identity mismatch
    overrides_identity = {
        "12345": [
            {
                "guid": "12345",
                "word": "wrong-word",  # mismatch
                "pos": "verb",
                "cefr": "B2",
                "original_example": "I wasn't coping any more.",
                "action": "skip",
                "reason": "testing",
            }
        ]
    }
    _, _, _, errors = annotate_card_examples(card, specs, overrides_identity, {})
    assert len(errors) == 2
    assert "Card identity mismatch" in errors[0]
    assert "Skip action not allowed for exact sense with synonyms" in errors[1]

    # Base text modified in override
    overrides_modified_base = {
        "12345": [
            {
                "guid": "12345",
                "word": "cope",
                "pos": "verb",
                "cefr": "B2",
                "original_example": "I wasn't coping any more.",
                "action": "annotate",
                "source_example": "I wasn't coping any more.",
                "annotated_example": "I wasn't coping (manage) any more and some extra words.",  # modified base text!
            }
        ]
    }
    _, _, _, errors = annotate_card_examples(card, specs, overrides_modified_base, {})
    assert len(errors) == 1
    assert "Base text modified" in errors[0]


def test_skip_abundant_fails():
    card = _card(
        word="abundant", pos="adjective", cefr="B2",
        example="Fish are abundant in the lake.",
    )
    specs = [
        {"text": "Fish are abundant in the lake.", "synonyms": ["plentiful"], "antonyms": []}
    ]
    overrides = {
        "12345": [
            {
                "guid": "12345",
                "word": "abundant",
                "pos": "adjective",
                "cefr": "B2",
                "original_example": "Fish are abundant in the lake.",
                "action": "skip",
                "reason": "Skip exact sense with synonyms",
            }
        ]
    }
    _, _, _, errors = annotate_card_examples(card, specs, overrides, {})
    assert len(errors) == 1
    assert "Skip action not allowed for exact sense with synonyms" in errors[0]


def test_annotate_missing_or_invalid_source_example():
    card = _card(
        word="cope", pos="verb", cefr="B2",
        example="I wasn't coping any more.",
    )
    specs = [
        {"text": "I wasn't coping any more.", "synonyms": ["manage"], "antonyms": []}
    ]

    # Missing source_example
    overrides_missing = {
        "12345": [
            {
                "guid": "12345",
                "word": "cope",
                "pos": "verb",
                "cefr": "B2",
                "original_example": "I wasn't coping any more.",
                "action": "annotate",
                # missing source_example
                "annotated_example": "I wasn't coping (manage) any more.",
            }
        ]
    }
    _, _, _, errors = annotate_card_examples(card, specs, overrides_missing, {})
    assert len(errors) == 1
    assert "Missing source_example in annotate synonym override" in errors[0]

    # Invalid source_example (does not match spec)
    overrides_invalid = {
        "12345": [
            {
                "guid": "12345",
                "word": "cope",
                "pos": "verb",
                "cefr": "B2",
                "original_example": "I wasn't coping any more.",
                "action": "annotate",
                "source_example": "completely different example text",
                "annotated_example": "I wasn't coping (manage) any more.",
            }
        ]
    }
    _, _, _, errors = annotate_card_examples(card, specs, overrides_invalid, {})
    assert len(errors) == 1
    assert "does not match any Oxford spec" in errors[0]
    assert "synonym" in errors[0]


def test_two_senses_same_synonym_no_ambiguity():
    card = _card(
        word="test", pos="verb", cefr="B2",
        example="I need to test this.",
    )
    specs = [
        {"text": "Let us test them.", "synonyms": ["evaluate"], "antonyms": []},
        {"text": "They test the software.", "synonyms": ["evaluate"], "antonyms": []},
    ]
    # The chunk "I need to test this" is unmapped. It should not guess or fallback to any evaluate spec.
    _, _, _, errors = annotate_card_examples(card, specs, {}, {})
    assert len(errors) == 1
    assert "Unresolved alignment" in errors[0]


# -----------------------------------------------------------------------------
# New tests for the lexical-relations refactor (synonym + antonym annotations).
# -----------------------------------------------------------------------------

def test_annotate_both_relations_order_synonym_first():
    """When both synonym and antonym are present, synonym appears first."""
    card = _card(
        word="cheap", pos="adjective", cefr="B2",
        example="a cheap car",
    )
    specs = [
        {
            "text": "a cheap car",
            "synonyms": ["inexpensive"],
            "antonyms": ["expensive"],
        },
    ]
    annotated, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {}, {})
    assert not errors
    # Synonym inserted right after the headword, antonym appended next.
    assert annotated == "a cheap (inexpensive) (expensive) car"
    assert syn_meta == "inexpensive"
    assert ant_meta == "expensive"


def test_annotate_antonym_only():
    """Antonym-only annotations (no synonym) work end-to-end."""
    card = _card(
        word="transparent", pos="adjective", cefr="C1",
        example="transparent glass is fragile|transparent glass can be scratched",
    )
    specs = [
        {
            "text": "transparent glass is fragile",
            "synonyms": [],
            "antonyms": ["opaque"],
        },
        {
            "text": "transparent glass can be scratched",
            "synonyms": [],
            "antonyms": [],
        },
    ]
    annotated, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {}, {})
    assert not errors
    # First chunk gets (opaque) appended to the headword; second chunk has no relation.
    assert annotated == "transparent (opaque) glass is fragile|transparent glass can be scratched"
    assert ant_meta == "opaque|"
    assert syn_meta == "|"


def test_annotate_antonym_skip_override_consumes_chunk():
    """Antonym skip override suppresses the auto-annotation for the matched chunk."""
    card = _card(
        word="unfold", pos="verb", cefr="B2",
        example="to unfold a map|The audience watched as the story unfolded before their eyes.",
    )
    specs = [
        {
            "text": "to unfold a map",
            "synonyms": [],
            "antonyms": ["fold"],
        },
    ]
    overrides = {
        "12345": [
            {
                "guid": "12345",
                "word": "unfold",
                "pos": "verb",
                "cefr": "B2",
                "original_example": "The audience watched as the story unfolded before their eyes.",
                "action": "skip",
                "reason": "story unfolded belongs to the C1 sense, not unfold<->fold",
            }
        ]
    }
    annotated, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {}, overrides)
    assert not errors
    # First chunk auto-annotates with (fold); second chunk is skipped (no annotation).
    assert annotated == "to unfold (fold) a map|The audience watched as the story unfolded before their eyes."
    assert ant_meta == "fold|"


def test_get_relation_specs_unions_relations_for_shared_example():
    """When multiple source senses share the same example text, their
    synonym/antonym relations must be unioned (first-appearance order)
    rather than last-wins. This protects the contract "the annotator
    applies exact Oxford relations" — losing relations to last-wins would
    silently strip metadata.
    """
    from src.deck_builder.synonym_annotator import get_relation_specs_for_card
    from src.deck_builder.simplify_senses import MergedSense

    ms1 = MergedSense(
        pos="noun", cefr="B2", text="def A", register_tags=[], topics=[],
        collocations={}, examples=[
            {"text": "shared example", "synonyms": ["rich"], "antonyms": []},
        ],
        countability=None, domain=None, is_phrase=False, is_idiom=False,
        source_pdd_idx=[0], source_def_idx=[0], cefr_originals=[None],
        cefr_sources=["sense_badge"], relation_specs=[
            {"text": "shared example", "synonyms": ["rich"], "antonyms": []},
        ],
    )
    ms2 = MergedSense(
        pos="noun", cefr="B2", text="def B", register_tags=[], topics=[],
        collocations={}, examples=[
            {"text": "shared example", "synonyms": ["plentiful"], "antonyms": ["scarce"]},
        ],
        countability=None, domain=None, is_phrase=False, is_idiom=False,
        source_pdd_idx=[0], source_def_idx=[1], cefr_originals=[None],
        cefr_sources=["sense_badge"], relation_specs=[
            {"text": "shared example", "synonyms": ["plentiful"], "antonyms": ["scarce"]},
        ],
    )
    senses_index = {("school", "noun", "B2"): [ms1, ms2]}
    card = _card(word="school", pos="noun", cefr="B2", example="shared example")
    specs = get_relation_specs_for_card(card, senses_index)
    # Both senses' relations must appear — first-appearance order preserved.
    assert len(specs) == 1
    assert specs[0]["text"] == "shared example"
    assert specs[0]["synonyms"] == ["rich", "plentiful"]
    assert specs[0]["antonyms"] == ["scarce"]


def test_annotate_applicable_appends_after_existing_oxford_parenthetical():
    """Regression for `applicable (relevant) (= if you have any)`: the synonym
    annotation `(relevant)` must be appended AFTER the existing Oxford
    parenthetical chain `(= if you have any)`, never inserted between the
    headword and the original Oxford parenthetical.

    This is the core invariant that protects the source text — the
    annotator must walk past immediately-following parentheticals before
    inserting its own relation.
    """
    card = _card(
        word="applicable", pos="adjective", cefr="C1",
        example="Give details of children where applicable (= if you have any).",
    )
    specs = [
        {
            "text": "Give details of children where applicable (= if you have any).",
            "synonyms": ["relevant"],
            "antonyms": [],
        },
    ]
    annotated, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {}, {})
    assert not errors
    # The (relevant) goes AFTER the existing (= if you have any), not before.
    assert annotated == "Give details of children where applicable (= if you have any) (relevant)."
    assert syn_meta == "relevant"
    assert ant_meta == ""


def test_unknown_guid_fails_on_single_card_build(tmp_path):
    oxford_jsonl = tmp_path / "oxford.jsonl"
    oxford_jsonl.write_text("", encoding="utf-8")
    registry = tmp_path / "card_registry.jsonl"
    registry.write_text(
        '{"word":"conquer","cefr":"C1","list":"NO_LIST","variant":"","pos":"verb","guid":"guid_conq","status":"active","deck_override":"Deck Oxford"}\n',
        encoding="utf-8",
    )
    manual = tmp_path / "manual_cards.jsonl"
    manual.write_text(
        '{"word":"conquer","cefr":"C1","list":"NO_LIST","variant":"","definition":"defn","example":"ex","collocations":"","wordfamily":"","ipa":"/ipa/","uk_audio":"","us_audio":"","source1":"Oxford","source2":"Oxford","idioms":"","provenance":{"source":"build_contract_source_gap","ledger_pos":"verb"},"tags":"Source::Oxford CEFR::C1 CEFR::oxford"}\n',
        encoding="utf-8",
    )

    # Overrides has a DIFFERENT guid (unknown GUID)
    overrides_file = tmp_path / "overrides.jsonl"
    overrides_file.write_text(
        '{"guid": "different_guid", "word": "abundant", "pos": "adjective", "cefr": "B2", "original_example": "ex", "action": "skip", "reason": "testing"}\n',
        encoding="utf-8",
    )

    paths = BuildNotesPaths(
        oxford_jsonl_path=oxford_jsonl,
        deck_audit_jsonl_path=tmp_path / "audit.jsonl",
        gamma_verdicts_path=tmp_path / "gamma.json",
        oxford_3000_md=tmp_path / "oxford_3000.md",
        oxford_5000_md=tmp_path / "oxford_5000.md",
        awl_md=tmp_path / "awl.md",
        audio_dir=tmp_path / "audio",
        card_registry_path=registry,
        manual_cards_path=manual,
        synonym_example_overrides_path=overrides_file,
        antonym_example_overrides_path=tmp_path / "antonym_overrides.jsonl",
    )

    # Write empty files for dependencies
    paths.deck_audit_jsonl_path.write_text("", encoding="utf-8")
    paths.gamma_verdicts_path.write_text('{"verdicts": []}\n', encoding="utf-8")
    paths.oxford_3000_md.write_text("", encoding="utf-8")
    paths.oxford_5000_md.write_text("", encoding="utf-8")
    paths.awl_md.write_text("", encoding="utf-8")
    paths.audio_dir.mkdir(exist_ok=True)
    # Antonym overrides file is empty (no entries); should be tolerated.
    paths.antonym_example_overrides_path.write_text("", encoding="utf-8")

    # Should fail due to unknown GUID in overrides
    with pytest.raises(BuildValidationError) as exc:
        build_notes(paths)
    assert "Unknown card GUIDs defined in synonym overrides" in str(exc.value)


def test_production_overrides_loaded_and_used_once():
    # This integration test verifies that the production overrides files are
    # 100% correct: all synonym AND antonym overrides are matched and used
    # exactly once with 0 errors, AND every built card has the new
    # synonyms/antonyms fields populated.
    proj = ProjectPaths()

    # Load cards and run the real builder to verify
    paths = BuildNotesPaths(
        oxford_jsonl_path=proj.oxford_jsonl,
        deck_audit_jsonl_path=proj.deck_audit_jsonl,
        gamma_verdicts_path=proj.gamma_verdicts,
        oxford_3000_md=proj.oxford_3000_md,
        oxford_5000_md=proj.oxford_5000_md,
        awl_md=proj.awl_md,
        audio_dir=proj.audio_dir,
        card_registry_path=proj.card_registry,
        manual_cards_path=proj.manual_cards,
        synonym_example_overrides_path=proj.synonym_example_overrides,
        antonym_example_overrides_path=proj.antonym_example_overrides,
        review_overrides_path=proj.non_oxford_non_c2_overrides,
        sense_label_overrides_path=proj.sense_label_overrides,
    )

    res = build_notes(paths)
    assert res.built_cards_count == 2461

    # Every built card has synonyms and antonyms fields (possibly empty strings).
    for c in res.built_cards:
        assert hasattr(c, "synonyms")
        assert hasattr(c, "antonyms")
        assert isinstance(c.synonyms, str)
        assert isinstance(c.antonyms, str)
        # Pipe-alignment invariant: #cells must match #example chunks (or be empty).
        ex_chunks = [chunk for chunk in c.example.split("|") if chunk.strip()]
        for meta in (c.synonyms, c.antonyms):
            if not meta:
                continue
            n_cells = len(meta.split("|"))
            assert n_cells == len(ex_chunks), (
                f"Card {c.word} ({c.guid}): {n_cells} relation cells vs {len(ex_chunks)} example chunks"
            )


def test_annotate_vicious_brutal():
    """Vicious example 'a vicious attack' + synonym 'brutal' annotates to 'a vicious (brutal) attack'."""
    card = _card(
        word="vicious", pos="adjective", cefr="C1",
        example="a vicious attack",
    )
    specs = [
        {"text": "a vicious attack", "synonyms": ["brutal"], "antonyms": []},
    ]
    annotated, syn_meta, ant_meta, errors = annotate_card_examples(card, specs, {})
    assert errors == []
    assert annotated == "a vicious (brutal) attack"
    assert syn_meta == "brutal"
    assert ant_meta == ""
