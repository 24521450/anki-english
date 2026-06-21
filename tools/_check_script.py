import re
text = open(r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py', encoding='utf-8').read()
m = re.search(r"    'bug\|noun\|B2':.*?\n", text)
if m:
    print('FOUND:', repr(m.group(0)))
else:
    print('NOT FOUND')
m = re.search(r'    # \.\.\. continues for all 258 multi-sense-3\+\n\}', text)
if m:
    print('END:', repr(m.group(0)))
else:
    print('END NOT FOUND')
