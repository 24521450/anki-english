import json
from collections import Counter

v = json.load(open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/gloss_all_verdicts.json', encoding='utf-8'))['verdicts']
lens = Counter(len(x.get('reasoning', '')) for x in v)
print('reasoning length distribution:', dict(lens))

fix_words = {'competitive', 'trigger', 'aesthetic', 'assemble', 'closure', 'depict', 'interval', 'legitimate', 'precious', 'provoke', 'seeker', 'variation', 'slam', 'monthly', 'stark', 'bat', 'firework', 'hook', 'jet', 'punk', 'radar', 'reporting', 'tackle', 'rip'}
others = [x for x in v if x.get('reasoning', '').strip() and x.get('word') not in fix_words]
print(f'others with reasoning: {len(others)}')
for x in others[:3]:
    word = x.get('word')
    reasoning = x.get('reasoning')
    print(f'  {word}: reasoning={reasoning!r}')
