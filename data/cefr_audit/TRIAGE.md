# Triage Report — 818 Failing Cards → 3 Buckets

**Generated:** 2026-06-13
**Tool:** `tools/triage_failures.py`
**Scope:** 818 cards from `failures_only_*.csv` (cards where `card_status == "mismatch"`)

## Headline counts

| Bucket | Count | What it means |
| --- | --- | --- |
| **IN_PLACE** (cefr-mismatch + badge=no + per-def non-null) | **87** | Card has a sense with a real per-def CEFR, but the card's declared CEFR disagrees. **Card has content but the badge is wrong.** |
| **MISSING_CARD** (source sense with cefr=X has no (word, X) card in deck) | **806** | Source has a sense tagged with a specific CEFR (X != null) but no card in the deck claims that CEFR for the word. **Card needs to be created or its declared CEFR needs to change.** |
| **FALSE_POSITIVE** (word-not-in-source OR sense-text-not-in-source) | **283** | 92 word-not-in-source (inflected forms); 191 sense-text-not-in-source (Cambridge wording). **Lemmatize resolves 58/92 word cases.** |
| Total bucket entries (overlap) | 87 + 806 + 283 = 1,176 | Some rows may overlap across buckets; not summed. |

Note: 87 + 806 + 283 = 1,176 > 818 because a single failing card can have multiple bucket hits (e.g. a card with cefr-mismatch AND a missing sense AND inflected form).

## Bucket 1: IN_PLACE (87 cards)

**Definition:** sense text matched source, source `per-def` CEFR is non-null, but the card's declared CEFR differs from the per-def CEFR AND from `oxford_badge`. (When badge matches deck, it's classified as "cefr-mismatch but badge supports deck" — left in B2 territory.)

**Top 20 examples:**

| line | word | sense# | deck_cef | src_cef | src_badge | reason |
| --- | --- | --- | --- | --- | --- | --- |
| 64 | addictive | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 202 | affirm | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 2536 | agile | 1 | UNCLASSIFIED | C2 | | cefr-mismatch (deck=UNCLASSIFIED, source=C2 [per-def]) |
| 303 | anecdote | 1 | UNCLASSIFIED | B2 | | cefr-mismatch (deck=UNCLASSIFIED, source=B2 [per-def]) |
| 468 | aspiring | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 172 | burnout | 1 | UNCLASSIFIED | C2 | | cefr-mismatch (deck=UNCLASSIFIED, source=C2 [per-def]) |
| 2552 | cascade | 1 | UNCLASSIFIED | C2 | | cefr-mismatch (deck=UNCLASSIFIED, source=C2 [per-def]) |
| 524 | chapel | 1 | UNCLASSIFIED | C2 | | cefr-mismatch (deck=UNCLASSIFIED, source=C2 [per-def]) |
| 1584 | coherent | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 1585 | compatible | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 1587 | conform | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 2513 | congruence | 1 | UNCLASSIFIED | C2 | | cefr-mismatch (deck=UNCLASSIFIED, source=C2 [per-def]) |
| 223 | consolidation | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 2475 | contagious | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 2564 | contaminate | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 1589 | contradict | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 1590 | convene | 1 | UNCLASSIFIED | C2 | | cefr-mismatch (deck=UNCLASSIFIED, source=C2 [per-def]) |
| 2844 | craft | 1 | B2 | C2 | C1 | cefr-mismatch (deck=B2, source=C2 [per-def], source-badge=C1) |
| 2525 | deception | 1 | UNCLASSIFIED | C1 | | cefr-mismatch (deck=UNCLASSIFIED, source=C1 [per-def]) |
| 76 | dehydrated | 1 | UNCLASSIFIED | C2 | | cefr-mismatch (deck=UNCLASSIFIED, source=C2 [per-def]) |

**Pattern:** Most of these are cards with `declared_cefr=UNCLASSIFIED` where source has a real per-def CEFR (B2/C1/C2). **These are easy fixes: change the card's declared CEFR to match source per-def.**

## Bucket 2: MISSING_CARD (806 cases)

**Definition:** source has a sense with a specific CEFR (X != null), but no card in the deck (across all 3,020) claims that CEFR for the word. (I.e. the (word, X) pair is missing from the deck.)

**Top 20 examples:**

| word | missing_cefr | pos | def# | sense_text |
| --- | --- | --- | --- | --- |
| absorb | C1 | verb | 3 | to reduce the effect of a physical impact or movement |
| absorb | C1 | verb | 4 | to take something into the mind and learn or understand it |
| absorb | C1 | verb | 5 | to interest somebody very much so that they pay no attention |
| absorb | C1 | verb | 6 | to make something smaller become part of something larger |
| academy | C2 | noun | 3 | a secondary school in Scotland |
| academy | C2 | noun | 4 | a private school in the US |
| academy | C2 | noun | 5 | a school in England that is independent of local authority c... |
| accommodate | C1 | verb | 2 | to provide enough space for somebody/something |
| accommodate | C1 | verb | 3 | to consider something such as somebody's opinion or a fact a... |
| addictive | C1 | adjective | 1 | if a substance or activity is addictive, it makes people una... |
| advocate | C2 | noun | 2 | a person who defends somebody in court |
| affirm | C1 | verb | 3 | to confirm a legal decision |
| agile | C2 | adjective | 2 | able to think quickly and in an intelligent way |
| agile | C2 | adjective | 3 | used to describe a way of managing projects in which work is... |
| agile | C2 | adjective | 4 | used to describe a way of working in which the time and plac... |
| ally | C2 | noun | 3 | a person who offers their support to a particular group of p... |
| ancestor | C1 | noun | 2 | an animal that lived in the past that a modern animal has de... |
| ancestor | C1 | noun | 3 | an early form of a machine that later became more developed |
| anecdote | B2 | noun | 1 | a short, interesting or funny story about a real person or e... |
| angel | C2 | noun | 4 | a person who supports a business by investing money in it, e... |

