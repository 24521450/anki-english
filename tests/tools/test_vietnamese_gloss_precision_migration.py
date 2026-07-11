from collections import Counter

from tools.archive.data_migrations._apply_vietnamese_gloss_precision_review import REPAIRS


def test_vietnamese_gloss_precision_manifest_is_complete():
    assert len(REPAIRS) == 12
    assert len({repair.guid for repair in REPAIRS}) == 12
    assert Counter(repair.owner for repair in REPAIRS) == {"audit": 8, "review": 4}


def test_repaired_translations_no_longer_have_three_slash_variants():
    for repair in REPAIRS:
        for chunk in repair.new_definition.split("|"):
            translation = chunk.rsplit("(", 1)[-1].rstrip(")")
            assert translation.count("/") < 2, repair.word
