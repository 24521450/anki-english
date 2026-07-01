from __future__ import annotations

GLOSS_REVIEW_FIX_STATUS = "gloss_review_log_20260630"
DEF_BEFORE_SYNC_FIX_STATUS = "def_before_oxford_sync_20260701"
HOMONYM_SPLIT_FIX_STATUS = "homonym_split_20260701"

DELETED_KEYS = {
    ("resilient", "adjective, noun", "UNCLASSIFIED"),
    ("byproducts", "noun", "UNCLASSIFIED"),
    ("carrying capacity", "noun", "UNCLASSIFIED"),
    ("consist", "verb", "B1"),
    ("criteria", "noun", "UNCLASSIFIED"),
    ("dabbler", "noun", "UNCLASSIFIED"),
    ("designated", "adjective", "UNCLASSIFIED"),
    ("destabilizing", "verb", "UNCLASSIFIED"),
    ("eliminated", "verb", "UNCLASSIFIED"),
    ("evolved", "verb", "UNCLASSIFIED"),
    ("extrapolated", "verb", "UNCLASSIFIED"),
    ("foraging", "noun", "UNCLASSIFIED"),
    ("gouging", "noun", "UNCLASSIFIED"),
    ("harbor", "noun", "UNCLASSIFIED"),
    ("harbor", "verb", "UNCLASSIFIED"),
    ("hyperfocus", "verb", "UNCLASSIFIED"),
    ("interweave", "verb", "UNCLASSIFIED"),
    ("invading", "verb", "UNCLASSIFIED"),
    ("ligaments", "noun", "UNCLASSIFIED"),
    ("logistical", "adjective", "UNCLASSIFIED"),
    ("randomized", "adjective", "UNCLASSIFIED"),
    ("relay", "noun", "UNCLASSIFIED"),
    ("shortsighted", "adjective", "UNCLASSIFIED"),
    ("shunned", "verb", "UNCLASSIFIED"),
    ("soullessly", "verb", "UNCLASSIFIED"),
    ("strip", "verb", "C1"),
    ("unfiltered", "adjective", "UNCLASSIFIED"),
    ("untethered", "adjective", "UNCLASSIFIED"),
    ("vertebrae", "noun", "UNCLASSIFIED"),
    ("wellbeing", "noun", "UNCLASSIFIED"),
    ("zigzagging", "verb", "UNCLASSIFIED"),
    ("deposit", "noun", "C2")
}

REPLACED_KEYS = {
    ("curated", "adjective", "UNCLASSIFIED"): ("curate", "verb", "UNCLASSIFIED"),
    ("strip", "noun, verb", "C2"): ("strip", "noun", "C2"),
}

SPLIT_KEYS = {
    ("incline", "noun, verb", "UNCLASSIFIED"): [
        ("incline", "noun, verb", "C2"),
        ("incline", "verb", "UNCLASSIFIED")
    ]
}

def fix_status(row: dict | None) -> str:
    """Extract and normalize fix_status from an audit row."""
    if row is None:
        return ""
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
    if fix_status(row) == DEF_BEFORE_SYNC_FIX_STATUS:
        return True
    if fix_status(row) == HOMONYM_SPLIT_FIX_STATUS:
        return True
    if not extra_statuses:
        return False
    if isinstance(extra_statuses, str):
        extra_statuses = {extra_statuses}
    return fix_status(row) in extra_statuses
