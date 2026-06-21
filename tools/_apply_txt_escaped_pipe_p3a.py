"""P3A Deck TXT Escaped-Pipe Cleanup tool.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.gloss_hygiene import compact_pipe_in_text

DECK_TXT = PROJECT_ROOT / 'English Academic Vocabulary.txt'


def process_line(line: str) -> tuple[str, bool]:
    """Process a single line of English Academic Vocabulary.txt.
    
    If the line starts with '#' or has fewer than 7 fields, returns it unchanged.
    Otherwise, applies compact_pipe_in_text (which handles un-escaping and compacting)
    to field index 6 (Definition).
    """
    if line.startswith('#') or not line.strip():
        return line, False
    
    fields = line.split('\t')
    if len(fields) <= 6:
        return line, False
    
    original_def = fields[6]
    if '\\|' not in original_def:
        return line, False
        
    # Check if we have escaped pipe or loose spacing
    # compact_pipe_in_text handles both un-escaping and spacing compaction.
    new_def, changed = compact_pipe_in_text(original_def)
    
    if changed:
        fields[6] = new_def
        return '\t'.join(fields), True
    
    return line, False


def process_txt_lines(lines: list[str], expected_count: int = 88) -> tuple[list[str], int]:
    """Process a list of lines. Raises ValueError if modified count != expected_count."""
    new_lines = []
    modified_count = 0
    for line in lines:
        new_line, modified = process_line(line)
        new_lines.append(new_line)
        if modified:
            modified_count += 1
            
    if modified_count != expected_count:
        raise ValueError(
            f"Expected exactly {expected_count} touched rows, but got {modified_count}"
        )
        
    return new_lines, modified_count


def _ts() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def main() -> int:
    ap = argparse.ArgumentParser(description='Apply P3A deck txt escaped-pipe cleanup.')
    ap.add_argument('--apply', action='store_true', help='Actually write changes.')
    args = ap.parse_args()

    print("=" * 72)
    print(f"P3A Deck TXT Escaped-Pipe Cleanup (apply={args.apply})")
    print(f"Timestamp: {_ts()}")
    print("=" * 72)

    # 1. Read file lines
    print(f"Reading {DECK_TXT.name}...")
    lines = DECK_TXT.read_text(encoding='utf-8').splitlines(keepends=False)
    print(f"Total lines: {len(lines)}")

    # 2. Process lines
    try:
        new_lines, count = process_txt_lines(lines, expected_count=88)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    print(f"Successfully processed: {count} rows updated.")

    # 3. Write changes if --apply
    if args.apply:
        # Create backup
        bak = DECK_TXT.with_suffix(DECK_TXT.suffix + f'.bak_pre_txt_pipe_p3a_{_ts()}')
        bak.write_bytes(DECK_TXT.read_bytes())
        print(f"Created backup: {bak.name}")

        # Replace file contents
        # splitlines(keepends=False) drops newlines. We write back joined with '\n' and ending with '\n'
        text_out = '\n'.join(new_lines) + '\n'
        tmp = DECK_TXT.with_suffix(DECK_TXT.suffix + '.tmp_p3a')
        tmp.write_text(text_out, encoding='utf-8')
        tmp.replace(DECK_TXT)
        print("Cleaned deck definitions written successfully.")
    else:
        print("Dry run completed. Run with --apply to write changes.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
