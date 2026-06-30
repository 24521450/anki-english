import lxml.html as LH
with open(r'C:\Users\admin\Downloads\ankideck/data/.cache_html/oxford/oxford_accordance_(noun).html', 'rb') as f:
    html = f.read()
root = LH.fromstring(html)

# Find all ol.sense_single
ols = root.cssselect("ol.sense_single")
print(f'sense_single ols: {len(ols)}')
for ol in ols:
    p = ol.getparent()
    if p is not None:
        cls = p.get("class") or ""
        tag = p.tag
        print(f'  parent: <{tag} class="{cls}">')
        # Check ancestor for idm-g
        gp = p.getparent()
        if gp is not None:
            print(f'  grandparent: <{gp.tag} class="{gp.get("class") or ""}">')
