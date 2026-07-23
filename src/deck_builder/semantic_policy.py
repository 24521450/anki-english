"""Machine-readable locks for reviewed learner-facing semantic decisions."""
from __future__ import annotations

from collections.abc import Iterable

from src.deck_builder.canonical_io import canonical_jsonl_bytes


POLICY_SCHEMA_VERSION = 1
POLICY_KINDS = {
    "exact_vi",
    "absent_semantic_sense",
    "exclude_source_sense",
    "retain_source_sense",
}
POLICY_AUTHORITIES = {"user", "adr"}
# These user-locked glosses are release invariants, not merely optional rows in
# the policy ledger.  Changing one requires an explicit user decision plus a
# matching code/data change, so deleting the ledger row cannot silently relax
# the contract.
REQUIRED_USER_EXACT_VI_LOCKS = {
    "exact_vi-compel-e02bd4db9b498b18b527db3e": {
        "guid": "N.6C{{Q%GG",
        "word": "compel",
        "semantic_sense_id": "sem_e02bd4db9b498b18b527db3e",
        "expected_vi": "ép buộc",
    },
    "exact_vi-contender-73bc855ad768af184e76094a": {
        "guid": "kIw0>Ohr#P",
        "word": "contender",
        "semantic_sense_id": "sem_73bc855ad768af184e76094a",
        "expected_vi": "đối thủ nặng ký",
    },
    "exact_vi-contend-with-d1cc03bcff6977280e280a23": {
        "guid": ";hj(dC?}9D",
        "word": "contend with sb/sth",
        "semantic_sense_id": "sem_d1cc03bcff6977280e280a23",
        "expected_vi": "đối phó",
    },
    "exact_vi-transcribe-75c277bcdafac903c8006c74": {
        "guid": "LD:NA=zzJA",
        "word": "transcribe",
        "semantic_sense_id": "sem_75c277bcdafac903c8006c74",
        "expected_vi": "chép lại",
    },
    "exact_vi-venture-ecd3888b7ae628ac2c2ac3e5": {
        "guid": "xrqZ_nwwe]",
        "word": "venture",
        "semantic_sense_id": "sem_ecd3888b7ae628ac2c2ac3e5",
        "expected_vi": "mạo hiểm, cả gan",
    },
}
_ROW_FIELDS = {
    "schema_version",
    "lock_id",
    "kind",
    "authority",
    "decision_ref",
    "guid",
    "word",
    "semantic_sense_id",
    "source_sense_id",
    "expected_vi",
    "supersedes",
}


def validate_policy_rows(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, dict] = {}
    superseded: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("policy_invalid_row_type")
            continue
        lock_id = str(row.get("lock_id") or "")
        if set(row) != _ROW_FIELDS:
            errors.append(f"policy_invalid_fields:{lock_id}")
        if row.get("schema_version") != POLICY_SCHEMA_VERSION:
            errors.append(f"policy_invalid_schema:{lock_id}")
        if not lock_id or lock_id in seen:
            errors.append(f"policy_duplicate_or_empty_lock_id:{lock_id}")
        kind = row.get("kind")
        if kind not in POLICY_KINDS:
            errors.append(f"policy_invalid_kind:{lock_id}:{kind}")
        if row.get("authority") not in POLICY_AUTHORITIES:
            errors.append(f"policy_invalid_authority:{lock_id}")
        for field in ("decision_ref", "guid", "word"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"policy_missing_{field}:{lock_id}")

        semantic_id = str(row.get("semantic_sense_id") or "")
        source_id = str(row.get("source_sense_id") or "")
        expected_vi = str(row.get("expected_vi") or "")
        if kind == "exact_vi":
            if not semantic_id or not expected_vi or source_id:
                errors.append(f"policy_invalid_exact_vi:{lock_id}")
        elif kind == "absent_semantic_sense":
            if not semantic_id or source_id or expected_vi:
                errors.append(f"policy_invalid_absent_sense:{lock_id}")
        elif kind == "exclude_source_sense":
            if semantic_id or not source_id or expected_vi:
                errors.append(f"policy_invalid_source_exclusion:{lock_id}")
        elif kind == "retain_source_sense":
            if not semantic_id or not source_id or expected_vi:
                errors.append(f"policy_invalid_source_retention:{lock_id}")

        parent_id = str(row.get("supersedes") or "")
        if parent_id:
            parent = seen.get(parent_id)
            if parent is None:
                errors.append(f"policy_unknown_or_forward_supersession:{lock_id}:{parent_id}")
            elif parent_id in superseded:
                errors.append(f"policy_duplicate_supersession:{parent_id}")
            elif any(
                row.get(field) != parent.get(field)
                for field in ("kind", "guid", "word")
            ):
                errors.append(f"policy_supersession_identity_mismatch:{lock_id}")
            else:
                superseded.add(parent_id)
        seen[lock_id] = row
    return errors


