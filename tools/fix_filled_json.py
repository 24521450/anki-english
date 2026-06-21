import json
from pathlib import Path

json_path = Path(r"C:\Users\admin\Downloads\missing_oxford_5000_cards_filled.json")

# Load filled cards
with json_path.open(encoding="utf-8") as f:
    cards = json.load(f)

# Corrections for the 7 mismatched cards
corrections = {
    "accused": {
        "pos": "noun",
        "def_before": "a person who is on trial for committing a crime",
        "gloss_after": "defendant",
        "separator": "none"
    },
    "diplomatic": {
        "pos": "adjective",
        "def_before": "connected with managing relations between countries; having or showing skill in dealing with people in difficult situations",
        "gloss_after": "tactful|international",
        "separator": "|"
    },
    "downtown": {
        "pos": "noun",
        "def_before": "the central part of a city, especially the business area",
        "gloss_after": "city centre",
        "separator": "none"
    },
    "mainland": {
        "pos": "noun",
        "def_before": "the main part of a country or continent, not including the islands around it",
        "gloss_after": "mainland",
        "separator": "none"
    },
    "nursing": {
        "pos": "adjective",
        "def_before": "relating to the job of caring for people who are sick or injured",
        "gloss_after": "caregiving",
        "separator": "none"
    },
    "solo": {
        "pos": "noun",
        "def_before": "a musical composition, or a passage, for a single voice or instrument; a performance by one person alone",
        "gloss_after": "solo performance",
        "separator": "none"
    },
    "worship": {
        "pos": "verb",
        "def_before": "to have or show a strong feeling of respect and admiration for God or a god; to love, respect, and admire someone or something very much",
        "gloss_after": "adore|revere",
        "separator": "|"
    }
}

updated_count = 0
for card in cards:
    w = card["word"].lower()
    if w in corrections:
        corr = corrections[w]
        card["pos"] = corr["pos"]
        card["def_before"] = corr["def_before"]
        card["gloss_after"] = corr["gloss_after"]
        card["separator"] = corr["separator"]
        card["rule_applied"] = "POS_DEF_MISMATCH_fixed"
        card["gloss_word_count"] = len(corr["gloss_after"].split("|"))
        updated_count += 1
        print(f"Updated card: {card['word']} -> POS: {card['pos']} | Def: {card['def_before'][:60]}...")

with json_path.open("w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

print(f"Successfully updated {updated_count} mismatched cards in JSON.")
