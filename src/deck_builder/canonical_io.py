"""Canonical UTF-8/LF serialization helpers for hash-bound text artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


def canonical_text_bytes(payload: bytes) -> bytes:
    """Normalize UTF-8 text bytes before hashing across operating systems."""
    text = payload.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_text_sha256(payload: bytes) -> str:
    return hashlib.sha256(canonical_text_bytes(payload)).hexdigest()


def canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if newline:
        text += "\n"
    return text.encode("utf-8")


def canonical_jsonl_bytes(rows: Iterable[dict]) -> bytes:
    return b"".join(canonical_json_bytes(row, newline=True) for row in rows)


def load_jsonl_document(path: Path) -> tuple[bytes, list[dict]]:
    """Load JSONL and return the canonical bytes used for provenance hashes."""
    canonical = canonical_text_bytes(path.read_bytes())
    rows = [
        json.loads(line)
        for line in canonical.decode("utf-8").splitlines()
        if line.strip()
    ]
    return canonical, rows
