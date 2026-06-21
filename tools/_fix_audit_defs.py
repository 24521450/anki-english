#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Rebuild `def_before` in audit_full_deck.jsonl from oxford_merged.jsonl.

For each card:
  - Normalize and lemmatize word, check spelling mappings.
  - If match in oxford_db: collect Oxford defs using simplify_record, POS/CEFR match.
  - If no match in headwords, search idioms.
  - Deduplicate, cap to top 3 definitions, join with "|", and update def_before.
  - If no match found at all: keep original, status = kept_not_found or kept_no_match.

Outputs:
  - <audit_full_deck>_fixed.jsonl (same dir as input)
  - <scratchpad>/fix_log.json (only cards with status=rebuilt or kept_no_match)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to sys.path to allow importing src.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_oxford_db(path: Path) -> tuple[dict[str, list[dict]], dict[str, list[tuple[dict, dict]]]]:
    """word -> list of Oxford records, and phrase_clean -> list of (record, idiom_dict)."""
    db: dict[str, list[dict]] = defaultdict(list)
    idioms_db: dict[str, list[tuple[dict, dict]]] = defaultdict(list)

    def clean_word(word):
        return re.sub(r"\s*\(.*?\)\s*", "", word.lower()).strip()

    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"[warn] oxford line {line_no}: invalid JSON: {exc}", file=sys.stderr)
                continue
            w = rec.get("word")
            if not w:
                continue
            db[w.lower()].append(rec)

            # Index idioms
            for idiom in rec.get("idioms") or []:
                phrase = idiom.get("phrase") or ""
                phrase_clean = clean_word(phrase)
                if phrase_clean:
                    idioms_db[phrase_clean].append((rec, idiom))

    return db, idioms_db


def split_pos(card_pos: str | None) -> list[str]:
    if not card_pos:
        return []
    return [p.strip() for p in card_pos.split(",") if p.strip()]


def get_word_candidates(word: str) -> list[str]:
    # Clean the word first (strip parentheticals)
    word_clean = re.sub(r"\s*\(.*?\)\s*", "", word.lower()).strip()
    
    cands = [word_clean]
    
    # 1. Suffix rules
    suffixes = [
        ("ies", "y"), ("ied", "y"), ("ying", "y"),
        ("ed", ""), ("ing", ""), ("ly", ""),
        ("es", ""), ("s", ""), ("er", ""), ("est", ""),
        ("al", ""),
    ]
    for suf, repl in suffixes:
        if word_clean.endswith(suf) and len(word_clean) > len(suf) + 2:
            base = word_clean[:-len(suf)]
            cands.append(base + repl)
            
            # Double consonant check (e.g. shunned -> shun)
            if len(base) > 1 and base[-1] == base[-2] and base[-1] in "bdfglmnprstz":
                cands.append(base[:-1] + repl)
                
            # If stripped ed or ing, try adding e (e.g. accused -> accuse)
            if suf in ("ed", "ing"):
                cands.append(base + "e")
                
    # 2. Spelling & Hyphenation
    if word_clean.endswith("or") and len(word_clean) > 3:
        cands.append(word_clean[:-2] + "our")
    if word_clean.endswith("our") and len(word_clean) > 4:
        cands.append(word_clean[:-3] + "or")
        
    if "wellbeing" in word_clean:
        cands.append("well-being")
    if "byproduct" in word_clean:
        cands.append("by-product")
    if "shortsighted" in word_clean:
        cands.append("short-sighted")
        
    # 3. Irregulars
    irregular = {
        "criteria": "criterion",
        "vertebrae": "vertebra",
        "ligaments": "ligament"
    }
    if word_clean in irregular:
        cands.append(irregular[word_clean])
        
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def find_idioms_for_word(word_clean: str, idioms_db: dict) -> list[tuple[dict, dict]]:
    # 1. Try exact match
    if word_clean in idioms_db:
        return idioms_db[word_clean]
        
    # 2. Try substring match (e.g. 'blink of an eye' in 'in the blink of an eye')
    for phrase_clean, records in idioms_db.items():
        if word_clean in phrase_clean or phrase_clean in word_clean:
            return records
            
    return []


def collect_idiom_defs(idioms_found: list[tuple[dict, dict]], card_cefr: str) -> list[str]:
    out = []
    seen = set()
    for _, idiom in idioms_found:
        idiom_cefr = idiom.get("cefr") or "UNCLASSIFIED"
        if idiom_cefr == card_cefr:
            text = idiom.get("text")
            if text and text.strip():
                t = text.strip()
                if t not in seen:
                    seen.add(t)
                    out.append(t)
    return out


