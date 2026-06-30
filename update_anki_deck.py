#!/usr/bin/env python3
"""CLI adapter for Anki .apkg packaging.

Reads notes from data/build/anki_notes.jsonl and templates from design/EAVM/,
builds a genanki Model/Decks, validates media assets under audio/,
and compiles them into ielts_deck.apkg.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path
import genanki

from src.config import ProjectPaths

paths = ProjectPaths()
NOTES_JSONL = paths.anki_notes_jsonl
AUDIO_DIR = paths.audio_dir
PROJECT_ROOT = paths.root
FRONT_TEMPLATE = PROJECT_ROOT / "design" / "EAVM" / "front_template.txt"
BACK_TEMPLATE = PROJECT_ROOT / "design" / "EAVM" / "back_template.txt"
STYLING_TXT = PROJECT_ROOT / "design" / "EAVM" / "styling.txt"
OUTPUT_APKG = PROJECT_ROOT / "ielts_deck.apkg"

def generate_deterministic_id(name: str) -> int:
    """Generate a stable positive 31-bit integer ID from SHA-1 of the string name.

    Anki requires deck/model IDs to be positive integers within 32-bit signed range
    (1 to 2**31 - 1). This ensures IDs are identical across runs/platforms.
    """
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()
    val = int(h[:8], 16) & 0x7FFFFFFF
    if val == 0:
        return 1
    return val

def extract_audio_filename(sound_field: str) -> str | None:
    """Extract file name from '[sound:filename.mp3]' wrapper."""
    if not sound_field:
        return None
    m = re.match(r'\[sound:(.+?)\]', sound_field.strip())
    if m:
        return m.group(1).strip()
    return None

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="CLI adapter for Anki .apkg packaging.")
    ap.add_argument("--dry-run", action="store_true", help="Run validation and checks, but do not write .apkg")
    args = ap.parse_args(argv)

    # 1. Enforce design sync check
    print("=== Step 1: Running design sync check ===", file=sys.stderr)
    from tools.check_design_sync import main as run_design_sync
    sync_code = run_design_sync()
    if sync_code != 0:
        print("Error: Design sync check failed! Aborting packaging.", file=sys.stderr)
        return 1

    # 2. Check inputs
    if not NOTES_JSONL.exists():
        print(f"Error: {NOTES_JSONL.name} not found. Run build step first.", file=sys.stderr)
        return 1
    if not FRONT_TEMPLATE.exists() or not BACK_TEMPLATE.exists() or not STYLING_TXT.exists():
        print("Error: EAVM template/styling files not found in design/EAVM/.", file=sys.stderr)
        return 1

    # 3. Read templates & CSS styling
    print("=== Step 2: Reading card design templates ===", file=sys.stderr)
    front_html = FRONT_TEMPLATE.read_text(encoding="utf-8")
    back_html = BACK_TEMPLATE.read_text(encoding="utf-8")
    styling_css = STYLING_TXT.read_text(encoding="utf-8")

    # 4. Define genanki model
    # Model ID is derived deterministically from the model name
    model_name = "English Academic Vocabulary Model"
    model_id = generate_deterministic_id(model_name)
    
    # 12-field mapping expected by templates
    fields_schema = [
        {"name": "Word"},
        {"name": "CEFRLevel"},
        {"name": "PartOfSpeech"},
        {"name": "Definition"},
        {"name": "Example"},
        {"name": "IPA"},
        {"name": "AudioUK"},
        {"name": "AudioUS"},
        {"name": "Tags"},
        {"name": "Collocations"},
        {"name": "WordFamily"},
        {"name": "Idioms"},
    ]

    model = genanki.Model(
        model_id,
        model_name,
        fields=fields_schema,
        templates=[
            {
                "name": "Card 1",
                "qfmt": front_html,
                "afmt": back_html,
            }
        ],
        css=styling_css
    )

    # 5. Load notes and group by deck
    print(f"=== Step 3: Loading notes from {NOTES_JSONL.name} ===", file=sys.stderr)
    decks: dict[str, genanki.Deck] = {}
    media_files: set[str] = set()

    with NOTES_JSONL.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON on line {line_num}: {e}", file=sys.stderr)
                return 1

            deck_name = r.get("deck")
            if not deck_name:
                print(f"Error: Note on line {line_num} has no deck value.", file=sys.stderr)
                return 1

            # Get or create deck (deterministic ID per deck name)
            if deck_name not in decks:
                deck_id = generate_deterministic_id(deck_name)
                decks[deck_name] = genanki.Deck(deck_id, deck_name)

            # Map JSONL keys to genanki fields order
            note_fields = [
                r.get("word") or "",
                r.get("cefr") or "",
                r.get("pos") or "",
                r.get("definition") or "",
                r.get("example") or "",
                r.get("ipa") or "",
                r.get("uk_audio") or "",
                r.get("us_audio") or "",
                r.get("tags") or "",
                r.get("collocations") or "",
                r.get("wordfamily") or "",
                r.get("idioms") or "",
            ]

            # Validate audio files
            for audio_field_name in ("uk_audio", "us_audio"):
                sound_str = r.get(audio_field_name)
                if sound_str and sound_str.strip():
                    filename = extract_audio_filename(sound_str)
                    if not filename:
                        print(f"Error: Malformed audio reference '{sound_str}' (referenced on line {line_num})", file=sys.stderr)
                        return 1
                    audio_path = AUDIO_DIR / filename
                    if not audio_path.exists():
                        print(f"Error: Missing referenced audio file '{filename}' (referenced on line {line_num})", file=sys.stderr)
                        return 1
                    media_files.add(str(audio_path))

            # Split space-separated tags list
            raw_tags = r.get("tags") or ""
            note_tags = [t.strip() for t in raw_tags.split() if t.strip()]

            # Preserve GUID
            guid = r.get("guid")
            if not guid:
                print(f"Error: Note on line {line_num} has no GUID.", file=sys.stderr)
                return 1

            note = genanki.Note(
                model=model,
                fields=note_fields,
                guid=guid,
                tags=note_tags
            )
            decks[deck_name].add_note(note)

    # 6. Bake .apkg
    print("=== Step 4: Baking .apkg ===", file=sys.stderr)
    print(f"  Total decks: {len(decks)}", file=sys.stderr)
    for name, d in decks.items():
        print(f"    - {name}: {len(d.notes)} cards", file=sys.stderr)
    print(f"  Total media files: {len(media_files)}", file=sys.stderr)

    package = genanki.Package(list(decks.values()))
    package.media_files = sorted(list(media_files))
    
    if args.dry_run:
        print(f"[dry-run] Successfully validated notes, templates, and media. Output would be written to {OUTPUT_APKG}", file=sys.stderr)
        return 0

    # Write package file
    package.write_to_file(OUTPUT_APKG)
    print(f"[OK] Successfully wrote {OUTPUT_APKG}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
