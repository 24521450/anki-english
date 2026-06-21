# CEFR Audit — Anki deck vs `data/oxford_merged.jsonl`

**Generated:** 2026-06-12
**Tool:** `tools/check_deck_cefr.py`
**Inputs:**
- Deck: `English Academic Vocabulary.txt` (Anki "Notes in Plain Text" export, 16 columns, 3,020 cards)
- Source: `data/oxford_merged.jsonl` (5,354 words, schema v2 with per-def `cefr` + word-level `oxford_badge`)

**Outputs (timestamped):**
- `data/cefr_audit/per_card_audit_<TIMESTAMP>.csv`
- `data/cefr_audit/per_sense_audit_<TIMESTAMP>.csv`

## Decision spec (grilled 2026-06-11)

| Question | Decision |
| --- | --- |
| Compare unit | Both: per-card summary + per-sense detail |
| Source of truth | `oxford_merged.jsonl` |
| Unmatched sense | Flag as `mismatch` (CEFR fail) |
| Source `def.cefr = null` | **Fall back to `oxford_badge` (word-level CEFR)**, then to `UNCLASSIFIED` if badge is also null. The badge is the word's authoritative CEFR — per-def being null doesn't mean "unclassified". |
| Multi-POS card | Strict in-order per POS group; flat-match if deck has no per-sense POS chip. |

## Headline numbers

| Metric | Value |
| --- | --- |
| Cards parsed | 3,020 |
| Senses (per-sense rows) | 5,638 |
| **Cards: full match** | **2,202 (72.9%)** |
| **Cards: any mismatch** | **818 (27.1%)** |
| Senses: match | 4,568 (81.0%) |
| Senses: mismatch | 1,070 (19.0%) |
| Card word-CEFR = source `oxford_badge` | 2,501 / 3,020 (82.8%) |
| Card word-CEFR ≠ source `oxford_badge` | 519 / 3,020 (17.2%) |

## Per-sense mismatch — categorized

Of the 1,070 mismatched senses, by CEFR origin:

| Bucket | Count | What it means |
| --- | --- | --- |
| **Genuine per-def disagreement** | **683 (63.8%)** | Source per-def has a real CEFR (e.g. C1), deck has a different one (e.g. B2). **Real CEFR disagreement** — investigate. |
| **Sense text not in Oxford source** | **233 (21.8%)** | Deck def text uses Cambridge wording (e.g. "sb"/"sth" abbreviations, register-tag prefix) that doesn't match Oxford's def text. **Not a CEFR error** — text-source diff. |
| **Word not in source** | **92 (8.6%)** | Deck has a word form not in `oxford_merged.jsonl` (e.g. `evolved`, `resources` — plural/inflected forms whose base is in source but not the inflected form). **Deck builder issue** — cards for inflected forms. |
| **No source CEFR available** | **1 (0.1%)** | Source per-def is null AND `oxford_badge` is null. Deck CEFR can't be cross-verified. |
| **Misc (multi-POS flat-matched, etc.)** | **61 (5.7%)** | |

## Source CEFR origin (where the source CEFR came from)

| Origin | Count | Description |
| --- | --- | --- |
| `per-def` | 3,423 | Source had a per-def CEFR — most authoritative |
| `oxford-badge` | 1,434 | Per-def null, fell back to word-level `oxford_badge` |
| `none` | 417 | Neither per-def nor badge — source has no CEFR signal |
| (empty) | 364 | Not matched (word or sense text not found in source) |

## Top card-level failure patterns

| Count | Pattern | Interpretation |
| --- | --- | --- |
| 141 | `cefr-mismatch (deck=B2, source=C1 [per-def], source-badge=B2)` | Per-def C1 disagrees with deck B2. **Word-badge supports deck.** Oxford's per-def may be wrong, or deck used Cambridge CEFR for this word. |
| 130 | `cefr-mismatch (deck=C1, source=C2 [per-def], source-badge=C1)` | Same pattern, badge supports deck. |
| 75  | `1/3 senses failed: sense-text-not-in-source` | Multi-sense card where one sense uses Cambridge wording. |
| 62  | `word-not-in-source` | Inflected/plural form in deck; headword is in source. |
| 57  | `2/2 senses failed: cefr-mismatch (deck=B2, source=C1 [per-def], source-badge=B2)` | Both senses disagree. |
| 51  | `cefr-mismatch (deck=B2, source=C2 [per-def], source-badge=B2)` | |
| 47  | `no-per-sense-pos-in-deck; flat-matched` | Multi-POS card; senses couldn't be split per POS. **EAVM back template doesn't emit per-sense POS chips.** |
| 42  | `1/2 senses failed: sense-text-not-in-source` | |

## POS mismatches (real data bug)

Check `per_sense_audit.csv` for rows where `source_pos` is set but the sense text came from a different POS group than the deck's `pos_list` (rare, since flat-match hides most cases). Manual review of 24 known cases from previous run.

## CEFR level distribution (deck vs source)

| CEFR | Deck cards | Source `oxford_badge` |
| --- | --- | --- |
| A1 | 1 | 3 |
| A2 | 8 | 10 |
| B1 | 17 | 19 |
| B2 | 1,044 | 1,021 |
| C1 | 1,489 | 1,490 |
| UNCLASSIFIED | 461 | — (badge field is null) |

The 461 UNCLASSIFIED deck cards have `UNCLASSIFIED` in the topbar — words where neither source has a CEFR. Many of these are inflected forms (resources, evolved, etc.) or low-frequency vocab.

## How to read the CSVs

1. `per_card_audit_<TS>.csv` — one row per card. Filter `card_status == mismatch` for the 818 cards to review.
2. `card_reason` tells you why it failed. Pattern:
   - `cefr-mismatch (deck=X, source=Y [per-def], source-badge=Z)`:
     - If `Z == X`: **word-badge supports deck; per-def is the outlier.** Probably OK; deck used Cambridge CEFR.
     - If `Y == X` and `Z != X`: **deck matches source per-def; badge is the outlier.** Investigate.
     - If both `Y` and `Z` `!= X` and both agree: **deck is wrong.**
3. `per_sense_audit_<TS>.csv` — one row per `(word, sense)`. Filter `status == mismatch` for the 1,070 failing senses. Check `match_kind` (exact-norm / fuzzy-jaccard / none) to see if it's a true text diff.

## Suggested next steps

- **Cross-validate against `cambridge_full.jsonl`** — 233 senses have text that doesn't match Oxford; a Cambridge pass would resolve most of these.
- **Fix the 92 inflected-form cards** in the deck builder — cards for `evolved`, `resources`, `concentrations`, etc. should either lemmatize to the headword or be added to the source as separate records.
- **Investigate the 683 per-def disagreements** — these are the most likely real CEFR errors. Spot-check 10-20 to see if deck or source is wrong.
- **Add per-sense POS chips to EAVM back template** — 47 multi-POS cards can't be safely split per POS, so the audit flat-matches them.
- **Re-export Anki deck** when the above is done and re-run audit to confirm match rate improves.

## Audit run history

| Date | Match rate (cards) | Notes |
| --- | --- | --- |
| 2026-06-11 12:39 | 12.9% (390/3019) | First run; treated per-def null as UNCLASSIFIED. |
| 2026-06-11 13:00 | 30.9% (933/3019) | Added text normalization (sth/sb, register-tag strip, fuzzy jaccard). |
| 2026-06-12 20:08 | **72.9% (2202/3020)** | **Fixed CEFR resolution (badge fallback); switched to clean 16-col Anki export.** |
