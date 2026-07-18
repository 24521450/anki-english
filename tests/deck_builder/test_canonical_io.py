import hashlib
import json

from src.deck_builder.canonical_io import (
    canonical_jsonl_bytes,
    canonical_text_bytes,
    canonical_text_sha256,
    load_jsonl_document,
)


def test_text_hash_is_independent_of_checkout_newlines():
    lf = b'{"word":"compel"}\n{"word":"venture"}\n'
    crlf = lf.replace(b"\n", b"\r\n")

    assert canonical_text_bytes(crlf) == lf
    assert canonical_text_sha256(crlf) == hashlib.sha256(lf).hexdigest()


def test_load_jsonl_document_returns_canonical_bytes(tmp_path):
    path = tmp_path / "review.jsonl"
    path.write_bytes(b'{"b":2,"a":1}\r\n')

    payload, rows = load_jsonl_document(path)

    assert payload == b'{"b":2,"a":1}\n'
    assert rows == [{"a": 1, "b": 2}]
    assert canonical_jsonl_bytes(rows) == (
        json.dumps(
            {"a": 1, "b": 2},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
