from copy import deepcopy

from src.deck_builder.semantic_policy import (
    REQUIRED_USER_EXACT_VI_LOCKS,
    validate_audit_policy,
    validate_built_policy,
    validate_policy_rows,
    validate_required_user_exact_vi_locks,
    validate_registry_policy,
    validate_vietnamese_user_lock_evidence,
)
from src.config import ProjectPaths
import json


def _lock(kind="exact_vi", **overrides):
    row = {
        "schema_version": 1,
        "lock_id": "lock-1",
        "kind": kind,
        "authority": "user" if kind == "exact_vi" else "adr",
        "decision_ref": "USER_NOTES.md",
        "guid": "g1",
        "word": "compel",
        "semantic_sense_id": "sem-1" if kind != "exclude_source_sense" else "",
        "source_sense_id": "source-1" if kind == "retain_source_sense" else "",
        "expected_vi": "ép buộc" if kind == "exact_vi" else "",
        "supersedes": "",
    }
    row.update(overrides)
    return row


def _audit():
    return {
        "guid": "g1",
        "word": "compel",
        "semantic_senses": [{
            "semantic_sense_id": "sem-1",
            "source_sense_ids": ["source-1"],
            "decision": "pass",
            "current": {"definition_vi": "ép buộc"},
        }],
        "source_coverage": [{
            "source_sense_id": "source-1",
            "disposition": "mapped",
            "target_semantic_sense_ids": ["sem-1"],
        }],
    }


def _registry():
    return {
        "guid": "g1",
        "word": "compel",
        "senses": [{
            "semantic_sense_id": "sem-1",
            "order": 1,
            "definition_vi": "ép buộc",
            "source_sense_ids": ["source-1"],
        }],
    }


def test_exact_vi_lock_is_checked_across_every_production_layer():
    locks = [_lock()]
    assert validate_audit_policy([_audit()], locks) == []
    assert validate_registry_policy([_registry()], locks) == []
    assert validate_built_policy(
        [{"guid": "g1", "definition_vi": "ép buộc"}], [_registry()], locks
    ) == []

    changed = deepcopy(_registry())
    changed["senses"][0]["definition_vi"] = "khiến trở nên cần thiết"
    assert "policy_exact_vi_mismatch:lock-1" in validate_registry_policy(
        [changed], locks
    )


def test_source_retention_and_exclusion_are_fail_closed():
    retain = _lock("retain_source_sense")
    assert validate_audit_policy([_audit()], [retain]) == []

    audit = _audit()
    audit["source_coverage"][0].update({
        "disposition": "excluded",
        "target_semantic_sense_ids": [],
    })
    exclude = _lock(
        "exclude_source_sense",
        semantic_sense_id="",
        source_sense_id="source-1",
    )
    assert validate_audit_policy([audit], [exclude]) == []
    assert "policy_excluded_source_promoted:lock-1" in validate_registry_policy(
        [_registry()], [exclude]
    )


def test_policy_supersession_must_be_append_only_and_same_identity():
    original = _lock()
    replacement = _lock(
        lock_id="lock-2",
        supersedes="lock-1",
        expected_vi="bắt buộc",
    )
    assert validate_policy_rows([original, replacement]) == []

    assert any(
        error.startswith("policy_unknown_or_forward_supersession")
        for error in validate_policy_rows([replacement, original])
    )


def test_canonical_policy_contains_every_exact_user_wording_lock():
    path = ProjectPaths().semantic_policy_locks
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert validate_required_user_exact_vi_locks(rows) == []
    active_exact = {
        row["lock_id"]: row["expected_vi"]
        for row in rows
        if row["kind"] == "exact_vi" and row["authority"] == "user"
    }
    assert active_exact == {
        lock_id: expected["expected_vi"]
        for lock_id, expected in REQUIRED_USER_EXACT_VI_LOCKS.items()
    }


def test_required_user_wording_lock_cannot_be_deleted_or_edited():
    rows = [
        _lock(
            lock_id=lock_id,
            guid=expected["guid"],
            word=expected["word"],
            semantic_sense_id=expected["semantic_sense_id"],
            expected_vi=expected["expected_vi"],
        )
        for lock_id, expected in REQUIRED_USER_EXACT_VI_LOCKS.items()
    ]
    assert validate_required_user_exact_vi_locks(rows) == []

    removed = rows[1:]
    removed_id = rows[0]["lock_id"]
    assert f"policy_missing_required_user_lock:{removed_id}" in (
        validate_required_user_exact_vi_locks(removed)
    )

    changed = deepcopy(rows)
    changed[0]["expected_vi"] += "!"
    lock_id = changed[0]["lock_id"]
    assert f"policy_changed_required_user_lock:{lock_id}" in (
        validate_required_user_exact_vi_locks(changed)
    )

    replacement = deepcopy(rows[0])
    replacement.update({
        "lock_id": "replacement-lock",
        "expected_vi": "khiến trở nên cần thiết",
        "supersedes": rows[0]["lock_id"],
    })
    superseded = [*rows, replacement]
    assert validate_policy_rows(superseded) == []
    assert (
        "policy_superseded_required_user_lock:"
        f"{rows[0]['lock_id']}:replacement-lock"
    ) in validate_required_user_exact_vi_locks(superseded)


def test_vietnamese_user_lock_evidence_must_match_an_active_policy_row():
    lock = _lock()
    review = {
        "candidate_id": "g1::sem-1",
        "guid": "g1",
        "word": "compel",
        "semantic_sense_id": "sem-1",
        "decision": "keep_natural",
        "reason_code": "user_lock",
        "lock_id": "lock-1",
        "expected_definition_vi": "ép buộc",
        "proposed_vi": "",
    }
    assert validate_vietnamese_user_lock_evidence([review], [lock]) == []

    fake = deepcopy(review)
    fake["lock_id"] = "invented-lock"
    errors = validate_vietnamese_user_lock_evidence([fake], [lock])
    assert "policy_review_unknown_or_inactive_user_lock" in "\n".join(errors)
    assert "policy_review_missing_user_lock:lock-1" in errors

    wrong_vi = deepcopy(review)
    wrong_vi["expected_definition_vi"] = "khiến trở nên cần thiết"
    assert (
        "policy_review_user_lock_mismatch:g1::sem-1:lock-1"
        in validate_vietnamese_user_lock_evidence([wrong_vi], [lock])
    )


def test_every_active_exact_user_lock_requires_an_explicit_review_claim():
    assert validate_vietnamese_user_lock_evidence([], [_lock()]) == [
        "policy_review_missing_user_lock:lock-1"
    ]
