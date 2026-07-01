from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import requests
from pathlib import Path

# Setup paths
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from src.config import ProjectPaths
from src.scraper.cambridge_audio import (
    normalize_word,
    normalize_pos,
    parse_cambridge_entries,
    select_entry,
    get_audio_filename,
)

paths = ProjectPaths(Path(PROJECT_ROOT))

COLLISION_WORDS = [
    "acid", "alien", "bat", "craft", "deposit", "designate", "dynamic", "exit",
    "extract", "firm", "fit", "harbour", "hook", "incline", "intellectual", "labor",
    "mainland", "migrate", "navigate", "pop", "principal", "sanctuary", "spare",
    "tackle", "terminal", "total", "trace", "trigger"
]

SCOPED_WORDS = set(COLLISION_WORDS) | {"curate", "sake"}

PREFLIGHT_CARD_COUNT = 60  # 28 collision groups (58 cards) + curate (1) + sake (1)

CAMBRIDGE_BASE_URL = "https://dictionary.cambridge.org"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def load_word_to_source_file() -> dict[str, str]:
    """Load word to source file mapping from cambridge.jsonl."""
    word_to_file = {}
    jsonl_path = paths.cambridge_jsonl
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} does not exist. Run full cache parser first.")
        sys.exit(1)
        
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            w = rec.get("word")
            sf = rec.get("source_files")
            if w and sf:
                word_to_file[w.lower()] = sf[0]
                
    return word_to_file

def is_valid_mp3(content: bytes) -> bool:
    """Check if content has a valid MP3/ID3 header and minimum size."""
    if len(content) < 1000:
        return False
    # MP3 files usually start with b'ID3' or b'\xff\xfb' or b'\xff\xf3' or b'\xff\xf2'
    if content.startswith(b"ID3"):
        return True
    if content.startswith(b"\xff\xfb") or content.startswith(b"\xff\xf3") or content.startswith(b"\xff\xf2"):
        return True
    return False

