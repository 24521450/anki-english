# Obsolete One-Shot Tools Archive

> [!WARNING]
> The scripts in this directory are unsupported, obsolete, one-shot migration tools used in previous phases of data cleanup.
> They are kept here for historical reference only and should not be run against the current production datasets, as they may cause data corruption or unexpected behavior.

This README is the canonical notice for `tools/archive/data_migrations/`.
Public tools, pipeline dependencies, test-imported modules, and tools referenced
by current source or project documentation must remain in `tools/` and use
`src.config.ProjectPaths`.

Archived files may keep their original names, including non-underscore names
from older phases. Location is authoritative here: anything in this directory is
historical unless it is explicitly restored to top-level `tools/` and re-tested.