def collect_defs_for_card(oxford_records: list[dict], card_pos_list: list[str], card_cefr: str) -> list[str]:
    from src.deck_builder.simplify_senses import simplify_record
    if not card_pos_list or not card_cefr:
        return []

    all_senses = []
    for pos in card_pos_list:
        for rec in oxford_records:
            try:
                simplified = simplify_record(rec)
            except Exception as e:
                print(f"[warn] simplify error: {e}", file=sys.stderr)
                continue
            for ms in simplified:
                if ms.pos != pos:
                    continue
                ms_cefr = ms.cefr or "UNCLASSIFIED"
                if ms_cefr != card_cefr:
                    continue
                all_senses.append(ms)

    # Deduplicate identical texts and cap to 3
    seen_texts = set()
    out = []
    for s in all_senses:
        t = (s.text or "").strip()
        if t and t not in seen_texts:
            seen_texts.add(t)
            out.append(t)
            if len(out) >= 3:
                break
    return out


def process_cards(oxford_db: dict[str, list[dict]], idioms_db: dict, cards: list[dict]) -> tuple[list[dict], list[dict], dict]:
    fixed_cards: list[dict] = []
    log_entries: list[dict] = []
    counts = defaultdict(int)

    for card in cards:
        word = card.get("word") or ""
        card_cefr = card.get("cefr")
        old_def = card.get("def_before")
        card_pos_list = split_pos(card.get("pos"))

        new_card = dict(card)  # shallow copy

        # Generate candidates for word matching
        cands = get_word_candidates(word)
        
        # 1. Try matching headwords in oxford_db
        matched_records = []
        matched_word = None
        for cand in cands:
            if cand in oxford_db:
                matched_records = oxford_db[cand]
                matched_word = cand
                break
                
        # 2. Try matching idioms if headword not found
        idioms_found = []
        if not matched_records:
            word_clean = cands[0]  # first candidate is always cleaned word
            idioms_found = find_idioms_for_word(word_clean, idioms_db)
            
        # Collect definitions
        defs = []
        if matched_records:
            defs = collect_defs_for_card(matched_records, card_pos_list, card_cefr)
        elif idioms_found:
            defs = collect_idiom_defs(idioms_found, card_cefr)
            
        if not defs:
            if not matched_records and not idioms_found:
                new_card["fix_status"] = "kept_not_found"
                counts["kept_not_found"] += 1
            else:
                new_card["fix_status"] = "kept_no_match"
                counts["kept_no_match"] += 1
                
            log_entries.append({
                "word": word,
                "pos": card.get("pos"),
                "cefr": card_cefr,
                "def_before_old": old_def,
                "def_before_new": None,
                "fix_status": new_card["fix_status"],
                "reason": "no oxford def matched card (pos, cefr)",
            })
            fixed_cards.append(new_card)
            continue

        # Rebuilt definition found!
        new_def = "|".join(defs)
        new_card["def_before"] = new_def
        new_card["fix_status"] = "rebuilt"
        counts["rebuilt"] += 1
        
        log_entries.append({
            "word": word,
            "pos": card.get("pos"),
            "cefr": card_cefr,
            "def_before_old": old_def,
            "def_before_new": new_def,
            "fix_status": "rebuilt",
            "def_count": len(defs),
        })
        fixed_cards.append(new_card)

    return fixed_cards, log_entries, counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--audit",
        default=r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl",
        help="Path to audit_full_deck.jsonl",
    )
    ap.add_argument(
        "--oxford",
        default=r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl",
        help="Path to oxford_merged.jsonl",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Output jsonl path (default: <audit>_fixed.jsonl)",
    )
    ap.add_argument(
        "--log",
        default=r"C:\Users\admin\.mavis\scratchpads\mvs_44fdd6d07882432093d3deee72f8015a\fix_log.json",
        help="Output log path",
    )
    args = ap.parse_args()

    audit_path = Path(args.audit)
    oxford_path = Path(args.oxford)
    out_path = Path(args.out) if args.out else audit_path.with_name(audit_path.stem + "_fixed.jsonl")
    log_path = Path(args.log)

    print(f"[load] oxford: {oxford_path}")
    oxford_db, idioms_db = load_oxford_db(oxford_path)
    print(f"[load] oxford: {sum(len(v) for v in oxford_db.values())} records, {len(oxford_db)} unique words")
    print(f"[load] idioms: {len(idioms_db)} unique phrases")

    print(f"[load] audit: {audit_path}")
    with audit_path.open("r", encoding="utf-8") as f:
        cards = [json.loads(line) for line in f if line.strip()]
    print(f"[load] audit: {len(cards)} cards")

    fixed, log_entries, counts = process_cards(oxford_db, idioms_db, cards)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for c in fixed:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"[write] {out_path}: {len(fixed)} cards")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        json.dump(log_entries, f, ensure_ascii=False, indent=2)
    print(f"[write] {log_path}: {len(log_entries)} entries")

    print("\n[summary] counts:")
    for k in sorted(counts.keys()):
        print(f"  {k}: {counts[k]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())