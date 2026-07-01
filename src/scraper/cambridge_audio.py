from __future__ import annotations
import re
from typing import Any, Optional
from lxml import html as lxml_html


_CARD_AUDIO_POS_OVERRIDES = {
    ("converse", "adjective_noun_verb"): "verb",
}

def normalize_word(word: str) -> str:
    """Strip parentheticals, trim whitespace, and lowercase the word."""
    return re.sub(r"\s*\(.*?\)\s*", "", word).strip().lower()

def normalize_pos(pos: str) -> str:
    """Normalize POS to a lowercase snake_case slug (e.g. 'noun, verb' -> 'noun_verb')."""
    return "_".join([p.strip().lower() for p in pos.replace(",", " ").replace("/", " ").split() if p.strip()])


def resolve_audio_pos(word: str, card_pos: str) -> str:
    """Return the Cambridge entry POS that supplies a card's pronunciation."""
    key = (normalize_word(word), normalize_pos(card_pos))
    return _CARD_AUDIO_POS_OVERRIDES.get(key, card_pos)

def parse_cambridge_entries(html_bytes: bytes) -> list[dict[str, Any]]:
    """Parse Cambridge HTML bytes into a list of entry dicts containing pos and audio paths."""
    root = lxml_html.fromstring(html_bytes)
    entries: list[dict[str, Any]] = []
    
    # Cambridge Dictionary structure has .entry-body__el for each homonym/entry block
    for entry_el in root.cssselect(".entry-body__el"):
        # Extract headword
        hw_el = entry_el.cssselect(".headword")
        headword = hw_el[0].text_content().strip() if hw_el else ""
        
        # Extract POS labels
        pos_els = entry_el.cssselect("span.pos.dpos")
        pos_list = [p.text_content().strip().lower() for p in pos_els]
        
        # Extract audio paths
        uk_audio_el = entry_el.cssselect("audio source[src*='uk_pron']")
        us_audio_el = entry_el.cssselect("audio source[src*='us_pron']")
        
        uk_audio = uk_audio_el[0].get("src") if uk_audio_el else None
        us_audio = us_audio_el[0].get("src") if us_audio_el else None
        
        entries.append({
            "headword": headword,
            "pos": pos_list,
            "uk_audio": uk_audio,
            "us_audio": us_audio
        })
        
    return entries

def select_entry(word: str, pos: str, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the correct entry matching the word and POS based on fallback/override rules."""
    if not entries:
        return None
        
    word_clean = normalize_word(word)
    pos_parts = [p.strip().lower() for p in pos.replace(",", " ").replace("/", " ").split() if p.strip()]
    target_pos = pos_parts[0] if pos_parts else ""
    
    # Locks/Overrides
    if word_clean == "counter" and target_pos == "noun":
        return entries[0] if len(entries) > 0 else None
    if word_clean == "designate" and target_pos == "adjective":
        return entries[1] if len(entries) > 1 else None
    if word_clean == "mainland" and target_pos == "noun":
        return entries[1] if len(entries) > 1 else None
    if word_clean == "sake" and target_pos == "noun":
        return entries[1] if len(entries) > 1 else None
        
    # Standard matching: first try to find entry with target POS and both UK & US audio
    for entry in entries:
        if target_pos in entry["pos"] and entry.get("uk_audio") and entry.get("us_audio"):
            return entry
            
    # Second try: find first entry containing the target POS even if audio is missing
    for entry in entries:
        if target_pos in entry["pos"]:
            return entry
            
    # Fallback to the first entry
    return entries[0]

def get_audio_filename(word: str, pos: str, accent: str) -> str:
    """Generate the POS-suffixed audio filename (handling sake override)."""
    word_clean = normalize_word(word)
    pos_slug = normalize_pos(pos)
    accent = accent.lower()
    
    if word_clean == "sake" and pos_slug == "noun":
        return f"cambridge_{accent}_sake_noun_2.mp3"
        
    return f"cambridge_{accent}_{word_clean}_{pos_slug}.mp3"
