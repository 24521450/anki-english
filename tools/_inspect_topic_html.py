import os
from lxml import html as lxml_html

PROJECT_ROOT = r"C:\Users\admin\Downloads\ankideck"
OXFORD_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")

def inspect_file(filename):
    path = os.path.join(OXFORD_DIR, filename)
    if not os.path.exists(path):
        print(f"Not found: {filename}")
        return
    with open(path, "rb") as f:
        content = f.read()
    root = lxml_html.fromstring(content)
    
    # Let's find span.topic-g and print their HTML snippet
    topic_gs = root.cssselect("span.topic-g")
    print(f"\n=== Inspecting {filename} ({len(topic_gs)} span.topic-g elements) ===")
    for i, tg in enumerate(topic_gs, 1):
        html_str = lxml_html.tostring(tg, encoding="utf-8").decode("utf-8")
        print(f"\n[{i}] Element outer HTML:\n{html_str}")
        
        # Also print the children
        children = list(tg)
        print("Children tags & classes:")
        for c in children:
            print(f"  <{c.tag} class='{c.get('class', '')}'> Text: {c.text!r} Tail: {c.tail!r}")

inspect_file("oxford_TV.html")
inspect_file("oxford_academic_(adj).html")
inspect_file("oxford_accident_(noun).html")
