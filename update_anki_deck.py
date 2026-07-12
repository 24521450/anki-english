"""Compatibility CLI adapter for Anki .apkg packaging."""
from __future__ import annotations

import sys

from src.deck_builder.package_command import (
    extract_audio_filename,
    generate_deterministic_id,
    main,
)

__all__ = ["extract_audio_filename", "generate_deterministic_id", "main"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
