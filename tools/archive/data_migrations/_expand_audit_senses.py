import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL_FILE = PROJECT_ROOT / "data" / "oxford_merged.jsonl"
AUDIT_FILE = PROJECT_ROOT / "data" / "audit_full_deck_v2.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data" / "audit_expanded_needs_gloss.jsonl"

def main():
    print("=== Expanding Audit Senses (No Limit) ===")
    
    # 1. Load senses from oxford_merged.jsonl
    # Index by (word, pos, cefr) -> list of MergedSense dicts
    senses_index = {}
    if JSONL_FILE.exists():
        with JSONL_FILE.open(encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                word = r.get('word', '').strip().lower()
                for pd in r.get('pos_data', []) or []:
                    pos = pd.get('pos', '').strip().lower()
                    for s in pd.get('definitions', []) or []:
                        cefr = (s.get('cefr') or '').strip().upper()
                        if not cefr:
                            cefr = 'UNCLASSIFIED'
                        key = (word, pos, cefr)
                        senses_index.setdefault(key, []).append(s)

    # 2. Iterate audit_full_deck_v2.jsonl and modify entries
    modified_records = []
    new_audit_lines = []
    
    if AUDIT_FILE.exists():
        with AUDIT_FILE.open(encoding='utf-8') as f:
            for line_idx, line in enumerate(f, 1):
                if not line.strip():
                    new_audit_lines.append(line)
                    continue
                r = json.loads(line)
                word = r.get('word', '').strip().lower()
                pos_str = r.get('pos', '').strip().lower()
                cefr = r.get('cefr', '').strip().upper()
                def_before = r.get('def_before') or ''
                
                # Check condition: do not check cards with UNCLASSIFIED or null CEFR
                if cefr == 'UNCLASSIFIED' or not cefr:
                    new_audit_lines.append(line)
                    continue
                
                # Split POS parts
                pos_parts = [p.strip() for p in pos_str.split(',') if p.strip()]
                
                # Re-simulate senses gathering (build_notes.py waterfall)
                all_senses = []
                for p in pos_parts:
                    key = (word, p, cefr)
                    if key in senses_index:
                        all_senses.extend(senses_index[key])
                    else:
                        # Fallback sibling CEFR
                        for (w, pos_val, c), senses in senses_index.items():
                            if w == word and pos_val == p:
                                all_senses.extend(senses)
                                break
                
                # Deduplicate identical texts (case-insensitive comparison)
                seen_texts = set()
                deduped_senses = []
                for s in all_senses:
                    t = (s.get('text') or '').strip()
                    if t and t.lower() not in seen_texts:
                        seen_texts.add(t.lower())
                        deduped_senses.append(t)
                
                db_sense_count = len(deduped_senses)
                
                # Split current def_before
                # The separator in def_before could be '|' or ';' (legacy)
                # Let's count definitions by checking both separators
                if '|' in def_before:
                    def_before_parts = [d.strip() for d in def_before.split('|') if d.strip()]
                else:
                    def_before_parts = [d.strip() for d in def_before.split(';') if d.strip()]
                
                built_sense_count = len(def_before_parts)
                
                # If database has more matching senses than def_before has
                if db_sense_count > built_sense_count:
                    print(f"Modifying '{word}' ({pos_str}, {cefr}): DB Senses {db_sense_count} > Built {built_sense_count}")
                    
                    # 1. Update def_before with all senses joined by '|'
                    r['def_before'] = '|'.join(deduped_senses)
                    # 2. Empty gloss_after
                    r['gloss_after'] = ''
                    # 3. Mark as modified
                    r['fix_status'] = 'expanded_needs_gloss'
                    
                    modified_records.append(r)
                    new_audit_lines.append(json.dumps(r, ensure_ascii=False))
                else:
                    new_audit_lines.append(line)
        
        # 3. Write back modified audit file
        AUDIT_FILE.write_text('\n'.join(new_audit_lines) + '\n', encoding='utf-8')
        print(f"Successfully updated {len(modified_records)} records in audit_full_deck_v2.jsonl")
        
        # 4. Write modified records to a separate file
        with OUTPUT_FILE.open('w', encoding='utf-8') as out_f:
            for r in modified_records:
                out_f.write(json.dumps(r, ensure_ascii=False) + '\n')
        print(f"Successfully wrote expanded records to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
