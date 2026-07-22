"""Shared detection for text damaged by lossy Unicode conversion."""
from __future__ import annotations


def _looks_like_mojibake(value: str) -> bool:
    """Return whether UTF-8 bytes were decoded through a single-byte codec.

    A round-trip check is deliberately used instead of a broad non-ASCII
    heuristic: ordinary Vietnamese (and normal punctuation) must remain valid,
    while strings such as ``hoÃ n`` / ``â€™`` reliably repair to a different
    UTF-8 string through Latin-1 or Windows-1252.
    """
    for encoding in ("latin-1", "cp1252"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired != value and any(ord(char) >= 0x80 for char in value):
            return True
    return False


def has_suspected_lossy_unicode(value: object) -> bool:
    """Detect replacement, mojibake, and embedded lossy ``?`` characters.

    A terminal question mark remains valid; a question mark immediately before
    a letter is the high-confidence shape produced by the project's historical
    lossy export path.
    """
    if not isinstance(value, str):
        return False
    if "\ufffd" in value:
        return True
    if _looks_like_mojibake(value):
        return True
    return any(
        character == "?"
        and index + 1 < len(value)
        and value[index + 1].isalpha()
        for index, character in enumerate(value)
    )
