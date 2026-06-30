import json
import secrets
import string
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TXT_FILE = PROJECT_ROOT / "English Academic Vocabulary.txt"
JSONL_FILE = PROJECT_ROOT / "data" / "anki_notes.jsonl"
AUDIT_FILE = PROJECT_ROOT / "data" / "audit_full_deck_v2.jsonl"

def _new_guid() -> str:
    """Generate a 10-char alphanumeric GUID in Anki's style."""
    alphabet = string.ascii_letters + string.digits + '!#%&()*+,-./:;<=>?@[]^_`{|}~'
    return ''.join(secrets.choice(alphabet) for _ in range(10))

def main():
    print("=== Splitting 'firm' Card ===")
    
    # 1. Generate new GUID for the noun card
    new_guid = _new_guid()
    print(f"Generated new GUID for noun card: {new_guid}")
    
    # 2. Modify English Academic Vocabulary.txt
    if TXT_FILE.exists():
        lines = TXT_FILE.read_text(encoding='utf-8').splitlines()
        new_lines = []
        found = False
        for line in lines:
            if not line.strip():
                new_lines.append(line)
                continue
            parts = line.split('\t')
            if len(parts) >= 15 and parts[3] == 'firm' and parts[4] == 'adjective, noun':
                found = True
                print("Found 'firm' in TXT file. Splitting...")
                
                # Card 1: adjective
                # guid, notetype, deck, word, pos, ipa, defn, ex, coll, wf, uk, us, src1, src2, cefr, idioms, tags
                adj_parts = list(parts)
                adj_parts[4] = 'adjective'
                adj_parts[6] = 'solid or hard | unlikely to change | strongly fixed'
                # Keep original example, idioms
                adj_parts[16] = 'Source::Oxford CEFR::B2 CEFR::oxford Oxford_5000 idioms'
                new_lines.append('\t'.join(adj_parts))
                
                # Card 2: noun
                noun_parts = list(parts)
                noun_parts[0] = new_guid
                noun_parts[4] = 'noun'
                noun_parts[6] = 'business or company'
                noun_parts[7] = ''  # empty example, will be populated by build script
                if len(noun_parts) > 15:
                    noun_parts[15] = ''  # empty idioms
                    noun_parts[16] = 'Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000'
                else:
                    noun_parts[15] = 'Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000'
                new_lines.append('\t'.join(noun_parts))
            else:
                new_lines.append(line)
        
        if found:
            TXT_FILE.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
            print("Successfully updated TXT file.")
        else:
            print("Warning: 'firm' (adjective, noun) not found in TXT file.")

    # 3. Modify data/anki_notes.jsonl
    if JSONL_FILE.exists():
        lines = JSONL_FILE.read_text(encoding='utf-8').splitlines()
        new_lines = []
        found = False
        for line in lines:
            if not line.strip():
                new_lines.append(line)
                continue
            r = json.loads(line)
            if r.get('word') == 'firm' and r.get('pos') == 'adjective, noun':
                found = True
                print("Found 'firm' in JSONL file. Splitting...")
                
                # Card 1: adjective
                adj_card = dict(r)
                adj_card['pos'] = 'adjective'
                adj_card['definition'] = 'solid or hard | unlikely to change | strongly fixed'
                adj_card['tags'] = 'Source::Oxford CEFR::B2 CEFR::oxford Oxford_5000 idioms'
                new_lines.append(json.dumps(adj_card, ensure_ascii=False))
                
                # Card 2: noun
                noun_card = dict(r)
                noun_card['guid'] = new_guid
                noun_card['pos'] = 'noun'
                noun_card['definition'] = 'business or company'
                noun_card['example'] = ''
                noun_card['idioms'] = ''
                noun_card['tags'] = 'Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000'
                new_lines.append(json.dumps(noun_card, ensure_ascii=False))
            else:
                new_lines.append(line)
                
        if found:
            JSONL_FILE.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
            print("Successfully updated JSONL file.")
        else:
            print("Warning: 'firm' (adjective, noun) not found in JSONL file.")

    # 4. Modify data/audit_full_deck_v2.jsonl
    if AUDIT_FILE.exists():
        lines = AUDIT_FILE.read_text(encoding='utf-8').splitlines()
        new_lines = []
        found = False
        for line in lines:
            if not line.strip():
                new_lines.append(line)
                continue
            r = json.loads(line)
            if r.get('word') == 'firm' and r.get('pos') == 'adjective, noun':
                found = True
                print("Found 'firm' in AUDIT file. Splitting...")
                
                # Entry 1: adjective
                adj_entry = {
                    "word": "firm",
                    "pos": "adjective",
                    "cefr": "B2",
                    "def_before": "fairly hard; not easy to press into a different shape|not likely to change|strongly fixed in place",
                    "gloss_after": "solid or hard | unlikely to change | strongly fixed",
                    "separator": "none",
                    "rule_applied": None,
                    "gloss_word_count": 9,
                    "gate_status": "pass",
                    "source": "rerun_v2_streamA",
                    "fix_status": "rebuilt"
                }
                new_lines.append(json.dumps(adj_entry, ensure_ascii=False))
                
                # Entry 2: noun
                noun_entry = {
                    "word": "firm",
                    "pos": "noun",
                    "cefr": "B2",
                    "def_before": "a business or company",
                    "gloss_after": "business or company",
                    "separator": "none",
                    "rule_applied": None,
                    "gloss_word_count": 3,
                    "gate_status": "pass",
                    "source": "rerun_v2_streamA",
                    "fix_status": "rebuilt"
                }
                new_lines.append(json.dumps(noun_entry, ensure_ascii=False))
            else:
                new_lines.append(line)
                
        if found:
            AUDIT_FILE.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
            print("Successfully updated AUDIT file.")
        else:
            print("Warning: 'firm' (adjective, noun) not found in AUDIT file.")

if __name__ == '__main__':
    main()
