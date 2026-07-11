from collections import Counter

from tools.archive.data_migrations._apply_sense_grouping_review import (
    REPAIRS,
    RETIRED_GUIDS,
    UNCHANGED_KEEP_GUIDS,
)


def test_sense_grouping_manifest_is_complete_and_unique():
    assert len(REPAIRS) == 46
    assert len({repair.guid for repair in REPAIRS}) == 46
    assert Counter(repair.owner for repair in REPAIRS) == {"audit": 32, "review": 14}
    assert RETIRED_GUIDS == {"blK!z$J^4}", "OZZPa?0t@2"}
    assert len(UNCHANGED_KEEP_GUIDS) == 6


def test_grouping_shapes_match_definitions():
    for repair in REPAIRS:
        assert len(repair.definition.split("|")) == len(repair.groups), repair.word
        if len(repair.groups) == 1 and any(len(group) > 1 for group in repair.groups):
            assert len(repair.definition.split("|")) == 1
