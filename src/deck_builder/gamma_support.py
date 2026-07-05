"""Gamma verdict loading and application helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.deck_builder.simplify_senses import simplify_record, _resolve_def


def load_gamma_verdicts(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    for verdict in data.get("verdicts", []):
        out[verdict["cluster_hash"]] = verdict
    return out


def simplify_with_gamma(record: dict, gamma: dict) -> list:
    base = simplify_record(record)
    if not base:
        return base
    for i, merged_sense in enumerate(base):
        src_texts = []
        for pos_data_idx, def_idx in zip(merged_sense.source_pdd_idx, merged_sense.source_def_idx):
            definition = _resolve_def(record, pos_data_idx, def_idx)
            text = definition.get("text", "")
            src_texts.append("" if text is None else text)
        key = f"{record.get('word', '').lower()}|{merged_sense.pos}|" + "|".join(sorted(src_texts))
        cluster_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        verdict = gamma.get(cluster_hash)
        if verdict and verdict.get("decision") == "merge" and verdict.get("merged_text"):
            base[i] = merged_sense._replace(text=verdict["merged_text"])
    return base
