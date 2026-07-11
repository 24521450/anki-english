from collections import Counter

from tools.archive.data_migrations._apply_semantic_overload_grouping import (
    GROUPINGS,
    KEEP_GUIDS,
)


def test_semantic_overload_manifest_has_ten_repairs_and_two_keeps():
    assert len(GROUPINGS) == 10
    assert KEEP_GUIDS == {"B7[0+R><3N", "ka@NZF]8Qa"}
    assert Counter(grouping.owner for grouping in GROUPINGS) == {
        "audit": 8,
        "review": 2,
    }
    assert len({grouping.guid for grouping in GROUPINGS}) == 10


def test_every_grouping_has_three_aligned_display_chunks():
    for grouping in GROUPINGS:
        assert len(grouping.definition.split("|")) == 3, grouping.word
        assert len(grouping.example.split("|")) == 3, grouping.word
        assert "<br><br>" in grouping.example, grouping.word
