#!/usr/bin/env python3
"""Production command for Anki .apkg packaging.

Reads notes from data/build/anki_notes.jsonl and templates from design/EAVM/,
builds a genanki Model/Decks, validates media assets under audio/,
and compiles them into ielts_deck.apkg.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import sys
from pathlib import Path

import genanki

from src.config import ProjectPaths
from src.design_css import design_css_in_sync, load_production_css

paths = ProjectPaths()
NOTES_JSONL = paths.anki_notes_jsonl
AUDIO_DIR = paths.audio_dir
PROJECT_ROOT = paths.root
FRONT_TEMPLATE = PROJECT_ROOT / "design" / "EAVM" / "front_template.txt"
BACK_TEMPLATE = PROJECT_ROOT / "design" / "EAVM" / "back_template.txt"
PRODUCTION_FRONT_TEMPLATE = (
    PROJECT_ROOT / "design" / "EAVM" / "production_front_template.txt"
)
PRODUCTION_ANSWER_PREFIX = (
    PROJECT_ROOT / "design" / "EAVM" / "production_answer_prefix.txt"
)
STYLING_TXT = PROJECT_ROOT / "design" / "EAVM" / "styling.txt"
DESIGN_INDEX = PROJECT_ROOT / "design" / "index.html"
OUTPUT_APKG = PROJECT_ROOT / "ielts_deck.apkg"

# Identity of the established local EAVM note type. Changing this ID or its
# field order makes Anki create a suffixed duplicate during package import.
EAVM_MODEL_NAME = "English Academic Vocabulary Model"
EAVM_MODEL_ID = 1607392819
EAVM_JSON_TO_FIELD: tuple[tuple[str, str], ...] = (
    ("word", "Word"),
    ("pos", "PartOfSpeech"),
    ("ipa", "IPA"),
    ("definition", "Definition"),
    ("example", "Example"),
    ("collocations", "Collocations"),
    ("wordfamily", "WordFamily"),
    ("uk_audio", "AudioUK"),
    ("us_audio", "AudioUS"),
    ("source1", "AudioSource"),
    ("source2", "Source"),
    ("cefr", "CEFRLevel"),
    ("idioms", "Idioms"),
    ("synonyms", "Synonyms"),
    ("antonyms", "Antonyms"),
    ("example_audio_uk", "ExampleAudioUK"),
    ("example_audio_us", "ExampleAudioUS"),
    ("idiom_example_audio_uk", "IdiomExampleAudioUK"),
    ("idiom_example_audio_us", "IdiomExampleAudioUS"),
    ("definition_vi", "DefinitionVI"),
    ("cambridge_url", "CambridgeURL"),
    ("oxford_pos_urls", "OxfordPOSURLs"),
    ("production_answer", "ProductionAnswer"),
)
EAVM_FIELD_NAMES: tuple[str, ...] = tuple(
    field_name for _, field_name in EAVM_JSON_TO_FIELD
)
EAVM_TEMPLATE_NAMES = ("Recognition", "Production (VI -> EN)")


@dataclass(frozen=True)
class EavmTemplate:
    """One canonical EAVM template in Anki ordinal order."""

    name: str
    front: str
    back: str

    def for_genanki(self) -> dict[str, str]:
        return {"name": self.name, "qfmt": self.front, "afmt": self.back}

    def for_anki_connect(self) -> dict[str, str]:
        return {"Front": self.front, "Back": self.back}


def load_eavm_templates(
    recognition_front_path: Path | None = None,
    recognition_back_path: Path | None = None,
    production_front_path: Path | None = None,
    production_answer_prefix_path: Path | None = None,
) -> tuple[EavmTemplate, EavmTemplate]:
    """Load the ordered Recognition and Production template contract."""

    recognition_front = (recognition_front_path or FRONT_TEMPLATE).read_text(
        encoding="utf-8"
    )
    recognition_back = (recognition_back_path or BACK_TEMPLATE).read_text(
        encoding="utf-8"
    )
    production_front = (production_front_path or PRODUCTION_FRONT_TEMPLATE).read_text(
        encoding="utf-8"
    )
    production_prefix = (
        production_answer_prefix_path or PRODUCTION_ANSWER_PREFIX
    ).read_text(encoding="utf-8")
    native_type_count = (
        production_front + production_prefix + recognition_back
    ).count("{{type:ProductionAnswer}}")
    if (
        production_front.count("{{type:ProductionAnswer}}") != 1
        or native_type_count != 1
        or "{{type:ProductionAnswer}}" in recognition_front
        or "{{FrontSide}}" in production_front
    ):
        raise ValueError(
            "Production front template must contain exactly one native "
            "{{type:ProductionAnswer}} replacement and no {{FrontSide}}"
        )
    production_back = production_prefix + recognition_back
    if (production_front + production_back).count("{{FrontSide}}") != 1:
        raise ValueError(
            "Production answer must contain exactly one {{FrontSide}} replacement"
        )
    return (
        EavmTemplate("Recognition", recognition_front, recognition_back),
        EavmTemplate(
            "Production (VI -> EN)",
            production_front,
            production_back,
        ),
    )


def configure_genanki_requirements(model: genanki.Model) -> None:
    """Tell genanki's static parser the conditional card-generation contract.

    The Recognition template intentionally carries hidden raw fields and the
    Production template carries JavaScript.  genanki's Mustache probe treats
    those hidden references as required unless the requirements are explicit;
    Anki itself still evaluates the native conditional sections at import.
    """

    field_index = {name: index for index, name in enumerate(EAVM_FIELD_NAMES)}
    model._req = [
        [0, "any", [field_index["Word"]]],
        [
            1,
            "all",
            sorted(
                field_index[name]
                for name in ("DefinitionVI", "Example", "ProductionAnswer")
            ),
        ],
    ]


def check_design_sync() -> bool:
    try:
        return design_css_in_sync(DESIGN_INDEX, STYLING_TXT)
    except (OSError, ValueError):
        return False

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


def extract_audio_filenames(audio_field: str) -> list[str]:
    """Extract all Anki sound and manual HTML-audio media references."""
    if not audio_field:
        return []
    filenames = re.findall(r'\[sound:([^\]]+)\]', audio_field)
    filenames.extend(
        re.findall(r'<audio\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>', audio_field, re.IGNORECASE)
    )
    return [filename.strip() for filename in filenames if filename.strip()]


def is_empty_audio_layout(audio_field: str) -> bool:
    """Return whether a reference field contains alignment delimiters only."""
    remainder = re.sub(r"(?:\$\$|\||<br\s*/?>|\s)+", "", audio_field, flags=re.IGNORECASE)
    return not remainder

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="CLI adapter for Anki .apkg packaging.")
    ap.add_argument("--dry-run", action="store_true", help="Run validation and checks, but do not write .apkg")
    args = ap.parse_args(argv)

    # 1. Enforce design sync check
    print("=== Step 1: Running design sync check ===", file=sys.stderr)
    if not check_design_sync():
        print("Error: Design sync check failed! Aborting packaging.", file=sys.stderr)
        return 1

    # 2. Check inputs
    if not NOTES_JSONL.exists():
        print(f"Error: {NOTES_JSONL.name} not found. Run build step first.", file=sys.stderr)
        return 1
    required_design_files = (
        FRONT_TEMPLATE,
        BACK_TEMPLATE,
        PRODUCTION_FRONT_TEMPLATE,
        PRODUCTION_ANSWER_PREFIX,
        STYLING_TXT,
    )
    if any(not path.exists() for path in required_design_files):
        print("Error: EAVM template/styling files not found in design/EAVM/.", file=sys.stderr)
        return 1

    # 3. Read templates & CSS styling
    print("=== Step 2: Reading card design templates ===", file=sys.stderr)
    try:
        templates = load_eavm_templates()
        styling_css = load_production_css(STYLING_TXT)
    except (OSError, ValueError) as exc:
        print(f"Error: Invalid EAVM design contract: {exc}", file=sys.stderr)
        return 1

    # 4. Define genanki model
    # Tags are Anki metadata, exposed through the built-in {{Tags}} replacement.
    fields_schema = [{"name": name} for name in EAVM_FIELD_NAMES]

    model = genanki.Model(
        EAVM_MODEL_ID,
        EAVM_MODEL_NAME,
        fields=fields_schema,
        templates=[template.for_genanki() for template in templates],
        css=styling_css
    )
    configure_genanki_requirements(model)

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

            # Map JSONL keys to genanki fields order. Missing keys default
            # to empty string so legacy 12-field JSONL rows still validate.
            note_fields = [r.get(key) or "" for key, _ in EAVM_JSON_TO_FIELD]

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

            for audio_field_name in (
                "example_audio_uk", "example_audio_us",
                "idiom_example_audio_uk", "idiom_example_audio_us",
            ):
                audio_value = r.get(audio_field_name) or ""
                filenames = extract_audio_filenames(audio_value)
                if audio_value.strip() and not filenames and not is_empty_audio_layout(audio_value):
                    print(
                        f"Error: Malformed example audio field {audio_field_name!r} "
                        f"(referenced on line {line_num})",
                        file=sys.stderr,
                    )
                    return 1
                for filename in filenames:
                    if Path(filename).name != filename:
                        print(f"Error: Invalid audio filename {filename!r} on line {line_num}", file=sys.stderr)
                        return 1
                    audio_path = AUDIO_DIR / filename
                    if not audio_path.exists():
                        print(
                            f"Error: Missing referenced audio file '{filename}' "
                            f"(referenced on line {line_num})",
                            file=sys.stderr,
                        )
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
