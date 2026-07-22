"""Shared card-level policy for main Examples and POS values."""
from __future__ import annotations

import re
from collections.abc import Iterable


_DOUBLE_BREAK_RE = re.compile(
    r"(?:<br\s*/?>\s*){2}",
    flags=re.IGNORECASE,
)


def main_example_pos_shortfall(
    pos: object,
    examples: Iterable[object],
) -> tuple[int, int] | None:
    """Return ``(actual, required)`` when main Examples are below card POS."""
    distinct_pos = {
        part.strip()
        for part in str(pos or "").split(",")
        if part.strip()
    }
    actual = sum(
        1 for example in examples
        if isinstance(example, str) and example.strip()
    )
    required = len(distinct_pos)
    if actual < required:
        return actual, required
    return None


def rendered_main_examples(value: object) -> list[str]:
    """Parse the rendered Example field without considering Idiom Examples."""
    if not isinstance(value, str):
        return []
    return [
        example.strip()
        for sense_cell in value.split("|")
        for example in _DOUBLE_BREAK_RE.split(sense_cell)
        if example.strip()
    ]