def validate_required_user_exact_vi_locks(rows: list[dict]) -> list[str]:
    """Require every explicit user wording lock with its exact identity/text."""

    indexed = {
        str(row.get("lock_id") or ""): row
        for row in rows
        if isinstance(row, dict)
    }
    errors: list[str] = []
    required_ids = set(REQUIRED_USER_EXACT_VI_LOCKS)
    for row in rows:
        superseded_id = str(row.get("supersedes") or "")
        if superseded_id in required_ids:
            errors.append(
                "policy_superseded_required_user_lock:"
                f"{superseded_id}:{row.get('lock_id') or ''}"
            )
    for lock_id, expected in REQUIRED_USER_EXACT_VI_LOCKS.items():
        row = indexed.get(lock_id)
        if row is None:
            errors.append(f"policy_missing_required_user_lock:{lock_id}")
            continue
        required = {
            "kind": "exact_vi",
            "authority": "user",
            "decision_ref": "USER_NOTES.md",
            **expected,
        }
        if any(row.get(field) != value for field, value in required.items()):
            errors.append(f"policy_changed_required_user_lock:{lock_id}")
    return errors


def validate_vietnamese_user_lock_evidence(
    review_rows: list[dict], policy_rows: list[dict]
) -> list[str]:
    """Bind every ``user_lock`` review verdict to one active exact-VI policy row.

    The Vietnamese review schema deliberately stays reusable without a policy
    document.  Promotion uses this cross-document validator so a reviewer
    cannot bypass row-specific evidence by inventing a non-empty ``lock_id``.
    """

    active_user_locks = {
        str(row.get("lock_id") or ""): row
        for row in active_policy_rows(policy_rows)
        if row.get("kind") == "exact_vi" and row.get("authority") == "user"
    }
    claimed: dict[str, str] = {}
    errors: list[str] = []
    for review in review_rows:
        if review.get("reason_code") != "user_lock":
            continue
        candidate_id = str(review.get("candidate_id") or "")
        lock_id = str(review.get("lock_id") or "")
        lock = active_user_locks.get(lock_id)
        if lock is None:
            errors.append(
                f"policy_review_unknown_or_inactive_user_lock:{candidate_id}:{lock_id}"
            )
            continue
        previous = claimed.get(lock_id)
        if previous is not None:
            errors.append(
                f"policy_review_duplicate_user_lock:{lock_id}:{previous}:{candidate_id}"
            )
        else:
            claimed[lock_id] = candidate_id
        final_vi = (
            str(review.get("proposed_vi") or "")
            if review.get("decision") == "rewrite"
            else str(review.get("expected_definition_vi") or "")
        )
        if any(
            (
                review.get("guid") != lock.get("guid"),
                review.get("word") != lock.get("word"),
                review.get("semantic_sense_id") != lock.get("semantic_sense_id"),
                final_vi != lock.get("expected_vi"),
            )
        ):
            errors.append(
                f"policy_review_user_lock_mismatch:{candidate_id}:{lock_id}"
            )

    for lock_id in sorted(set(active_user_locks) - set(claimed)):
        errors.append(f"policy_review_missing_user_lock:{lock_id}")
    return sorted(errors)


def active_policy_rows(rows: list[dict]) -> list[dict]:
    superseded = {str(row.get("supersedes") or "") for row in rows}
    return [row for row in rows if row.get("lock_id") not in superseded]


def _index_cards(rows: Iterable[dict]) -> tuple[dict[str, dict], list[str]]:
    indexed: dict[str, dict] = {}
    errors: list[str] = []
    for row in rows:
        guid = str(row.get("guid") or "")
        if not guid or guid in indexed:
            errors.append(f"policy_duplicate_or_empty_guid:{guid}")
            continue
        indexed[guid] = row
    return indexed, errors


def _effective_audit_senses(card: dict) -> dict[str, tuple[dict, dict]]:
    senses: dict[str, tuple[dict, dict]] = {}
    for sense in card.get("semantic_senses") or []:
        semantic_id = str(sense.get("semantic_sense_id") or "")
        if sense.get("decision") == "pass":
            content = sense.get("current") or {}
        elif sense.get("decision") == "repair_proposed" and sense.get("approval") == "approved":
            content = sense.get("proposed") or {}
        else:
            content = {}
        senses[semantic_id] = (sense, content)
    return senses