**Pattern:** Many words have senses with C1/C2 CEFR that don't have a card claiming that level. `absorb` is the most prominent — 4 missing C1 verbs. `academy` missing 3 C2 noun senses. `agile` missing 3 C2 adjective senses.

## Bucket 3: FALSE_POSITIVE (283 cases)

| Sub-category | Count | Lemmatize resolves? |
| --- | --- | --- |
| word-not-in-source | 92 | **58 / 92 (63%)** lemmatize → in source |
| sense-text-not-in-source | 191 | (text not retried per decision) |

### word-not-in-source (92) — lemmatize results

**58 lemmatize to a base form that exists in `oxford_merged.jsonl`** — these are inflected forms (e.g. `resources` → `resource`).

**34 do NOT resolve** (compound words, proper nouns, or wordnet gaps).

**Top 20 with lemma results:**

| word | → lemma | in_source |
| --- | --- | --- |
| resources | resource | yes |
| countermeasures | countermeasure | yes |
| evolved | evolve | yes |
| lineages | lineage | yes |
| setbacks | setback | yes |
| concentrations | concentration | yes |
| regulations | regulation | yes |
| hyperfocus | hyperfocus | no |
| saturating | saturate | yes |
| soullessly | soullessly | no |
| invading | invade | yes |
| extrapolated | extrapolate | yes |
| eliminated | eliminate | yes |
| estimates | estimate | yes |
| harbored | harbor | yes (note: "harbored" → "harbor" with lemmatize, not "harbour") |
| harnessing | harness | yes |
| monitors | monitor | yes |
| unfiltered | unfiltered | no |
| carrying capacity | carrying capacity | no |
| blink of an eye | blink of an eye | no |

**Pattern:** Most "word-not-in-source" cases are inflected forms whose lemma is in source. WordNet handles plurals/past-tenses well; compounds (`carrying capacity`, `blink of an eye`) and some adverbs (`soullessly`) don't resolve.

### sense-text-not-in-source (191) — **NOT retried in this pass**

These are Cambridge wording diffs (per decision in `/grill-with-docs` — fuzzy threshold risks false-matches). These remain in the report as "needs review" for a separate audit pass against `cambridge_full.jsonl`.

## uncertain verification

**`uncertain` IS MISSING_CARD (B1): True**

**Details:**

Deck has 2 cards for `uncertain`:
- **line 8** (UNCLASSIFIED, 2 senses): "not confident | feeling doubt about sth; not sure" — fails audit (sense "feeling doubt" has source per-def=B1, deck declares UNCLASSIFIED).
- **line 2473** (UNCLASSIFIED, 3 senses): "likely to change... | not definite or decided | not confident" — passes audit (all 3 source senses have null per-def).

Source for `uncertain` (1 POS group, 4 senses):
- sense 1: "feeling doubt about something; not sure" **cefr=B1** ← MISSING in deck
- sense 2: "likely to change..." cefr=null
- sense 3: "not definite or decided" cefr=null
- sense 4: "not confident" cefr=null

**Across all 3,020 deck cards, no card claims `(uncertain, B1)`.** The sense text "feeling doubt about sth" IS on card line 8, but that card's declared CEFR is UNCLASSIFIED, not B1. So the audit's MISSING_CARD check correctly identifies B1 as missing.

**This means the deck-builder dropped the B1 CEFR for `uncertain`** when generating card line 8 — likely because the source's `oxford_badge` for `uncertain` is null and per-def had only 1 tagged sense (sense 1 with B1). The builder should have used sense-1's per-def CEFR (B1) for the card. The sense text made it into the card but the CEFR didn't propagate.

## Outputs (timestamped)

- `data/cefr_audit/bucket1_in_place_<TS>.csv` (87 rows)
- `data/cefr_audit/bucket2_missing_card_<TS>.csv` (806 rows)
- `data/cefr_audit/bucket3_false_positive_<TS>.csv` (283 rows)

## Suggested next steps (not in this phase)

1. **Bucket 1 (87 cards): auto-patch** — for cards with `declared_cefr=UNCLASSIFIED` and source per-def non-null, set declared to source per-def. One-shot fix in deck builder.
2. **Bucket 2 (806 cases): card-generation gap** — many words have senses with C1/C2 per-def that don't have corresponding `(word, CEFR)` cards. Most likely because the deck builder was emitting only 1 card per word (or per (word, badge-CEFR) pair), missing the per-def-CEFR split. Major data-build issue.
3. **Bucket 3 word (58 resolved): lemmatize in source-lookup** — re-run `check_deck_cefr.py` with a lemma-fallback in the source lookup. Will move 58 cards from mismatch → match without changing any data.
4. **Bucket 3 sense-text (191 unresolved): cross-validate against `cambridge_full.jsonl`** — separate audit pass.
