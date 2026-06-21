import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# We will import these from our tool to be implemented
from tools._apply_card_identity_p2 import should_delete_row, process_rows

# Sample keeper and loser rows for testing
SAMPLE_LOSER_LABOR = {
    "word": "labor", "pos": "noun", "cefr": "C2",
    "def_before": "the period of time or the process of giving birth to a baby",
    "gloss_after": "process of giving birth",
    "gate_status": "skip_fallback", "source": "original_100pct",
    "rule_applied": "concrete_1sense", "fix_status": "rebuilt"
}

SAMPLE_KEEPER_LABOR = {
    "word": "labor", "pos": "noun", "cefr": "C2",
    "def_before": "the period of time or the process of giving birth to a baby",
    "gloss_after": "childbirth",
    "gate_status": "pass", "source": "original_100pct",
    "rule_applied": None, "fix_status": "rebuilt"
}

SAMPLE_LOSER_DIPLOMATIC = {
    "word": "diplomatic", "pos": "adjective", "cefr": "C1",
    "def_before": "connected with managing relations between countries (= diplomacy)|having or showing skill in dealing with people in difficult situations",
    "gloss_after": "political|tactful",
    "gate_status": "pass", "source": "rerun_v2_streamA",
    "rule_applied": "2sense_distinct", "fix_status": "rebuilt"
}

SAMPLE_KEEPER_DIPLOMATIC = {
    "word": "diplomatic", "pos": "adjective", "cefr": "C1",
    "def_before": "connected with managing relations between countries; having or showing skill in dealing with people in difficult situations",
    "gloss_after": "international|tactful",
    "gate_status": "pass", "source": "missing_oxford_5000",
    "rule_applied": "POS_DEF_MISMATCH_fixed", "fix_status": "rebuilt"
}

SAMPLE_UNRELATED_ROW = {
    "word": "behalf", "pos": "noun", "cefr": "C1",
    "def_before": "on behalf of", "gloss_after": "in someone's place; representing them",
    "gate_status": "skip_fallback", "source": "streamD_legacy_20260618", "fix_status": "kept_no_match"
}


def test_should_delete_row():
    # Should delete the exact loser row
    assert should_delete_row(SAMPLE_LOSER_LABOR) is True
    assert should_delete_row(SAMPLE_LOSER_DIPLOMATIC) is True

    # Should NOT delete the keeper rows
    assert should_delete_row(SAMPLE_KEEPER_LABOR) is False
    assert should_delete_row(SAMPLE_KEEPER_DIPLOMATIC) is False

    # Should NOT delete unrelated rows
    assert should_delete_row(SAMPLE_UNRELATED_ROW) is False


def test_process_rows_success():
    # Mock data representing 5 losers + some keepers + unrelated rows
    all_guards_losers = [
        # 1. labor
        SAMPLE_LOSER_LABOR,
        # 2. migrate
        {
            "word": "migrate", "pos": "verb", "cefr": "C1",
            "def_before": "to move from one town, country, etc. to go and live and/or work in another",
            "gloss_after": "move", "gate_status": "skip_fallback", "source": "original_100pct",
            "rule_applied": None, "fix_status": "p1_rewritten"
        },
        # 3. navigate
        {
            "word": "navigate", "pos": "verb", "cefr": "C1",
            "def_before": "to find your way around on the internet or on a particular website",
            "gloss_after": "find way", "gate_status": "skip_fallback", "source": "original_100pct",
            "rule_applied": None, "fix_status": "p1_rewritten"
        },
        # 4. sanctuary
        {
            "word": "sanctuary", "pos": "noun", "cefr": "C2",
            "def_before": "a holy building or the part of it that is considered the most holy",
            "gloss_after": "holy place", "gate_status": "skip_fallback", "source": "original_100pct",
            "rule_applied": None, "fix_status": "p1_rewritten"
        },
        # 5. diplomatic
        SAMPLE_LOSER_DIPLOMATIC
    ]

    keepers_and_others = [
        SAMPLE_KEEPER_LABOR,
        SAMPLE_KEEPER_DIPLOMATIC,
        SAMPLE_UNRELATED_ROW
    ]

    input_rows = all_guards_losers + keepers_and_others
    # Expect success and exactly 5 rows removed
    result = process_rows(input_rows)
    assert result is not None
    assert len(result) == len(keepers_and_others)
    # Check that keepers are present and losers are absent
    assert SAMPLE_KEEPER_LABOR in result
    assert SAMPLE_KEEPER_DIPLOMATIC in result
    assert SAMPLE_UNRELATED_ROW in result
    assert SAMPLE_LOSER_LABOR not in result
    assert SAMPLE_LOSER_DIPLOMATIC not in result


def test_process_rows_abort_on_mismatch():
    # Only 4 losers present, missing sanctuary duplicate loser
    incomplete_losers = [
        SAMPLE_LOSER_LABOR,
        SAMPLE_LOSER_DIPLOMATIC
    ]
    input_rows = incomplete_losers + [SAMPLE_UNRELATED_ROW]
    
    # Should return None or raise to signal abort
    with pytest.raises(ValueError, match="Did not find exactly 5 duplicate loser rows"):
        process_rows(input_rows)