def download_audio(url: str, dest_path: Path, apply: bool) -> bool:
    """Download audio to a temp file, validate, and replace atomically with retries."""
    absolute_url = url if url.startswith("http") else CAMBRIDGE_BASE_URL + url
    
    if not apply:
        print(f"  [DRY-RUN] Would download {absolute_url} to {dest_path.name}")
        return True
        
    if dest_path.exists():
        with open(dest_path, "rb") as f:
            content = f.read()
        if is_valid_mp3(content):
            print(f"  File {dest_path.name} already exists and is valid. Skipping download.")
            return True
        
    import time
    max_retries = 5
    backoff = 3
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(absolute_url, headers={"User-Agent": USER_AGENT}, timeout=30)
            if resp.status_code == 429:
                print(f"  Received HTTP 429 (Rate Limit) for {absolute_url}. Retrying in {backoff}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(backoff)
                backoff *= 2
                continue
                
            if resp.status_code != 200:
                print(f"  Error: HTTP {resp.status_code} for {absolute_url}")
                return False
                
            content = resp.content
            if not is_valid_mp3(content):
                print(f"  Error: Invalid MP3 file (size={len(content)} bytes) from {absolute_url}")
                return False
                
            # Write to temp file in the same directory, then rename atomically
            dest_dir = dest_path.parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            fd, temp_path = tempfile.mkstemp(dir=dest_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                os.replace(temp_path, dest_path)
                print(f"  Successfully downloaded and saved: {dest_path.name}")
                return True
            except Exception as e:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                print(f"  Error saving file: {e}")
                return False
                
        except Exception as e:
            print(f"  Network/IO Error downloading {absolute_url}: {e}. Retrying in {backoff}s...")
            time.sleep(backoff)
            backoff *= 2
            
    print(f"  Error: Max retries exceeded for {absolute_url}")
    return False

def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Cambridge POS-disambiguated audio files.")
    parser.add_argument("--apply", action="store_true", help="Perform the actual downloads and sync.")
    args = parser.parse_args()
    
    # Enable utf-8 encoding for console printing
    sys.stdout.reconfigure(encoding="utf-8")
    
    # 1. Load cards from anki_notes.jsonl
    jsonl_path = paths.root / "data" / "build" / "anki_notes.jsonl"
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} not found. Build notes first.")
        return 1
        
    cards = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            cards.append(json.loads(line))
            
    # Filter cards within scope
    scoped_cards = [c for c in cards if c.get("word", "").lower() in SCOPED_WORDS]
    
    print(f"Found {len(scoped_cards)} cards in scope (preflight check: {PREFLIGHT_CARD_COUNT})")
    if len(scoped_cards) != PREFLIGHT_CARD_COUNT:
        print(f"Error: Scoped cards count ({len(scoped_cards)}) differs from preflight count ({PREFLIGHT_CARD_COUNT}). Aborting.")
        return 1
        
    # Load word to source file mapping
    word_to_file = load_word_to_source_file()
    
    # Pre-parse all cache files
    cache_dir = paths.root / "data" / ".cache_html" / "cambridge"
    
    download_plan = []
    old_files_to_delete = set()
    output_filenames = {}
    
    for card in scoped_cards:
        word = card.get("word")
        pos = card.get("pos")
        
        word_clean = normalize_word(word)
        source_file = word_to_file.get(word_clean)
        if not source_file:
            print(f"Error: No Cambridge cache file mapped for '{word_clean}'. Aborting.")
            return 1
            
        cache_path = cache_dir / source_file
        if not cache_path.exists():
            print(f"Error: Cache file {cache_path} does not exist. Aborting.")
            return 1
            
        with open(cache_path, "rb") as f:
            html_bytes = f.read()
            
        entries = parse_cambridge_entries(html_bytes)
        entry = select_entry(word, pos, entries)
        if not entry:
            print(f"Error: No matching entry found for '{word}' ({pos}) in {source_file}. Aborting.")
            return 1
            
        # Extract UK and US URLs
        uk_url = entry.get("uk_audio")
        us_url = entry.get("us_audio")
        
        if not uk_url or not us_url:
            print(f"Error: Missing UK or US URL for '{word}' ({pos}) in {source_file}. Aborting.")
            return 1
            
        # Target filenames
        uk_name = get_audio_filename(word, pos, "uk")
        us_name = get_audio_filename(word, pos, "us")
        
        # Check for output filename collisions
        if uk_name in output_filenames and output_filenames[uk_name] != uk_url:
            print(f"Error: Output filename collision detected ('{uk_name}' maps to different URLs). Aborting.")
            return 1
        if us_name in output_filenames and output_filenames[us_name] != us_url:
            print(f"Error: Output filename collision detected ('{us_name}' maps to different URLs). Aborting.")
            return 1
            
        if uk_name not in output_filenames:
            output_filenames[uk_name] = uk_url
            download_plan.append((uk_url, paths.root / "audio" / uk_name))
        if us_name not in output_filenames:
            output_filenames[us_name] = us_url
            download_plan.append((us_url, paths.root / "audio" / us_name))
        
        # Identify old files to delete
        # For Cambridge, the old names were cambridge_{uk|us}_{word}.mp3 or variants
        old_files_to_delete.add(f"cambridge_uk_{word}.mp3")
        old_files_to_delete.add(f"cambridge_us_{word}.mp3")
        old_files_to_delete.add(f"cambridge_uk_{word_clean}.mp3")
        old_files_to_delete.add(f"cambridge_us_{word_clean}.mp3")
        
        # For curate and sake, also Oxford files
        if word_clean in ("curate", "sake"):
            old_files_to_delete.add(f"oxford_uk_{word_clean}.mp3")
            old_files_to_delete.add(f"oxford_us_{word_clean}.mp3")
            
    print(f"Preflight check passed. Total downloads planned: {len(download_plan)}")
    
    # Perform downloads
    success_count = 0
    for url, dest_path in download_plan:
        if download_audio(url, dest_path, args.apply):
            success_count += 1
            
    if args.apply and success_count != len(download_plan):
        print("Error: Some downloads failed. Aborting.")
        return 1
        
    print(f"Sync complete. Success count: {success_count}/{len(download_plan)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
