import json
from pathlib import Path


AUDIT_PATH = Path("data/review/bilingual_semantic_audit.jsonl")
SEMANTIC_REGISTRY_PATH = Path("data/curated/semantic_registry.jsonl")

# Explicit learner-relevance decisions. These IDs are stable audit identities;
# keeping the table here prevents a later scaffold/promote cycle from silently
# restoring the reviewed niche senses.
REMOVED_SENSES_BY_GUID = {
    "fDXW(m|WN]": {
        "sem_c07cf50448a2f58f49a63219",  # Agile project management
        "sem_10c806fdb751729a3cbd2a71",  # Agile working arrangements
    },
    "?FS8N8JG*N": {"sem_bb4f9ec966295042524fe18e"},  # internet domain
    "[($rY)T[)t": {"sem_5d24cf68388598831e41fd8d"},  # plant cutting
    "DPE9USJCIh": {"sem_dbe31ccff4fe3a86e0ececc8"},  # military detachment
    "iEZhd.29XY": {"sem_f3bf200291d4e4bbc17434b7"},  # glitch music
    "fHFQHXzU[=": {"sem_56f2c79be9bd58d6d1dad1be"},  # inflection paradigm
    "G3Lsl^zOtF": {
        "sem_b73cc4b7cd7faa04c9b47c4b",  # altar area inside a church
        "sem_8a7e6200474839f9c39d7bdd",  # denomination-specific church name
        "sem_a27bee6da3930b5c8e1f50f1",  # funeral chapel subtype
    },
    "Qr=^?OKRgW": {"sem_2d261669eea5368f47275516"},  # humorous comforts use
    "OU7k,s>M|F": {"sem_fe0dd03fd1e9f2991d6e33e5"},  # golf handicap formula
    "I_w2q^IJck": {"sem_e42cfd4e161dc9f8cfad8f8c"},  # sports strip
    "LD:NA=zzJA": {"sem_1a8802fbb16a40fdb8418dae"},  # music transcription
    "4H,imiI94H": {"sem_c7d6455804566324d8d9307e"},  # political informing
}


def _audit_by_guid() -> dict[str, dict]:
    return {
        row["guid"]: row
        for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }


def _semantic_registry_by_guid() -> dict[str, dict]:
    return {
        row["guid"]: row
        for line in SEMANTIC_REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }


def test_reviewed_niche_senses_are_absent_and_have_no_source_targets():
    audit = _audit_by_guid()

    for guid, removed_ids in REMOVED_SENSES_BY_GUID.items():
        card = audit[guid]
        retained_ids = {
            sense["semantic_sense_id"] for sense in card["semantic_senses"]
        }
        assert retained_ids
        assert retained_ids.isdisjoint(removed_ids)
        assert [sense["order"] for sense in card["semantic_senses"]] == list(
            range(1, len(card["semantic_senses"]) + 1)
        )
        for coverage in card["source_coverage"]:
            assert removed_ids.isdisjoint(
                coverage.get("target_semantic_sense_ids") or []
            )


def test_directly_excluded_niche_sources_stay_excluded():
    audit = _audit_by_guid()
    expected = {
        "fDXW(m|WN]": {
            "ox_86c295b95a2b9fb92eb5363b",
            "ox_e1ee3b9d909a3bf272d01018",
        },
        "?FS8N8JG*N": {
            "ox_b798c794856ee954e6ab779d",
            "cam_af05134e38ecab0e74bb67f1",
            "cam_0bf94bde4beb1cf84b95a799",
        },
        "[($rY)T[)t": {
            "ox_b216b00f87a9ce7328421361",
            "cam_9e5420197a5fc6a83b6bf109",
            "cam_098304b3dee79dbaee04a22f",
        },
        "DPE9USJCIh": {"ox_6edd2038539d2c5851b94c0a"},
        "iEZhd.29XY": {"ox_dbbec6fcf209717520e538d9"},
        "fHFQHXzU[=": {"ox_79a2ad7b332c365b73cee33d"},
        "G3Lsl^zOtF": {"ox_e64fd461fa8926b49ed8421e"},
        "Qr=^?OKRgW": {"ox_d9801ebe9ad2761318feea63"},
        "OU7k,s>M|F": {"ox_fc1484305995192c6fb78868"},
        "I_w2q^IJck": {
            "ox_901fa3923ed33651ca01fe95",
            "cam_3145e26d6f711fe5349b700c",
        },
        "LD:NA=zzJA": {"ox_ce82ee4af19257de005705c0"},
        "4H,imiI94H": {
            "ox_82f45acbe6774ee4e3229cb6",
            "cam_e22f4ad6fb6ab85c2939f941",
        },
        "r`_r,m.#U]": {"ox_1ecdd7f4cd992c0618d667aa"},
        "V8mV8Z*-r3": {"ox_8d7848e50bf7752154f6db85"},
        "j;VJZAa9!J": {
            "ox_8dc089a27f6fb2b9edba35dc",
            "cam_8f32a4cb7c01b5f942eec533",
        },
    }

    for guid, source_ids in expected.items():
        coverage = {
            item["source_sense_id"]: item for item in audit[guid]["source_coverage"]
        }
        for source_id in source_ids:
            assert coverage[source_id]["disposition"] == "excluded"
            assert coverage[source_id]["target_semantic_sense_ids"] == []
            assert coverage[source_id]["reason"].strip()


