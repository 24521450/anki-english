"""Scan oxford_merged.jsonl to find multi-topic issues.

Finds:
1. Topic names containing ','
2. Topic names containing a CEFR badge pattern (e.g., a1, b2, c1) not at the end.
"""
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
MERGED_PATH = ROOT / "data" / "oxford_merged.jsonl"

def main():
    if not MERGED_PATH.exists():
        print(f"File not found: {MERGED_PATH}")
        return 1

    cefr_pattern = re.compile(r"[a-c][1-2]", re.IGNORECASE)
    
    count_comma = 0
    count_embedded_cefr = 0
    affected_words = set()
    
    examples = []
    
    with open(MERGED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            word = record.get("word")
            
            for pd in record.get("pos_data", []):
                for d in pd.get("definitions", []):
                    for topic in d.get("topics", []):
                        name = topic.get("name", "")
                        has_comma = "," in name
                        # Find if there is a CEFR pattern anywhere in the name
                        has_embedded = bool(cefr_pattern.search(name))
                        
                        if has_comma or has_embedded:
                            affected_words.add(word)
                            if has_comma:
                                count_comma += 1
                            if has_embedded:
                                count_embedded_cefr += 1
                            examples.append({
                                "word": word,
                                "topic_name": name,
                                "cefr": topic.get("cefr"),
                                "has_comma": has_comma,
                                "has_embedded": has_embedded
                            })

    print(f"Total affected words: {len(affected_words)}")
    print(f"Total topics with comma: {count_comma}")
    print(f"Total topics with embedded CEFR: {count_embedded_cefr}")
    
    print("\n--- Top 20 Examples ---")
    for ex in examples[:20]:
        print(f"Word: {ex['word']:<20} | Topic: {ex['topic_name']:<40} | CEFR: {ex['cefr']}")
        
    return 0

if __name__ == "__main__":
    main()
