"""Stable, dependency-light source sense identity contract."""
from __future__ import annotations

import hashlib
import json


def source_sense_id(record: dict, flat_sense) -> str:
    """Return the existing audit ID without depending on audit/XLSX code."""
    definition = record["pos_data"][flat_sense.pd_idx]["definitions"][flat_sense.def_idx]
    identity = {
        "word": record.get("word"),
        "homonym_index": record.get("homonym_index"),
        "source_files": record.get("source_files") or [],
        "pos": flat_sense.pos,
        "pd_idx": flat_sense.pd_idx,
        "def_idx": flat_sense.def_idx,
        "sensenum_local": definition.get("sensenum_local"),
        "text": definition.get("text"),
    }
    payload = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    prefix = "cam_" if (record.get("source") or "").casefold() == "cambridge" else "ox_"
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
