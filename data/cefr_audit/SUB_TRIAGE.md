# Sub-Triage Report — Bucket 1 (IN_PLACE) + Bucket 2 (MISSING_CARD)

**Generated:** 2026-06-13
**Tool:** `tools/sub_triage.py`
**Scope:** 87 cards in Bucket 1 + 806 cases in Bucket 2
**Decision (grilled 2026-06-13):** Exact normalized match for 2A detection (no substring, no Jaccard).

## Summary

| Sub-bucket | Count | Risk to fix in-place | Constraint check |
| --- | --- | --- | --- |
| **1A** (homogeneous CEFR) | **85 cards** | Low — relabel card to uniform per-def CEFR | OK — in-place relabel only, no new card |
| **1B** (mixed CEFR) | **2 cards** | High — relabel would mis-tag one or more senses | **NOT in-place fixable** — needs split decision |
| **2A** (text exists in some card of word) | **600 cases** (452 unique words) | Medium — content present but on wrong card; "create new card for missing (word, CEFR) pair" = new card with content extracted from existing | **Out of scope** for "không thêm card" — same as 2B |
| **2B** (text truly absent) | **206 cases** (130 unique words) | High — content not in deck | **Out of scope** — needs new card with new content |

**Numbers add up:**
- Distinct cards in 1A + 1B = 87 (matches Bucket 1 count)
- 1B line 8 (`uncertain`) appears in BOTH 1B and 2A (overlap = 1)
- Total cases = 85 + 2 + 600 + 206 = 893, but distinct rows in any sub-bucket = 87 cards ∪ 806 (word, missing_cefr, sense) cases

## Bucket 1 sub-split (87 cards → 85A + 2B)

### 1A homogeneous — 85 cards SAFE TO RELABEL

All senses of these cards have the same non-null per-def CEFR. Setting `declared_cefr` to that value fixes the card without mis-tagging any sense.

| line | word | deck | per-def uniform | n_senses |
| --- | --- | --- | --- | --- |
| 62 | stimulant | UNCLASSIFIED | C2 | 1 |
| 64 | addictive | UNCLASSIFIED | C1 | 1 |
| 76 | dehydrated | UNCLASSIFIED | C2 | 1 |
| 96 | shoddy | UNCLASSIFIED | C2 | 1 |
| 122 | primitive | UNCLASSIFIED | C1 | 1 |
| 132 | embryo | UNCLASSIFIED | C1 | 1 |
| 148 | glitch | UNCLASSIFIED | C2 | 2 |
| 172 | burnout | UNCLASSIFIED | C2 | 1 |
| 180 | intimacy | UNCLASSIFIED | C2 | 1 |
| 202 | affirm | UNCLASSIFIED | C1 | 1 |

(Full list: `sub_1a_homogeneous_<TS>.csv` — 85 rows.)

### 1B mixed — 2 cards NEEDS SPLIT

| line | word | deck | per_defs | has_null |
| --- | --- | --- | --- | --- |
| 8 | uncertain | UNCLASSIFIED | NULL \| B1 | yes |
| 2487 | domesticated | UNCLASSIFIED | NULL | yes (single sense but null) |

