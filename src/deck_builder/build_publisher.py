"""Transactional publisher for the two generated Anki note artifacts."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from src.deck_builder.build_contracts import BuildNotesResult
from src.deck_builder.build_issues import BuildIssue, BuildValidationError
from src.deck_builder.build_validation import (
    ValidationReport,
    sha256_file,
    validate_artifact_paths,
    validate_build_result,
)
from src.deck_builder.registry_build import RegistryBuildInputs


class PublishFault(RuntimeError):
    """Raised by tests to simulate a crash/failure at a publish step."""


def _fsync_file(path: Path) -> None:
    with path.open("rb") as fh:
        os.fsync(fh.fileno())


def _write_text_fsynced(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def _write_json_atomic(path: Path, data: dict, *, fault_at: str | None = None) -> None:
    if fault_at == "journal_update":
        raise PublishFault("injected fault at journal update")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_journal(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _restore_from_journal(txn_dir: Path, journal: dict) -> None:
    old_dir = txn_dir / "old"
    targets = journal.get("targets") or {}
    old = journal.get("old") or {}
    for name in ("anki_notes.jsonl", "anki_notes.txt"):
        target = Path(targets[name])
        old_info = old.get(name) or {}
        old_path = old_dir / name
        if old_info.get("exists"):
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(old_path, target)
        elif target.exists():
            target.unlink()


def _recover_one_transaction(txn_dir: Path, journal: dict) -> None:
    state = journal.get("state")
    if state == "committed":
        targets = journal.get("targets") or {}
        staged_hashes = journal.get("staged") or {}
        mismatches = []
        for name in ("anki_notes.jsonl", "anki_notes.txt"):
            target = Path(targets[name])
            expected = (staged_hashes.get(name) or {}).get("sha256")
            if not target.exists() or sha256_file(target) != expected:
                mismatches.append(name)
        if mismatches:
            raise BuildValidationError([
                BuildIssue(
                    "error",
                    "committed_hash_mismatch",
                    f"committed transaction {txn_dir.name} has target hash mismatch: {mismatches}",
                    source=txn_dir / "journal.json",
                )
            ])
        shutil.rmtree(txn_dir, ignore_errors=True)
    elif state in {"prepared", "jsonl_replaced", "txt_replaced"}:
        _restore_from_journal(txn_dir, journal)
        shutil.rmtree(txn_dir, ignore_errors=True)
    else:
        raise BuildValidationError([
            BuildIssue(
                "error",
                "unknown_transaction_state",
                f"transaction {txn_dir.name} has unknown state {state!r}",
                source=txn_dir / "journal.json",
            )
        ])


def recover_publish_transactions(staging_dir: Path) -> None:
    """Recover any interrupted publish transaction in the staging directory."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    for txn_dir in sorted(staging_dir.glob("txn-*")):
        journal_path = txn_dir / "journal.json"
        if not journal_path.exists():
            shutil.rmtree(txn_dir, ignore_errors=True)
            continue
        _recover_one_transaction(txn_dir, _read_journal(journal_path))

    lock = staging_dir / "publish.lock"
    if lock.exists():
        lock.unlink()


def _acquire_lock(lock_path: Path) -> int:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BuildValidationError([
            BuildIssue("error", "publish_lock_exists", f"publish lock already exists: {lock_path}", source=lock_path)
        ]) from exc


def _copy_old_targets(jsonl_path: Path, txt_path: Path, old_dir: Path) -> dict:
    old_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for path in (jsonl_path, txt_path):
        name = path.name
        if path.exists():
            shutil.copy2(path, old_dir / name)
            out[name] = {"exists": True, "sha256": sha256_file(path)}
        else:
            out[name] = {"exists": False, "sha256": None}
    return out


def _journal_base(txn_id: str, jsonl_path: Path, txt_path: Path, old: dict, staged: dict) -> dict:
    return {
        "schema_version": 1,
        "transaction_id": txn_id,
        "state": "prepared",
        "targets": {
            "anki_notes.jsonl": str(jsonl_path),
            "anki_notes.txt": str(txt_path),
        },
        "old": old,
        "staged": staged,
    }


def publish_build_result_transactional(
    result: BuildNotesResult,
    jsonl_path: Path,
    txt_path: Path,
    registry_inputs: RegistryBuildInputs,
    registry_path: Path,
    audio_dir: Path,
    staging_dir: Path,
    *,
    fault_at: str | None = None,
) -> ValidationReport:
    """Validate and publish JSONL/TXT as an all-or-restore pair."""
    recover_publish_transactions(staging_dir)
    lock_path = staging_dir / "publish.lock"
    lock_fd = _acquire_lock(lock_path)
    txn_dir = staging_dir / f"txn-{uuid.uuid4().hex}"
    journal_path = txn_dir / "journal.json"
    try:
        os.write(lock_fd, str(os.getpid()).encode("ascii"))
        os.fsync(lock_fd)

        report = validate_build_result(result, registry_inputs, audio_dir)
        if not report.ok:
            raise BuildValidationError(report.issues)

        new_dir = txn_dir / "new"
        old_dir = txn_dir / "old"
        staged_jsonl = new_dir / jsonl_path.name
        staged_txt = new_dir / txt_path.name

        if fault_at == "staged_write":
            raise PublishFault("injected fault at staged write")
        _write_text_fsynced(staged_jsonl, result.jsonl_text)
        _write_text_fsynced(staged_txt, result.txt_text)

        staged_report = validate_artifact_paths(staged_jsonl, staged_txt, registry_path, audio_dir)
        if fault_at == "staged_validation":
            raise PublishFault("injected fault at staged validation")
        if not staged_report.ok:
            raise BuildValidationError(staged_report.issues)

        if fault_at == "backup_creation":
            raise PublishFault("injected fault at backup creation")
        old = _copy_old_targets(jsonl_path, txt_path, old_dir)
        staged = {
            "anki_notes.jsonl": {"sha256": sha256_file(staged_jsonl)},
            "anki_notes.txt": {"sha256": sha256_file(staged_txt)},
        }
        journal = _journal_base(txn_dir.name, jsonl_path, txt_path, old, staged)
        _write_json_atomic(journal_path, journal)

        try:
            os.replace(staged_jsonl, jsonl_path)
            if fault_at == "after_jsonl_replace":
                raise PublishFault("injected fault after JSONL replace")
            journal["state"] = "jsonl_replaced"
            _write_json_atomic(journal_path, journal, fault_at=fault_at)

            os.replace(staged_txt, txt_path)
            if fault_at == "after_txt_replace":
                raise PublishFault("injected fault after TXT replace")
            journal["state"] = "txt_replaced"
            _write_json_atomic(journal_path, journal, fault_at=fault_at)

            if (
                sha256_file(jsonl_path) != staged["anki_notes.jsonl"]["sha256"]
                or sha256_file(txt_path) != staged["anki_notes.txt"]["sha256"]
                or fault_at == "hash_verification"
            ):
                raise PublishFault("target hash verification failed")

            journal["state"] = "committed"
            _write_json_atomic(journal_path, journal, fault_at=fault_at)
            shutil.rmtree(txn_dir, ignore_errors=True)
            return staged_report
        except Exception:
            if journal_path.exists():
                _recover_one_transaction(txn_dir, _read_journal(journal_path))
            raise
    finally:
        os.close(lock_fd)
        if lock_path.exists():
            lock_path.unlink()
