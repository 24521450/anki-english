# ADR-0002: Multi-POS merge bug in Phase 5 build

- **Status**: Known bug, fix pending
- **Date**: 2026-06-11
- **Context**: Phase 5 full cache build of `data/oxford_full.jsonl`
- **Supersedes**: N/A
- **Superseded by**: N/A

## Context

The Phase 5 build used the Phase 3 parser (`src/scraper/oxford.py`) which extracts `pos_data` by iterating over the top-level `pos-g hclass="pos"` markers. For each top-level POS label, it copies **all** senses from the file into that POS section. This works for the common case where each Oxford file contains exactly one POS section. It breaks for words where Oxford returns multiple POS in a single file.

## Symptom

Word `sick` cached as `oxford_sick_1_(adj).html` contains all 3 POS sections (adjective, noun, verb) concatenated. The parser produces 3 duplicate `pos_data` entries, each with 16 definitions (same content).

```json
"word": "sick",
"pos": ["adjective", "noun", "verb"],
"pos_data": [
  {"pos": "adjective", "definitions": [16 defs]},
  {"pos": "noun", "definitions": [16 defs]},
  {"pos": "verb", "definitions": [16 defs]}
]
```

All three `pos_data` entries have identical content — the parser is grouping all senses under each top-level POS label instead of partitioning by the `<pos-g htag="span">` boundary in the file.

## Scale

3,886 Oxford words affected in Phase 5 build (out of 6,828 records = 57%).

## Root cause

The parser uses `root.cssselect("li.sense")` to grab all senses, then creates one `pos_data` entry per top-level POS label, copying the same full sense list to each. It does not respect the in-file `<pos-g htag="span">` boundary that separates POS sections within a single Oxford page.

## Fix (schema v2.1, not yet implemented)

The Oxford HTML structure for multi-POS files is:

```html
<ol class="senses_multiple">
  <li class="sense" ...>...</li>  <!-- sense 1 of adj -->
  <li class="sense" ...>...</li>  <!-- sense 2 of adj -->
</ol>
<pos-g hclass="pos" htag="span"><pos>adjective</pos></pos-g>  ← section break
<ol class="senses_multiple">
  <li class="sense" ...>...</li>  <!-- sense 1 of noun -->
</ol>
```

(Approximate — exact structure needs verification in Phase 6 implementation.)

**Algorithm for fix:**
1. Walk the file in document order
2. Detect `<pos-g htag="span">` boundary (or whatever structural marker Oxford uses)
3. For each section, collect only the senses that appear AFTER the previous pos-g boundary
4. Each section becomes one `pos_data` entry with the right `n` counter starting from 1

## Workaround in current build

The Phase 5 JSONL is buildable. Downstream consumers (Anki card builder) should:
- Dedupe by `(word, pos)` if they want one card per POS
- Or treat duplicate `pos_data` entries as a known data quality issue and ignore duplicates

## Decision

Document the bug, ship the JSONL as-is, plan Phase 6 to:
1. Verify exact Oxford HTML structure for multi-POS single-file cases
2. Implement boundary-based grouping in `src/scraper/oxford.py`
3. Add regression test for `sick` (and 2-3 other known multi-POS words)
4. Re-run full cache build, validate against schema, compare record counts

## Related

- Schema field `pos_data.description` no longer carries this note (per Phase 5 review)
- See `docs/adr/0003-oxford-register-tags-unverified.md` (TBD) for the related `.reg` selector issue
