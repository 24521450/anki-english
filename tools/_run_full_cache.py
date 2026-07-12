"""CLI adapter for the deterministic Oxford/Cambridge cache rebuild."""
from __future__ import annotations

import sys

from src.scraper.rebuild_command import (
    main,
    merge_oxford_records,
    merge_oxford_records_from_file,
    run_source,
)

__all__ = [
    "main",
    "merge_oxford_records",
    "merge_oxford_records_from_file",
    "run_source",
]


if __name__ == "__main__":
    sys.exit(main())
