"""CLI adapter for the registry-driven Anki notes build."""
from __future__ import annotations

import sys

from src.deck_builder.build_command import main


if __name__ == "__main__":
    sys.exit(main())
