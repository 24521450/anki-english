# `data/` artifact layout

This directory stores tracked datasets by lifecycle. Runtime code must obtain
canonical paths from `src.config.ProjectPaths` instead of constructing paths
or embedding machine-specific repository roots.

## Canonical artifacts

| Path | Role |
| --- | --- |
| `sources/oxford.jsonl` | Consolidated Oxford parser output and canonical builder source. Multi-file homonyms are merged; `_skip` records remain for auditability. |
| `sources/cambridge.jsonl` | Cambridge parser output using the shared dictionary-record schema. |
| `curated/deck_audit.jsonl` | Production gloss, example, and collocation overrides consumed during note building. This is production data, not review state. |
| `review/gamma_verdicts.json` | Cached gamma decisions used by sense simplification. |
| `review/manual_card_fills.json` | Reviewed manual fills that require preservation during rebuilds. |
| `review/non_oxford_non_c2_overrides.jsonl` | Review overrides for 381 non-Oxford / non-C2 cards. |
| `build/anki_notes.jsonl` | Generated structured notes consumed by the deck packager. |
| `build/anki_notes.txt` | Generated tab-separated Anki notes and the source used to preserve GUIDs across rebuilds. |

Supporting data remains in place:

- `schema/` contains Oxford and Cambridge JSON schemas.
- `oxford_labels.json` contains the Oxford labels taxonomy.
- `oxford_symbols.json` contains the Oxford dictionary-symbol taxonomy.
- `.cache_html/{oxford,cambridge}/` contains ignored fetcher caches.
- Retired audit snapshots and intermediate analysis artifacts are not tracked
  in `data/`. Runtime code must depend only on paths exposed through
  `ProjectPaths`. Local audit tools may recreate ignored output directories
  such as `cefr_audit/`, `simplify_diff/`, or `archive/`.

## Lifecycle

```text
data/.cache_html/{oxford,cambridge}
                 |
                 v
data/sources/{oxford,cambridge}.jsonl
                 |
                 +-- data/curated/deck_audit.jsonl
                 +-- data/review/*.json
                 |
                 v
data/build/anki_notes.{txt,jsonl}
                 |
                 v
ielts_deck.apkg
```

The Oxford source is consolidated because Oxford can have multiple cache files
for one word. Cambridge currently has one source record per cache page. Those
implementation details do not appear in filenames; the source field and schema
carry source-specific semantics.

## Commands

```bash
# Rebuild both source datasets from the local HTML caches.
python -m tools._run_full_cache

# Rebuild only Oxford and preserve the determinism contract.
python -m tools._run_full_cache --oxford-only

# Validate source JSONL files against their schemas.
python -m tools._validate_jsonl

# Compute Anki notes without writing files.
python -m tools.build_notes --dry-run

# Validate the production pipeline without writing outputs.
python -m src.pipeline --dry-run
```

## Contracts

- Rebuilding `sources/oxford.jsonl` from the same cache must be byte-identical.
- `build/anki_notes.txt` and `build/anki_notes.jsonl` represent the same notes
  and must preserve GUIDs.
- Source JSONL, curated overrides, and review inputs are tracked. HTML caches,
  audit/intermediate output directories, backups, logs, and `.apkg` packages
  are ignored.
- New maintained code must use `ProjectPaths`; old artifact names and absolute
  checkout paths are rejected by `tests/test_drift_guard.py`.

## Schema notes

Each source file contains one JSON object per line. Both share the same general
record shape: headword metadata plus `pos_data`, definitions, examples, IPA,
audio references, register tags, topics, idioms, and source files. Oxford-only
fields such as `oxford_lists`, `opal`, and topics remain empty on Cambridge
records.

`sensenum_local` preserves Oxford's numbering within each POS section. A null
value commonly identifies an idiom or phrasal-verb sense and is not by itself
an error.
