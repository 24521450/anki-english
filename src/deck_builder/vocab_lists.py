"""Parsers for Markdown vocabulary seed lists."""
from __future__ import annotations

import re
from pathlib import Path

from src.deck_builder.build_contracts import POS_NORM


def parse_vocab_list(path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| **"):
            continue
        match = re.match(r"\| \*\*([^*]+)\*\* \| ([^|]+) \| ([^|]+) \|", line)
        if not match:
            continue
        word = match.group(1).strip()
        word_clean = word.split(" (")[0].strip().lower()
        pos_str = match.group(2).strip()
        cefr = match.group(3).strip().upper()
        if word_clean == "a, an" or word_clean == "a":
            pos_list = ["indefinite article"]
        else:
            raw_parts = []
            for part in re.split(r",|/", pos_str):
                part = part.strip()
                if part:
                    raw_parts.append(part)
            pos_list = []
            for part in raw_parts:
                part_clean = part.rstrip(".")
                pos_list.append(POS_NORM.get(part_clean, part_clean))
        for pos in pos_list:
            out.add((word_clean, pos, cefr))
    return out
