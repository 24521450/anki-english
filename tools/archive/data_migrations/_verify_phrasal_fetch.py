"""Verify fetched phrasal verb HTML has senses."""
import lxml.html

for f in ["oxford_devote-to_(phrasal_verb).html", "oxford_rely-on_(phrasal_verb).html"]:
    path = rf"C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\{f}"
    with open(path, "rb") as fh:
        tree = lxml.html.fromstring(fh.read())
    hw = tree.cssselect("h1.headword")
    pos = tree.cssselect("span.pos")
    ol_sm = tree.cssselect("ol.senses_multiple")
    ol_ss = tree.cssselect("ol.sense_single")
    li_sel = 'li.sense, li[hclass="sense"]'
    li_sense = tree.cssselect(li_sel)
    print(f"{f}:")
    print(f"  headword: {hw[0].text_content() if hw else None}")
    print(f"  pos: {[p.text_content() for p in pos[:3]]}")
    print(f"  ol.senses_multiple: {len(ol_sm)}, ol.sense_single: {len(ol_ss)}")
    print(f"  li.sense: {len(li_sense)}")