**line 8 (uncertain)**: 2 senses, only sense 2 has B1, sense 1 (NULL) would be mis-tagged if relabeled to B1.
**line 2487 (domesticated)**: 1 sense but per-def is null. Classified as "mixed" because it has at least one null sense and zero non-null matching — actually `n_senses=1, n_non_null=0`. The "homogeneous" check requires `n_non_null == n_senses AND all same value`, so this fails. Relabel would also mis-tag. (This case is a 1A-equiv edge — single sense, no per-def — but the code can't safely infer CEFR from a single null. **Treat as 1B.**)

## Bucket 2 sub-split (806 cases → 600A + 206B)

### 2A mislabeled — 600 cases (452 unique words)

Text exists in some card of the word but on a card with different declared CEFR. To "fix", need to either:
- Split the existing card (extract this sense to a new card with correct CEFR), or
- Add a new card with same sense text but different CEFR label (duplicates content).

**Top 20:**

| word | missing | pos | found_in_line# (declared) | sense |
| --- | --- | --- | --- | --- |
| absorb | C1 | verb | 2797 (B2) | to reduce the effect of a physical impact or movement |
| absorb | C1 | verb | 2797 (B2) | to take something into the mind and learn or understand it |
| absorb | C1 | verb | 2797 (B2) | to interest somebody very much so that they pay no attention |
| academy | C2 | noun | 2799 (C1) | a secondary school in Scotland |
| academy | C2 | noun | 2799 (C1) | a private school in the US |
| academy | C2 | noun | 2799 (C1) | a school in England that is independent of local authority c... |
| accommodate | C1 | verb | 2800 (B2) | to provide enough space for somebody/something |
| addictive | C1 | adjective | 64 (UNCLASSIFIED) | if a substance or activity is addictive, it makes people una... |
| advocate | C2 | noun | 2563 (C1) | a person who defends somebody in court |
| affirm | C1 | verb | 202 (UNCLASSIFIED) | to confirm a legal decision |
| agile | C2 | adjective | 2536 (UNCLASSIFIED) | able to think quickly and in an intelligent way |
| ancestor | C1 | noun | 2802 (B2) | an animal that lived in the past that a modern animal has de... |
| ancestor | C1 | noun | 2802 (B2) | an early form of a machine that later became more developed |
| anecdote | B2 | noun | 303 (UNCLASSIFIED) | a short, interesting or funny story about a real person or e... |
| anxiety | C1 | noun | 2548 (B2) | a strong feeling of wanting to do something or of... |
| apology | C2 | noun | 2804 (B2) | information that you cannot go to a meeting or mus... |
| archive | C2 | noun | 2618 (C1) | an electronic record of the data on a computer sys... |
| array | C2 | noun | 2619 (C1) | a way of organizing and storing related data in a... |
| array | C2 | noun | 2619 (C1) | a set of numbers, signs or values arranged in rows... |
| ash | C2 | noun | 2620 (C1) | the powder that is left after a dead person's body... |

**Pattern observations:**
- `absorb` 3 C1 verbs live on a B2 card (line 2797) → deck only emitted B2 card, missing C1 card
- `academy` 3 C2 nouns live on C1 card (line 2799) → similar
- `addictive` C1 adjective lives on UNCLASSIFIED card (line 64) → same as 1A but for 1 sense
- `anxiety` C1 noun lives on B2 card (line 2548)
- `uncertain` B1 adjective lives on UNCLASSIFIED card (line 8) — confirmed in 1B too

**Decision needed:** for 2A, to truly add a `(word, missing_cefr)` card we'd need to either:
- **Split**: take this sense out of the existing card and put on new card with correct CEFR (loses user's review history on that sense, but the new card only has this sense, the existing card keeps the other senses with the original CEFR)
- **Add**: create a new card that duplicates the sense text + correct CEFR (preserves review history on existing card, but adds a duplicate-content card — may confuse Anki scheduling)

Both options create **new cards**, which is out of scope for "không thêm card". **2A is a content gap case, just like 2B**, only the content is already in the deck.

### 2B truly absent — 206 cases (130 unique words)

Source sense text does NOT appear in any card of the word in the deck. Truly missing content.

**Top 20:**

| word | missing | pos | sense |
| --- | --- | --- | --- |
| absorb | C1 | verb | to make something smaller become part of something |
| accommodate | C1 | verb | to consider something such as somebody's opinion o... |
| agile | C2 | adjective | used to describe a way of managing projects in whi... |
| agile | C2 | adjective | used to describe a way of working in which the tim... |
| ally | C2 | noun | a person who offers their support to a particular... |
| angel | C2 | noun | a person who supports a business by investing mone... |
| archive | C2 | verb | to put or store a document or other material in an... |
| archive | C2 | verb | to move information that is not often needed to a... |
| arm | A1 | noun | either of the two long parts that stick out from t... |
| arm | A1 | noun | the part of a piece of clothing that covers the ar... |
| aside | C2 | noun | something that a character in a play says to the a... |
| automatic | C2 | noun | a gun that can fire bullets continuously as long a... |
| automatic | C1 | noun | a vehicle with a system of gears that operates wit... |
| beam | C2 | verb | to have a big happy smile on your face |
| beam | C2 | verb | to send radio or television signals over long dist... |
| bench | C2 | verb | to remove a player from a team, or not include the... |
| bench | C2 | verb | to be attracted to somebody and want to see them o... |
| bias | C1 | noun | the fact that the results of research or an experi... |
| bias | C1 | verb | to unfairly influence somebody's opinions or decis... |
| bias | C1 | verb | to have an effect on the results of research or an... |

**Pattern observations:**
- Many "secondary" senses (e.g. `arm` A1 — body part, deck may have only the figurative arm)
- `automatic` 2 missing C2 noun senses
- `archive` 2 missing C2 verb senses (deck has C1 noun)
- `bias` 3 missing C1 senses
- 130 words × ~1.6 senses each = 206 missing (word, cefr, sense) tuples

## uncertain verification (revisited)

`uncertain` is at the intersection of multiple buckets:

| Sub-bucket | In it? | What it means |
| --- | --- | --- |
| 1A homogeneous | NO | line 8 has per_defs=[NULL, B1] — mixed, not homogeneous |
| 1B mixed | YES | line 8 has 2 senses with different per-def CEFRs |
| 2A mislabeled | YES | B1 sense text IS on a card (line 8), but that card is declared UNCLASSIFIED, not B1 |
| 2B truly absent | NO | text exists in deck |

**Confirmed: `uncertain` is a 1B+2A case.** Text present, but split decision needed (don't relabel whole card to B1 because sense 1 is NULL).

**Fix path (NOT in this phase):**
- Split line 8 into 2 cards:
  - Card 8a: "not confident" with declared=UNCLASSIFIED (no change for this sense)
  - Card 8b: "feeling doubt about something; not sure" with declared=B1 (new CEFR for this sense)
- This is a split (in-place reorganization of existing content) — still adds a new card in Anki terms, but the content was already being studied.

## What this means for action decisions

| Action | Count | Constraint check |
| --- | --- | --- |
| **Pure relabel** (1A) | **85 cards** | ✓ OK — just change `declared_cefr` on existing card. No new card, no content change. |
| **Split needed** (1B) | **2 cards** | New cards but content already exists. Borderline — depends on interpretation. |
| **Add new card** (2A) | **600 cases** | New cards with content extracted from existing cards. **Out of scope** for "không thêm card". |
| **Add new card with new content** (2B) | **206 cases** | Truly new content. **Out of scope**. |
| **Decision deferred** (1B+2A+2B) | **808** | Needs separate decision: expand deck or accept current subset as-is. |

**In-place fixable in scope: 85 cards (1A only).**

## Suggested next steps (not in this phase)

1. **1A patch (85 cards)**: auto-relabel `declared_cefr` from UNCLASSIFIED to source per-def CEFR. Run a one-shot script. **Safe**, **in-place**, no new cards.
2. **1B (2 cards: uncertain + domesticated)**: decide split vs accept-mismatch. `uncertain` is a clear split case (sense has explicit B1). `domesticated` is a single-sense null per-def — needs manual review.
3. **2A + 2B (806 cases)**: separate decision — these all require adding new cards. Out of scope for "không thêm card". Two paths:
   - (a) **Expand deck**: create new cards for these 806 cases. Pipeline change.
   - (b) **Accept subset**: document that current deck is a curated subset, and these 806 are "by design" not in the deck.

## Outputs (timestamped)

- `data/cefr_audit/sub_1a_homogeneous_<TS>.csv` (85 rows)
- `data/cefr_audit/sub_1b_mixed_<TS>.csv` (2 rows)
- `data/cefr_audit/sub_2a_mislabeled_<TS>.csv` (600 rows)
- `data/cefr_audit/sub_2b_truly_absent_<TS>.csv` (206 rows)
