with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

n_total = 0
malformed = 0
delete_tag = 0
malformed_examples = []
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    n_total += 1
    p = l.split('\t')
    if len(p) < 15:
        malformed += 1
        if len(malformed_examples) < 3:
            malformed_examples.append(l[:100])
        continue
    tags = p[15] if len(p) > 15 else ''
    if 'delete' in tags.split():
        delete_tag += 1

print(f'total non-comment: {n_total}')
print(f'malformed (len < 15): {malformed}')
for ex in malformed_examples:
    print(f'  example: {ex}')
print(f'delete tagged: {delete_tag}')
print(f'expected audit count: {n_total} - {malformed} - {delete_tag} = {n_total - malformed - delete_tag}')
