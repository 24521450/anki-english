"""Audit database integrity check logic for def_before rows in deck_audit.jsonl."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

from src.deck_builder.build_notes import _parse_vocab_list

class DefBeforeIntegrityPaths(NamedTuple):
    deck_audit_jsonl: Path
    oxford_jsonl: Path
    manual_card_fills: Path
    anki_notes_txt: Path
    oxford_5000_md: Path

class DefBeforeIntegrityReport(NamedTuple):
    stats: dict[str, int]
    total_rows_read: int
    orphan_rows: list[tuple[int, dict]]
    unmatched_rows: list[tuple[int, dict]]
    ambiguous_rows: list[tuple[int, dict]]

    def has_errors(self) -> bool:
        return bool(
            self.orphan_rows
            or self.unmatched_rows
            or self.ambiguous_rows
            or sum(self.stats.values()) != self.total_rows_read
        )

def norm_def(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r'^\s*\[[^\]]+\]\s*', '', s)
    s = re.sub(r'\bsth\.?\b', 'something', s, flags=re.IGNORECASE)
    s = re.sub(r'\bsb\.?\b', 'somebody', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', ' ', s)
    s = s.rstrip('.').strip().lower()
    return s

def check_def_before_integrity(paths: DefBeforeIntegrityPaths) -> DefBeforeIntegrityReport:
    stats = {
        "oxford_exact": 0,
        "oxford_headword_cefr": 0,
        "oxford_5000_seed": 0,
        "oxford_idiom": 0,
        "manual_fill": 0,
        "orphan": 0,
        "unmatched": 0,
        "ambiguous": 0
    }
    orphan_rows = []
    unmatched_rows = []
    ambiguous_rows = []
    total_rows_read = 0

    for required_path in paths:
        if not required_path.exists():
            raise FileNotFoundError(f"Required integrity input does not exist: {required_path}")

    # 1. Parse existing cards from anki_notes.txt
    existing_cards = []
    for line in paths.anki_notes_txt.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 15:
            word = parts[3].strip().lower()
            pos = parts[4].strip().lower()
            cefr = parts[14].strip().upper()
            existing_cards.append((word, pos, cefr))

    # 2. Parse manual fills
    manual_fills = json.loads(paths.manual_card_fills.read_text(encoding="utf-8"))
    if not isinstance(manual_fills, list):
        raise ValueError("manual_card_fills must contain a JSON list")
    oxford_5000_keys = _parse_vocab_list(paths.oxford_5000_md)

    # 3. Load oxford source records and index idioms
    oxford_db = {}
    idioms_by_word = {}
    with paths.oxford_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            w = r.get("word", "").strip().lower()
            if w:
                oxford_db.setdefault(w, []).append(r)
            for idiom in r.get("idioms", []):
                phrase = idiom.get("phrase", "")
                phrase_clean = re.sub(r"\s*\(.*?\)\s*", "", phrase.lower()).strip()
                words_in_phrase = {wd for wd in re.findall(r'[a-z0-9]+', phrase_clean) if len(wd) > 2}
                for wd in words_in_phrase:
                    idioms_by_word.setdefault(wd, []).append((r, idiom))

    # Process each audit row
    with paths.deck_audit_jsonl.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            total_rows_read += 1
            row = json.loads(line)
            word = row.get("word", "").strip().lower()
            pos_str = row.get("pos", "").strip().lower()
            cefr = row.get("cefr", "").strip().upper()
            def_before = row.get("def_before", "")

            # A. Check orphan (exact word/CEFR and POS overlap)
            row_pos_parts = {p.strip() for p in pos_str.split(",") if p.strip()}
            has_matching_card = False
            for card_word, card_pos_str, card_cefr in existing_cards:
                if card_word == word and card_cefr == cefr:
                    card_pos_parts = {p.strip() for p in card_pos_str.split(",") if p.strip()}
                    if row_pos_parts & card_pos_parts:
                        has_matching_card = True
                        break

            if not has_matching_card:
                stats["orphan"] += 1
                orphan_rows.append((line_no, row))
                continue

            # Split def_before
            def_before_parts = re.split(r'\s*\|\s*|\s+;\s+|\n', def_before)
            def_before_parts_norm = [norm_def(p) for p in def_before_parts if p.strip()]

            # B. Prepare the explicit manual-fill fallback. Oxford evidence is
            # evaluated first so a manual row cannot hide a source mismatch.
            matching_manual_fills = []
            for mf in manual_fills:
                mf_word = mf.get("word", "").strip().lower()
                mf_pos = mf.get("pos", "").strip().lower()
                mf_cefr = mf.get("cefr", "").strip().upper()
                if (
                    mf_word == word
                    and mf_pos == pos_str
                    and mf_cefr == cefr
                    and mf.get("source") == "missing_oxford_5000"
                ):
                    mf_def_before = mf.get("def_before", "")
                    mf_def_before_parts = re.split(r'\s*\|\s*|\s+;\s+|\n', mf_def_before)
                    mf_def_before_parts_norm = [norm_def(p) for p in mf_def_before_parts if p.strip()]
                    if def_before_parts_norm == mf_def_before_parts_norm:
                        matching_manual_fills.append(mf)

            if len(matching_manual_fills) > 1:
                stats["ambiguous"] += 1
                ambiguous_rows.append((line_no, row))
                continue
            is_manual = len(matching_manual_fills) == 1

            if not def_before_parts_norm:
                stats["unmatched"] += 1
                unmatched_rows.append((line_no, row))
                continue

            # C. Classify segments
            word_clean = re.sub(r"\s*\(.*?\)\s*", "", word).strip()
            recs = oxford_db.get(word_clean, [])
            pos_parts = [p.strip() for p in pos_str.split(",") if p.strip()]
            seed_override_allowed = (
                row.get("cefr_source") == "oxford_5000_seed"
                and all((word_clean, pos, cefr) in oxford_5000_keys for pos in pos_parts)
            )

            # Look up candidate idioms once
            words_in_word = [wd for wd in re.findall(r'[a-z0-9]+', word_clean) if len(wd) > 2]
            candidate_idioms = []
            seen_idiom_phrases = set()
            for wd in words_in_word:
                for rec, idiom in idioms_by_word.get(wd, []):
                    phrase = idiom.get("phrase", "")
                    if phrase not in seen_idiom_phrases:
                        seen_idiom_phrases.add(phrase)
                        candidate_idioms.append((rec, idiom))

            segment_results = []
            is_row_ambiguous = False
            is_row_unmatched = False

            for p_norm in def_before_parts_norm:
                exact_senses = []
                headword_cefr_senses = []
                seed_override_senses = []
                idiom_senses = []

                # Check regular definition senses
                for rec in recs:
                    for pd in rec.get("pos_data", []):
                        pd_pos = pd.get("pos", "").strip().lower()
                        if pd_pos not in pos_parts:
                            continue
                        for d in pd.get("definitions", []):
                            d_cefr = (d.get("cefr") or "").strip().upper()
                            d_text_norm = norm_def(d.get("text", ""))
                            if d_text_norm == p_norm:
                                # Oxford Exact: matches CEFR exactly or both are unclassified
                                if d_cefr == cefr or (cefr == "UNCLASSIFIED" and not d_cefr):
                                    exact_senses.append(d)
                                # Oxford Headword CEFR: no sense CEFR, but headword badge matches cefr
                                elif not d_cefr and rec.get("oxford_badge") == cefr:
                                    headword_cefr_senses.append(d)
                                elif seed_override_allowed:
                                    seed_override_senses.append(d)

                # Check idioms (exact match of definition or matches phrases)
                for rec, idiom in candidate_idioms:
                    phrase = idiom.get("phrase", "")
                    text = idiom.get("text", "")
                    phrases = [p.strip().lower() for p in phrase.split("|")]
                    clean_phrases = []
                    for ph in phrases:
                        ph_clean = re.sub(r"\s*\(.*?\)\s*", "", ph).strip()
                        ph_no_sb_sth = re.sub(r'\bsomebody\b|\bsb\b|\bsomething\b|\bsth\b', '', ph_clean).strip()
                        ph_no_sb_sth = re.sub(r'\s+', ' ', ph_no_sb_sth)
                        clean_phrases.append(norm_def(ph_no_sb_sth))
                        clean_phrases.append(norm_def(ph_clean))
                        clean_phrases.append(norm_def(ph))

                    rec_word = rec.get("word", "").lower()
                    if norm_def(text) == p_norm or p_norm in clean_phrases:
                        if rec_word in word_clean or word_clean in rec_word or any(word_clean in cp for cp in clean_phrases):
                            idiom_senses.append(idiom)

                total_matches = (
                    len(exact_senses)
                    + len(headword_cefr_senses)
                    + len(seed_override_senses)
                    + len(idiom_senses)
                )
                if total_matches > 1:
                    is_row_ambiguous = True
                    break
                elif total_matches == 0:
                    is_row_unmatched = True
                    break
                else:
                    if exact_senses:
                        segment_results.append("exact")
                    elif headword_cefr_senses:
                        segment_results.append("headword_cefr")
                    elif seed_override_senses:
                        segment_results.append("oxford_5000_seed")
                    else:
                        segment_results.append("idiom")

            if is_row_ambiguous:
                stats["ambiguous"] += 1
                ambiguous_rows.append((line_no, row))
            elif is_row_unmatched:
                if is_manual:
                    stats["manual_fill"] += 1
                else:
                    stats["unmatched"] += 1
                    unmatched_rows.append((line_no, row))
            else:
                # Classify based on segment results
                if all(cat == "exact" for cat in segment_results):
                    stats["oxford_exact"] += 1
                elif all(cat == "idiom" for cat in segment_results):
                    stats["oxford_idiom"] += 1
                elif all(cat == "oxford_5000_seed" for cat in segment_results):
                    stats["oxford_5000_seed"] += 1
                elif all(cat in ("exact", "headword_cefr") for cat in segment_results) and any(cat == "headword_cefr" for cat in segment_results):
                    stats["oxford_headword_cefr"] += 1
                else:
                    # Mixed category or unexpected state
                    stats["ambiguous"] += 1
                    ambiguous_rows.append((line_no, row))

    return DefBeforeIntegrityReport(
        stats,
        total_rows_read,
        orphan_rows,
        unmatched_rows,
        ambiguous_rows,
    )