def validate_audit_policy(audit_rows: list[dict], policy_rows: list[dict]) -> list[str]:
    errors = validate_policy_rows(policy_rows)
    cards, card_errors = _index_cards(audit_rows)
    errors.extend(card_errors)
    for lock in active_policy_rows(policy_rows):
        lock_id = lock["lock_id"]
        card = cards.get(lock["guid"])
        if card is None:
            errors.append(f"policy_missing_audit_card:{lock_id}")
            continue
        if card.get("word") != lock["word"]:
            errors.append(f"policy_audit_word_mismatch:{lock_id}")
        senses = _effective_audit_senses(card)
        coverage = {
            str(item.get("source_sense_id") or ""): item
            for item in card.get("source_coverage") or []
        }
        kind = lock["kind"]
        semantic_id = lock["semantic_sense_id"]
        source_id = lock["source_sense_id"]
        if kind == "exact_vi":
            pair = senses.get(semantic_id)
            if pair is None or pair[1].get("definition_vi") != lock["expected_vi"]:
                errors.append(f"policy_exact_vi_mismatch:{lock_id}")
        elif kind == "absent_semantic_sense":
            if semantic_id in senses:
                errors.append(f"policy_removed_sense_restored:{lock_id}")
        elif kind == "exclude_source_sense":
            item = coverage.get(source_id)
            if item is None or item.get("disposition") != "excluded" or item.get(
                "target_semantic_sense_ids"
            ):
                errors.append(f"policy_source_not_excluded:{lock_id}")
        elif kind == "retain_source_sense":
            pair = senses.get(semantic_id)
            item = coverage.get(source_id)
            if (
                pair is None
                or source_id not in (pair[0].get("source_sense_ids") or [])
                or item is None
                or item.get("disposition") != "mapped"
                or semantic_id not in (item.get("target_semantic_sense_ids") or [])
            ):
                errors.append(f"policy_source_not_retained:{lock_id}")
    return errors


def validate_registry_policy(
    registry_rows: list[dict], policy_rows: list[dict]
) -> list[str]:
    errors = validate_policy_rows(policy_rows)
    cards, card_errors = _index_cards(registry_rows)
    errors.extend(card_errors)
    for lock in active_policy_rows(policy_rows):
        lock_id = lock["lock_id"]
        card = cards.get(lock["guid"])
        if card is None:
            errors.append(f"policy_missing_registry_card:{lock_id}")
            continue
        senses = {
            str(sense.get("semantic_sense_id") or ""): sense
            for sense in card.get("senses") or []
        }
        all_source_ids = {
            source_id
            for sense in senses.values()
            for source_id in sense.get("source_sense_ids") or []
        }
        kind = lock["kind"]
        semantic_id = lock["semantic_sense_id"]
        source_id = lock["source_sense_id"]
        if kind == "exact_vi":
            sense = senses.get(semantic_id)
            if sense is None or sense.get("definition_vi") != lock["expected_vi"]:
                errors.append(f"policy_exact_vi_mismatch:{lock_id}")
        elif kind == "absent_semantic_sense":
            if semantic_id in senses:
                errors.append(f"policy_removed_sense_restored:{lock_id}")
        elif kind == "exclude_source_sense":
            if source_id in all_source_ids:
                errors.append(f"policy_excluded_source_promoted:{lock_id}")
        elif kind == "retain_source_sense":
            sense = senses.get(semantic_id)
            if sense is None or source_id not in (sense.get("source_sense_ids") or []):
                errors.append(f"policy_source_not_retained:{lock_id}")
    return errors


def validate_built_policy(
    note_rows: list[dict], registry_rows: list[dict], policy_rows: list[dict]
) -> list[str]:
    errors = validate_registry_policy(registry_rows, policy_rows)
    notes, note_errors = _index_cards(note_rows)
    registry, registry_errors = _index_cards(registry_rows)
    errors.extend(note_errors)
    errors.extend(registry_errors)
    for lock in active_policy_rows(policy_rows):
        if lock["kind"] != "exact_vi":
            continue
        note = notes.get(lock["guid"])
        card = registry.get(lock["guid"])
        if note is None or card is None:
            errors.append(f"policy_missing_built_card:{lock['lock_id']}")
            continue
        senses = card.get("senses") or []
        orders = {
            sense.get("semantic_sense_id"): int(sense.get("order") or 0)
            for sense in senses
        }
        order = orders.get(lock["semantic_sense_id"], 0)
        cells = str(note.get("definition_vi") or "").split("|")
        if order < 1 or order > len(cells) or cells[order - 1] != lock["expected_vi"]:
            errors.append(f"policy_built_vi_mismatch:{lock['lock_id']}")
    return errors


def serialize_policy_rows(rows: list[dict]) -> str:
    return canonical_jsonl_bytes(rows).decode("utf-8")
