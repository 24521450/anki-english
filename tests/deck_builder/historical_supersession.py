from __future__ import annotations

GLOSS_REVIEW_FIX_STATUS = "gloss_review_log_20260630"

def fix_status(row: dict) -> str:
    """Extract and normalize fix_status from an audit row."""
    return (row.get("fix_status") or "").strip()

def is_gloss_review_superseded(row: dict) -> bool:
    """Check if the row is superseded by the latest gloss review log."""
    return fix_status(row) == GLOSS_REVIEW_FIX_STATUS

def is_superseded_by(row: dict, statuses: set[str] | list[str] | str) -> bool:
    """Check if the row is superseded by any of the specified statuses."""
    if isinstance(statuses, str):
        statuses = {statuses}
    return fix_status(row) in statuses

def should_tolerate_historical_drift(row: dict, extra_statuses: set[str] | list[str] | str = ()) -> bool:
    """Return True if the row has been superseded by the latest gloss review log
    or any other status in extra_statuses, making historical drift tolerable.
    """
    if is_gloss_review_superseded(row):
        return True
    if not extra_statuses:
        return False
    if isinstance(extra_statuses, str):
        extra_statuses = {extra_statuses}
    return fix_status(row) in extra_statuses