def test_reviewed_lexical_glosses_stay_concise_in_production_registry():
    registry = _semantic_registry_by_guid()

    transcribe = {
        sense["semantic_sense_id"]: sense
        for sense in registry["LD:NA=zzJA"]["senses"]
    }
    assert (
        transcribe["sem_75c277bcdafac903c8006c74"]["definition_en"],
        transcribe["sem_75c277bcdafac903c8006c74"]["definition_vi"],
    ) == (
        "write down / convert into another written form",
        "chép lại",
    )
    assert "sem_4e90d7b508570047f607b454" in transcribe

    implicate = registry["r`_r,m.#U]"]["senses"]
    assert len(implicate) == 1
    assert (
        implicate[0]["semantic_sense_id"],
        implicate[0]["definition_en"],
        implicate[0]["definition_vi"],
    ) == (
        "sem_bafe450cc68be1b69e676410",
        "to show involvement in something bad",
        "dính líu",
    )

    thumb = registry["V8mV8Z*-r3"]["senses"]
    assert len(thumb) == 1
    assert thumb[0]["semantic_sense_id"] == "sem_0c02e3127d301b9bdc37fd3f"
    assert thumb[0]["definition_vi"] == "ngón cái"

    valid = {
        sense["semantic_sense_id"]: sense
        for sense in registry["j;VJZAa9!J"]["senses"]
    }
    assert (
        valid["sem_1b831a43cd31f2d15ab2e0c9"]["definition_en"],
        valid["sem_1b831a43cd31f2d15ab2e0c9"]["definition_vi"],
    ) == ("legally / officially acceptable", "hợp lệ, có hiệu lực")


def test_excluded_sources_and_removed_sense_do_not_reach_production_registry():
    registry = _semantic_registry_by_guid()
    excluded_sources = {
        "4H,imiI94H": {
            "ox_82f45acbe6774ee4e3229cb6",
            "cam_e22f4ad6fb6ab85c2939f941",
        },
        "r`_r,m.#U]": {"ox_1ecdd7f4cd992c0618d667aa"},
        "V8mV8Z*-r3": {"ox_8d7848e50bf7752154f6db85"},
        "j;VJZAa9!J": {
            "ox_8dc089a27f6fb2b9edba35dc",
            "cam_8f32a4cb7c01b5f942eec533",
        },
    }

    for guid, source_ids in excluded_sources.items():
        production_source_ids = {
            source_id
            for sense in registry[guid]["senses"]
            for source_id in sense["source_sense_ids"]
        }
        assert production_source_ids.isdisjoint(source_ids)

    denounce_sense_ids = {
        sense["semantic_sense_id"] for sense in registry["4H,imiI94H"]["senses"]
    }
    assert "sem_c7d6455804566324d8d9307e" not in denounce_sense_ids


def test_legacy_display_owners_do_not_restore_reviewed_niche_content():
    deck_rows = [
        json.loads(line)
        for line in Path("data/curated/deck_audit.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    deck_by_word = {row["word"]: row for row in deck_rows}
    forbidden_by_word = {
        "agile": ("Agile methods", "Agile working", "project method"),
        "chapel": ("funeral chapel", "Methodist", "Mormon"),
        "detach": ("soldiers", "troops", "destroyers"),
        "glitch": ("glitch music", "techno"),
        "handicap": ("golf", "handicap of 5"),
        "paradigm": ("verb paradigms", "grammatical paradigm"),
        "strip": ("sports uniform", "football", "Juventus"),
        "transcribe": ("rewrite music", "transcribe music", "guitar"),
    }
    for word, forbidden in forbidden_by_word.items():
        row = deck_by_word[word]
        displayed = "|".join(
            str(row.get(field) or "")
            for field in ("gloss_after", "example_after", "collocations_after")
        )
        assert all(value not in displayed for value in forbidden)

    manual_rows = [
        json.loads(line)
        for line in Path("data/review/manual_cards.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    paradigm = next(row for row in manual_rows if row["word"] == "paradigm")
    assert "verb paradigms" not in json.dumps(paradigm, ensure_ascii=False)

    override_rows = [
        json.loads(line)
        for line in Path("data/review/non_oxford_non_c2_overrides.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    overrides = {row["word"]: row for row in override_rows}
    assert "soldiers" not in json.dumps(overrides["detach"], ensure_ascii=False)
    assert "verb paradigms" not in json.dumps(overrides["paradigm"], ensure_ascii=False)
    assert "transcribe music" not in json.dumps(overrides["transcribe"], ensure_ascii=False)
