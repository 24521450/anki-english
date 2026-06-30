import json
import re
import random
import string
from pathlib import Path

from src.config import ProjectPaths

paths = ProjectPaths()
ROOT = paths.root
FILLED_JSON_PATH = paths.manual_card_fills
DECK_FILE = paths.anki_notes_txt
ANKI_NOTES_JSONL = paths.anki_notes_jsonl
AUDIT_FILE = paths.deck_audit_jsonl
OXFORD_MERGED = paths.oxford_jsonl
CAMBRIDGE_FULL = paths.cambridge_jsonl

def new_guid(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits + '!#$%&()*+,-./:;<=>?@[]^_`{|}~'
    return "".join(random.choices(alphabet, k=length))

# 1. Load dictionaries for IPA & Example extraction
oxford_db = {}
with OXFORD_MERGED.open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            r = json.loads(line)
            w = r.get("word", "").lower()
            if w:
                oxford_db.setdefault(w, []).append(r)

cambridge_db = {}
with CAMBRIDGE_FULL.open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            r = json.loads(line)
            w = (r.get("word") or "").lower()
            if w:
                cambridge_db.setdefault(w, []).append(r)

# Helpers to find IPA & Examples
def find_ipa_and_examples(word, pos):
    # Try oxford first
    recs = oxford_db.get(word.lower(), [])
    for rec in recs:
        for pd in rec.get("pos_data", []):
            if pd.get("pos") == pos or (pos == "noun" and pd.get("pos") in ("noun", "noun plural")) or (pos == "verb" and pd.get("pos") in ("verb", "phrasal verb")):
                ipa = ""
                examples = []
                for d in pd.get("definitions", []):
                    if d.get("ipa") and not ipa:
                        ipa = d.get("ipa").strip()
                    for ex in d.get("examples", []):
                        ex_text = ex.get("text", "").strip()
                        if ex_text and ex_text not in examples:
                            examples.append(ex_text)
                if ipa or examples:
                    return ipa, examples
    
    # Try cambridge
    recs = cambridge_db.get(word.lower(), [])
    if not recs and word.lower() == "accused":
        recs = cambridge_db.get("the accused", [])
        
    for rec in recs:
        for pd in rec.get("pos_data", []):
            if pd.get("pos") == pos or (pos == "noun" and pd.get("pos") in ("noun", "noun plural")) or (pos == "verb" and pd.get("pos") in ("verb", "phrasal verb")):
                ipa = ""
                examples = []
                for d in pd.get("definitions", []):
                    if d.get("ipa") and not ipa:
                        ipa = d.get("ipa").strip()
                    for ex in d.get("examples", []):
                        ex_text = ex.get("text", "").strip()
                        if ex_text and ex_text not in examples:
                            examples.append(ex_text)
                if ipa or examples:
                    return ipa, examples
                    
    return "", []

# 2. Load filled missing cards
with FILLED_JSON_PATH.open(encoding="utf-8") as f:
    missing_cards = json.load(f)

print(f"Loaded {len(missing_cards)} filled cards from JSON.")

# Generate full cards
new_tsv_rows = []
new_jsonl_rows = []
new_audit_rows = []

# To ensure GUID uniqueness, load existing GUIDs
existing_guids = set()
if DECK_FILE.exists():
    for line in DECK_FILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#") and line.strip():
            existing_guids.add(line.split("\t")[0])

for card in missing_cards:
    word = card["word"]
    pos = card["pos"]
    cefr = card["cefr"]
    gloss = card["gloss_after"]
    def_before = card["def_before"]
    
    # Get GUID
    guid = new_guid()
    while guid in existing_guids:
        guid = new_guid()
    existing_guids.add(guid)
    
    # Extract IPA and examples
    ipa, examples = find_ipa_and_examples(word, pos)
    # Cap to top example per sense or top 2 examples
    ex_str = " | ".join(examples[:2])
    
    # Audio tags
    uk_audio = f"[sound:cambridge_uk_{word.lower()}.mp3]"
    us_audio = f"[sound:cambridge_us_{word.lower()}.mp3]"
    
    # Tags
    tags = f"Audio::Cambridge CEFR::{cefr} CEFR::oxford Oxford_5000 Source::Oxford"
    
    # 17-col TSV card
    # cols: guid, notetype, deck, word, pos, ipa, definition, example, collocations, wordfamily, uk_audio, us_audio, source1, source2, cefr, idioms, tags
    row_parts = [
        guid,
        "English Academic Vocabulary Model",
        "English Academic Vocabulary::Oxford",
        word,
        pos,
        ipa,
        gloss,
        ex_str,
        "",  # collocations (empty)
        "",  # wordfamily (empty)
        uk_audio,
        us_audio,
        "Oxford",
        "Oxford",
        cefr,
        "",  # idioms (empty)
        tags
    ]
    new_tsv_rows.append("\t".join(row_parts))
    
    # JSONL card (corresponds to anki_notes.jsonl structure)
    new_jsonl_rows.append({
        "guid": guid,
        "notetype": "English Academic Vocabulary Model",
        "deck": "English Academic Vocabulary::Oxford",
        "word": word,
        "pos": pos,
        "ipa": ipa,
        "definition": gloss,
        "example": ex_str,
        "collocations": "",
        "wordfamily": "",
        "uk_audio": uk_audio,
        "us_audio": us_audio,
        "source1": "Oxford",
        "source2": "Oxford",
        "cefr": cefr,
        "idioms": "",
        "tags": tags
    })
    
    # Audit row
    new_audit_rows.append(card)

# Write to anki_notes.txt (append to end)
if DECK_FILE.exists():
    deck_content = DECK_FILE.read_text(encoding="utf-8")
    # Make sure it ends with newline
    if not deck_content.endswith("\n"):
        deck_content += "\n"
    deck_content += "\n".join(new_tsv_rows) + "\n"
    DECK_FILE.write_text(deck_content, encoding="utf-8")
    print(f"Appended {len(new_tsv_rows)} rows to {DECK_FILE.name}")

# Write to anki_notes.jsonl (append to end)
if ANKI_NOTES_JSONL.exists():
    with ANKI_NOTES_JSONL.open("a", encoding="utf-8") as f:
        for r in new_jsonl_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Appended {len(new_jsonl_rows)} records to {ANKI_NOTES_JSONL.name}")

# Write to deck_audit.jsonl (append to end)
if AUDIT_FILE.exists():
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        for r in new_audit_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Appended {len(new_audit_rows)} records to {AUDIT_FILE.name}")

print("Integration complete!")
