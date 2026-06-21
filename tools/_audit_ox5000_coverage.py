"""Oxford 5000 audit coverage check on current deck.

Verifies:
1. Each (word, pos, cefr) target in Oxford_5000.md has a card in deck.
2. Cards with Oxford_5000 tag actually match target (any POS).
3. Mixed-POS cards are reported separately (not as bugs).

Designed to be a trustworthy long-term checker:
- Per-triple coverage (NOT per-word-CEFR group): if Oxford_5000 has
  (word, noun, C1) AND (word, verb, C1) but deck only has noun,
  verb is reported as MISSING (not silently covered).
- ASCII-only output (no Unicode arrows), so PowerShell default cp1252
  does not crash with UnicodeEncodeError.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows so non-ASCII in any future
# output doesn't crash under PowerShell default cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
OX5000_PATH = ROOT / "vocab_list" / "Oxford" / "Oxford_5000.md"
TXT_PATH = ROOT / "English Academic Vocabulary.txt"

POS_NORM = {
    "n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb",
    "prep": "preposition", "pron": "pronoun", "det": "determiner",
    "conj": "conjunction", "num": "number", "modal": "modal",
    "predet": "predeterminer", "aux": "auxiliary", "exclam": "exclamation",
    "abbr": "abbreviation",
    "indefinite article": "indefinite article", "definite article": "definite article",
    "number": "number",
}


def parse_oxford_5000(path: Path) -> set[tuple[str, str, str]]:
    """Return (word_lower, pos_lower, cefr_upper) tuples from Oxford_5000.md."""
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| **"):
            continue
        m = re.match(r"\| \*\*([^*]+)\*\* \| ([^|]+) \| ([^|]+) \|", line)
        if not m:
            continue
        word = m.group(1).strip().split(" (")[0].strip().lower()
        pos_str = m.group(2).strip()
        cefr = m.group(3).strip().upper()
        for pp in re.split(r"[,/]", pos_str):
            pp = pp.strip().rstrip(".").lower()
            if not pp:
                continue
            pp_norm = POS_NORM.get(pp, pp)
            out.add((word, pp_norm, cefr))
    return out


def parse_deck(path: Path) -> list[dict]:
    """Return list of cards parsed from txt."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 17:
            continue
        guid, notetype, deck, word, pos, ipa, defn, ex, coll, wf, uk, us, src1, src2, cefr, idioms, tags = parts[:17]
        word_clean = word.split(" (")[0].strip().lower()
        # Split multi-POS like 'adjective, noun' → ['adjective', 'noun']
        pos_parts = [p.strip().lower() for p in pos.split(",") if p.strip()]
        out.append({
            "guid": guid,
            "word_orig": word,
            "word": word_clean,
            "pos_str": pos,
            "pos_parts": pos_parts,
            "cefr": cefr,
            "tags": tags,
            "definition": defn,
        })
    return out


