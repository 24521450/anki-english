from __future__ import annotations

from tests.deck_builder.historical_supersession import (
    DEF_BEFORE_SYNC_FIX_STATUS,
    HOMONYM_SPLIT_FIX_STATUS,
    fix_status,
    is_gloss_review_superseded,
    is_superseded_by,
    should_tolerate_historical_drift,
)

def test_fix_status():
    assert fix_status(None) == ""
    assert fix_status({}) == ""
    assert fix_status({"fix_status": None}) == ""
    assert fix_status({"fix_status": "  my_status  "}) == "my_status"

def test_is_gloss_review_superseded():
    assert not is_gloss_review_superseded({})
    assert not is_gloss_review_superseded({"fix_status": "p15_simple_gloss_repaired"})
    assert is_gloss_review_superseded({"fix_status": "gloss_review_log_20260630"})
    assert is_gloss_review_superseded({"fix_status": "  gloss_review_log_20260630  "})

def test_is_superseded_by():
    assert not is_superseded_by({}, "status1")
    assert is_superseded_by({"fix_status": "status1"}, "status1")
    assert is_superseded_by({"fix_status": "status1"}, {"status1", "status2"})
    assert not is_superseded_by({"fix_status": "status3"}, {"status1", "status2"})

def test_should_tolerate_historical_drift():
    assert not should_tolerate_historical_drift({})
    
    # Tolerated because it's the latest review log
    assert should_tolerate_historical_drift({"fix_status": "gloss_review_log_20260630"})
    assert should_tolerate_historical_drift({"fix_status": DEF_BEFORE_SYNC_FIX_STATUS})
    assert should_tolerate_historical_drift({"fix_status": HOMONYM_SPLIT_FIX_STATUS})
    
    # Tolerated because it matches extra_statuses
    assert should_tolerate_historical_drift({"fix_status": "status1"}, "status1")
    assert should_tolerate_historical_drift({"fix_status": "status2"}, {"status1", "status2"})
    
    # Not tolerated
    assert not should_tolerate_historical_drift({"fix_status": "status3"}, {"status1", "status2"})
