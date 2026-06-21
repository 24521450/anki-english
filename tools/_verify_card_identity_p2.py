"""P2 Card Identity Dedup Verification tool.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

MASTER_AUDIT = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
FILLED_AUDIT = PROJECT_ROOT / 'data' / 'audit_expanded_needs_gloss_filled.jsonl'
DECK_TXT = PROJECT_ROOT / 'English Academic Vocabulary.txt'

EXPECTED_KEEPERS = {
    ('labor', 'noun', 'C2'): 'childbirth',
    ('migrate', 'verb', 'C1'): 'move',
    ('navigate', 'verb', 'C1'): 'find way',
    ('sanctuary', 'noun', 'C2'): 'holy place',
    ('diplomatic', 'adjective', 'C1'): 'international|tactful',
}


def verify() -> int:
    print("=" * 72)
    print("P2 CARD IDENTITY DEDUP VERIFICATION")
    print("=" * 72)

    # 1. Master audit count is 2487
    print("[1] Verifying master audit row count...")
    rows = []
    with MASTER_AUDIT.open(encoding='utf-8') as fp:
        for line in fp:
            if line.strip():
                rows.append(json.loads(line))
    
    row_count = len(rows)
    print(f"  Master audit count: {row_count}")
    assert row_count == 2487, f"Expected exactly 2487 rows, got {row_count}"

    # 2. No duplicates in audit
    print("[2] Verifying no duplicate (word, pos, cefr) keys in master audit...")
    keys = []
    for r in rows:
        keys.append((r['word'], r['pos'], r['cefr']))
    
    unique_keys = set(keys)
    duplicates = [k for k in unique_keys if keys.count(k) > 1]
    print(f"  Duplicate count: {len(duplicates)}")
    assert len(duplicates) == 0, f"Expected 0 duplicate keys, found: {duplicates}"

    # 3. Keeper keys exist once with expected gloss
    print("[3] Verifying keeper glosses in master audit...")
    for (w, p, c), expected_gloss in EXPECTED_KEEPERS.items():
        matching = [r for r in rows if r['word'] == w and r['pos'] == p and r['cefr'] == c]
        assert len(matching) == 1, f"Expected exactly 1 keeper row for ({w}, {p}, {c}), got {len(matching)}"
        actual_gloss = matching[0]['gloss_after']
        print(f"  ({w}, {p}, {c}) -> {actual_gloss} (Expected: {expected_gloss})")
        assert actual_gloss == expected_gloss, f"Gloss mismatch: got {actual_gloss!r}, expected {expected_gloss!r}"

    # 4. TXT definitions check
    print("[4] Verifying English Academic Vocabulary.txt definitions...")
    txt_rows = []
    with DECK_TXT.open(encoding='utf-8') as fp:
        for line in fp:
            if not line.startswith('#') and line.strip():
                txt_rows.append(line.split('\t'))

    # Check for no duplicate counterparts in TXT for those 5 keys
    for (w, p, c), expected_gloss in EXPECTED_KEEPERS.items():
        matching_txt = [r for r in txt_rows if len(r) > 14 and r[3] == w and r[4] == p and r[14] == c]
        # In TXT, some words (e.g. migrate) might have B2 and C1 cards, but each (word, pos, cefr) must appear at most once.
        # Let's count how many matching rows there are.
        print(f"  TXT cards for ({w}, {p}, {c}): {len(matching_txt)}")
        assert len(matching_txt) <= 1, f"Duplicate cards found in TXT for ({w}, {p}, {c}): {len(matching_txt)}"
        if len(matching_txt) == 1:
            actual_txt_def = matching_txt[0][6]
            print(f"    TXT Definition: {actual_txt_def!r} (Expected: {expected_gloss!r})")
            assert actual_txt_def == expected_gloss, f"TXT definition mismatch: got {actual_txt_def!r}, expected {expected_gloss!r}"

    # 5. Filled audit duplicates scan remains clean
    print("[5] Verifying no duplicates in filled audit...")
    filled_keys = []
    with FILLED_AUDIT.open(encoding='utf-8') as fp:
        for line in fp:
            if line.strip():
                r = json.loads(line)
                filled_keys.append((r['word'], r['pos'], r['cefr']))
    filled_dups = [k for k in set(filled_keys) if filled_keys.count(k) > 1]
    print(f"  Filled duplicates count: {len(filled_dups)}")
    assert len(filled_dups) == 0, f"Expected 0 duplicates in filled audit, got: {filled_dups}"

    # 6. Build dry-run loads exactly 2487 audit glosses and 2450 cards
    print("[6] Running build_notes.py dry-run to verify counts...")
    cmd = [sys.executable, str(PROJECT_ROOT / 'tools' / 'build_notes.py'), '--dry-run']
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
    stdout = res.stdout
    
    print("  Verifying stdout metrics:")
    assert "audit_glosses_loaded: 2487" in stdout or "audit glosses loaded: 2487" in stdout, "Did not find expected audit glosses loaded metric"
    assert "existing cards: 2450" in stdout or "built cards: 2450" in stdout, "Did not find expected built cards metric"
    assert "Dup emit skipped: 0" in stdout, "Did not find Dup emit skipped: 0 metric"
    print("  Build dry-run counts verified successfully.")

    print("\nPASS: All verification checks completed successfully.")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(verify())
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        sys.exit(1)