def main():
    target = parse_oxford_5000(OX5000_PATH)
    cards = parse_deck(TXT_PATH)

    # Index cards by key for lookup
    card_by_key: dict[tuple[str, str, str], dict] = {}
    card_by_word_cefr: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cards:
        card_by_key[(c["word"], c["pos_str"].lower(), c["cefr"])] = c
        card_by_word_cefr[(c["word"], c["cefr"])].append(c)

    # 1. Coverage: for each (word, pos, cefr) target, is there a card?
    # Per-triple check (NOT per-word-CEFR group). This catches partial-coverage
    # bugs like Oxford_5000 has (word, noun, C1) AND (word, verb, C1) but deck
    # only has the noun -- verb is reported as missing, not silently covered.
    print("=" * 70)
    print("1. COVERAGE: Oxford 5000 target -> deck cards (per-triple)")
    print("=" * 70)

    missing_targets: list[tuple[str, str, str]] = []
    # Sort targets for stable, deterministic output.
    for w, p, c in sorted(target):
        # A target (word, pos, cefr) is covered if any card at (word, cefr)
        # lists this POS among its POSes (handles multi-POS cards like
        # 'adjective, noun' covering both 'adjective' and 'noun' targets).
        cards_at_key = card_by_word_cefr.get((w, c), [])
        if any(p in card["pos_parts"] for card in cards_at_key):
            continue
        missing_targets.append((w, p, c))

    print(f"Total Oxford 5000 targets (word,pos,cefr): {len(target)}")
    print(f"Missing in deck: {len(missing_targets)}")
    if missing_targets:
        print("  First 30 missing:")
        for w, p, c in missing_targets[:30]:
            print(f"    ({w}, {p}, {c})")

    # 2. diplomatic spot check (per plan)
    print()
    print("=" * 70)
    print("2. SPOT CHECK: diplomatic")
    print("=" * 70)
    diplomatic_noun = ("diplomatic", "noun", "C1") in target
    diplomatic_adj = ("diplomatic", "adjective", "C1") in target
    diplomatic_card = next((c for c in cards if c["word"] == "diplomatic"), None)
    print(f"  Oxford_5000 has (diplomatic, noun, C1)? {diplomatic_noun} (expect False)")
    print(f"  Oxford_5000 has (diplomatic, adjective, C1)? {diplomatic_adj} (expect True)")
    print(f"  Deck has diplomatic card? {diplomatic_card is not None}")
    if diplomatic_card:
        print(f"    word={diplomatic_card['word_orig']!r} pos={diplomatic_card['pos_str']!r} cefr={diplomatic_card['cefr']!r}")
        print(f"    tags={diplomatic_card['tags']!r}")

    # 3. Cards with Oxford_5000 tag but no target match
    print()
    print("=" * 70)
    print("3. TAG WITHOUT TARGET MATCH: cards with Oxford_5000 tag but no (word, pos, cefr) in target")
    print("=" * 70)
    tagged_no_match: list[dict] = []
    for c in cards:
        if "Oxford_5000" not in c["tags"]:
            continue
        # Check if any POS in card matches target
        w, cefr = c["word"], c["cefr"]
        any_match = any((w, p, cefr) in target for p in c["pos_parts"])
        if not any_match:
            tagged_no_match.append(c)

    print(f"Cards with Oxford_5000 tag: {sum(1 for c in cards if 'Oxford_5000' in c['tags'])}")
    print(f"Cards with tag but no target match (BUGS): {len(tagged_no_match)}")
    if tagged_no_match:
        for c in tagged_no_match[:30]:
            print(f"    {c['word_orig']} | {c['pos_str']} | {c['cefr']}")

    # 4. Mixed-POS cards (tagged Oxford_5000, multi-POS, some POS match, some don't)
    print()
    print("=" * 70)
    print("4. MIXED-POS CARDS: tagged Oxford_5000 + multi-POS + partial match (NOT bugs, follow-up)")
    print("=" * 70)
    mixed_pos: list[dict] = []
    for c in cards:
        if "Oxford_5000" not in c["tags"]:
            continue
        if len(c["pos_parts"]) <= 1:
            continue
        w, cefr = c["word"], c["cefr"]
        matching = [p for p in c["pos_parts"] if (w, p, cefr) in target]
        non_matching = [p for p in c["pos_parts"] if (w, p, cefr) not in target]
        if matching and non_matching:
            mixed_pos.append({**c, "_matching": matching, "_non_matching": non_matching})

    print(f"Mixed-POS cards: {len(mixed_pos)}")
    for c in mixed_pos[:20]:
        print(f"    {c['word_orig']} | {c['pos_str']} | {c['cefr']} -> match={c['_matching']} no_match={c['_non_matching']}")

    # 5. firm spot check
    print()
    print("=" * 70)
    print("5. SPOT CHECK: firm")
    print("=" * 70)
    firm_cards = [c for c in cards if c["word"] == "firm"]
    firm_target = sorted([(p, c) for w, p, c in target if w == "firm"])
    print(f"  firm Oxford_5000 targets: {firm_target}")
    for fc in firm_cards:
        has_tag = "Oxford_5000" in fc["tags"]
        print(f"    card: pos={fc['pos_str']!r} cefr={fc['cefr']!r} has_Oxford_5000_tag={has_tag}")


if __name__ == "__main__":
    main()
