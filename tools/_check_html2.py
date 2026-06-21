import re
with open(r'C:\Users\admin\Downloads\ankideck/data/.cache_html/oxford/oxford_accordance_(noun).html', encoding='utf-8') as f:
    html = f.read()

pos_g_count = html.count('<pos-g')
print(f'pos-g count: {pos_g_count}')

ol_count = html.count('senses_multiple')
print(f'senses_multiple count: {ol_count}')

ol_single = html.count('sense_single')
print(f'sense_single count: {ol_single}')

# Find context around pos-g
i = 0
for n in range(3):
    j = html.find('<pos-g', i)
    if j < 0:
        break
    print(f'pos-g #{n} at {j}: {html[j:j+200]!r}')
    print()
    i = j + 10
