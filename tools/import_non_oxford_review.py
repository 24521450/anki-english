import sys
import os
import json
import re
import hashlib
import argparse
from pathlib import Path

# Insert project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.gloss_llm import validate_verdict
from src.config import ProjectPaths

EXPECTED_SHA = "31C28A42A8B1FE8445A591734DE5C0297DE675A398E24BA037E847E8BFAFC0EF"

def parse_english_gloss(definition: str) -> tuple[str, str, int]:
    """Extracts English gloss, determines separator and count from full Definition."""
    sep = '|' if '|' in definition else ';' if ';' in definition else 'none'
    chunks = re.split(r'\s*[|;]\s*', definition.strip())
    
    en_chunks = []
    for chunk in chunks:
        m = re.match(r"^(.*?)\s*\(", chunk)
        if m:
            en_chunks.append(m.group(1).strip())
        else:
            en_chunks.append(chunk.strip())
            
    en_gloss = ("|" if sep == '|' else ";" if sep == ';' else "").join(en_chunks)
    return en_gloss, sep, len(en_chunks)

def main() -> int:
    ap = argparse.ArgumentParser(description="Import non-Oxford non-C2 review overrides.")
    ap.add_argument("--apply", action="store_true", help="Write to canonical JSONL output path")
    ap.add_argument("--source", type=Path, required=True, help="Path to source markdown file")
    args = ap.parse_args()

    if not args.source.exists():
        print(f"Error: Source file not found: {args.source}", file=sys.stderr)
        return 1

    # Verify SHA-256
    source_bytes = args.source.read_bytes()
    sha256 = hashlib.sha256(source_bytes).hexdigest().upper()
    if sha256 != EXPECTED_SHA:
        print(f"Error: SHA-256 mismatch! Expected {EXPECTED_SHA}, got {sha256}", file=sys.stderr)
        return 1

    content = source_bytes.decode("utf-8", errors="ignore")
    blocks = re.findall(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    
    if len(blocks) != 381:
        print(f"Error: Expected exactly 381 blocks, but found {len(blocks)}", file=sys.stderr)
        return 1

    # Use ProjectPaths config
    paths_reg = ProjectPaths()
    canonical_output = paths_reg.non_oxford_non_c2_overrides
    canonical_built_notes = paths_reg.anki_notes_jsonl

    # Load existing overrides to map GUIDs for rerun stability
    existing_overrides_by_key = {}
    if canonical_output.exists():
        with open(canonical_output, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    k = (r["word"].strip().lower(), r["input_pos"].strip().lower(), r["cefr"].strip().upper())
                    existing_overrides_by_key[k] = r

    # Load built notes
    if not canonical_built_notes.exists():
        print(f"Error: Built notes not found at {canonical_built_notes}. Please run tools.build_notes first.", file=sys.stderr)
        return 1

    built_cards = []
    with open(canonical_built_notes, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                built_cards.append(json.loads(line))

    cards_by_guid = {c["guid"]: c for c in built_cards}
    cards_by_key = {
        (c["word"].strip().lower(), c["pos"].strip().lower(), c["cefr"].strip().upper()): c
        for c in built_cards
    }

    seen_keys = set()
    output_rows = []
    semicolon_count = 0

    for idx, block in enumerate(blocks, 1):
        try:
            data = json.loads(block)
        except Exception as e:
            print(f"Error parsing block {idx}: {e}", file=sys.stderr)
            return 1

        word = data.get("word")
        pos = data.get("pos")
        cefr = data.get("cefr")
        update = data.get("anki_update")

        if not word or not pos or not cefr or not update:
            print(f"Error block {idx}: missing word/pos/cefr/anki_update", file=sys.stderr)
            return 1

        word_clean = word.strip()
        pos_clean = pos.strip()
        cefr_clean = cefr.strip().upper()
        key = (word_clean.lower(), pos_clean.lower(), cefr_clean)

        if key in seen_keys:
            print(f"Error block {idx}: duplicate key in source: {key}", file=sys.stderr)
            return 1
            
        seen_keys.add(key)

        definition = update.get("Definition", "").strip()
        example = update.get("Example", "").strip()
        collocations = update.get("Collocations", "").strip()

        if not definition:
            print(f"Error block {idx} ({word_clean}): empty definition", file=sys.stderr)
            return 1

        # Apply manual decisions
        output_pos = None
        if word_clean.lower() == "harness" and pos_clean.lower() == "verb" and cefr_clean == "UNCLASSIFIED":
            definition = "control and use power or resources (khai thác/tận dụng)"
            example = "attempts to harness the sun’s rays as a source of energy"
            collocations = "harness energy/power/resources; harness the sun/wind; harness sth to do sth"
        elif word_clean.lower() == "nursing" and pos_clean.lower() == "noun, adjective" and cefr_clean == "B2":
            definition = "care of sick people (nghề điều dưỡng/chăm sóc bệnh nhân)"
            example = "a career in nursing"
            collocations = "nursing care/profession/career; career in nursing"
            output_pos = "noun"

        # Count semicolons in Collocations before normalization
        semicolon_count += collocations.count(";")

        # Convert semicolons to pipes and strip whitespaces
        collocations = collocations.replace(";", "|")
        colloc_chunks = [c.strip() for c in collocations.split("|")]
        collocations = "|".join([c for c in colloc_chunks if c])

        # Validate English gloss using validate_verdict
        en_gloss, sep, count = parse_english_gloss(definition)
        violations = validate_verdict(word_clean, en_gloss, sep, count)
        if violations:
            print(f"Validation failed for {word_clean} ({pos_clean}, {cefr_clean}): {violations}", file=sys.stderr)
            return 1

        # GUID matching & rerun stability
        matched_card = None

        # 1. Match from existing overrides if rerun
        if key in existing_overrides_by_key:
            existing_guid = existing_overrides_by_key[key]["guid"]
            matched_card = cards_by_guid.get(existing_guid)

        # 2. Match from key in built notes
        if not matched_card:
            matched_card = cards_by_key.get(key)

        # 3. Match from remapped output POS in built notes (rerun after POS migration has run)
        if not matched_card and output_pos:
            remapped_key = (word_clean.lower(), output_pos.lower(), cefr_clean)
            matched_card = cards_by_key.get(remapped_key)

        if not matched_card:
            print(f"Error: Card key {key} not found in built notes {canonical_built_notes}", file=sys.stderr)
            return 1

        row = {
            "guid": matched_card["guid"],
            "word": word_clean,
            "input_pos": pos_clean,
            "cefr": cefr_clean,
            "Definition": definition,
            "Example": example,
            "Collocations": collocations,
            "output_pos": output_pos,
            "source_filename": args.source.name,
            "sha256": EXPECTED_SHA,
            "fix_status": "non_oxford_non_c2_review_20260701",
        }
        output_rows.append(row)

    if len(output_rows) != 381:
        print(f"Error: Output rows count is {len(output_rows)}, expected 381", file=sys.stderr)
        return 1

    if args.apply:
        canonical_output.parent.mkdir(parents=True, exist_ok=True)
        with open(canonical_output, "w", encoding="utf-8") as f:
            for row in output_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Successfully wrote 381 rows to {canonical_output}")
        print(f"Total semicolons replaced in Collocations: {semicolon_count}")
    else:
        print(f"Dry-run verification passed successfully! Parsed and matched 381 rows.")
        print(f"Total semicolons to replace in Collocations: {semicolon_count}")
        print(f"Run with --apply to write to {canonical_output}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
