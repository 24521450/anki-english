import os
import json
from lxml import html as lxml_html
from src.scraper.oxford import _extract_cefr, _extract_topics

PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
OXFORD_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")

def check_leaks():
    leaks = []
    count = 0
    for file in os.listdir(OXFORD_DIR):
        if not file.endswith(".html"):
            continue
        path = os.path.join(OXFORD_DIR, file)
        with open(path, "rb") as f:
            content = f.read()
        try:
            root = lxml_html.fromstring(content)
        except Exception:
            continue
        
        # Find all senses
        for sense_el in root.cssselect("li.sense, li[hclass='sense']"):
            # HTML sense CEFR
            html_cefr = sense_el.get("cefr")
            if html_cefr:
                html_cefr = html_cefr.upper()
            
            # Parsed topics CEFR
            topics = _extract_topics(sense_el)
            topic_cefrs = [t["cefr"] for t in topics if t.get("cefr")]
            
            # Parsed sense CEFR from our python extractor
            parsed_cefr = _extract_cefr(sense_el)
            
            # Check if parsed_cefr matches a topic CEFR but html_cefr is None/empty
            if html_cefr is None and parsed_cefr is not None:
                leaks.append({
                    "file": file,
                    "html_cefr": html_cefr,
                    "parsed_cefr": parsed_cefr,
                    "topic_cefrs": topic_cefrs
                })
            count += 1
            
    print(f"Checked {count} senses.")
    print(f"Found {len(leaks)} cases where html_cefr is None but parsed_cefr is not None.")
    for l in leaks[:10]:
        print(l)

if __name__ == "__main__":
    check_leaks()
