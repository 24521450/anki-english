"""Find non-skip zero-card records (anomaly investigation)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
sys.path.insert(0, str(PROJECT_ROOT))

import json
from src.deck_builder import resolve_cards

with open(PROJECT_ROOT / "data" / "oxford_merged.jsonl", encoding="utf-8") as f:
    records = [json.loads(l) for l in f]

# Find records that produce 0 notes but aren't _skip=true
for r in records:
    if r.get("_skip"):
        continue
    notes = resolve_cards(r)
    if not notes:
        print(f"word={r['word']!r}, h={r.get('homonym_index')}, pos={r.get('pos')}, "
              f"badge={r.get('oxford_badge')}, pos_data_count={len(r.get('pos_data', []))}, "
              f"idioms={len(r.get('idioms', []))}")
