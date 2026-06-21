"""Count Anki cards in txt file (handle multi-line fields properly)."""
import re

with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    raw = f.read()

# Skip comment lines starting with #
# Card rows start with a GUID column 0 (an Anki GUID is 10 alphanumeric+special chars)
# Anki txt format: each line is tab-separated; if field contains \n, it's an actual newline
# A card is a SINGLE LINE in the file, but fields can contain HTML <br> for newlines

lines = raw.split('\n')
n_total_lines = len(lines)
n_noncomment = sum(1 for l in lines if l and not l.startswith('#'))
n_cards = sum(1 for l in lines if l and not l.startswith('#'))

# Look for the pattern of a card row: starts with a quoted-string GUID like "abc123"
guid_pattern = re.compile(r'^"[^"]+"\tEnglish Academic Vocabulary')
n_by_guid = sum(1 for l in lines if guid_pattern.match(l))

print(f'Total lines: {n_total_lines}')
print(f'Non-comment lines: {n_noncomment}')
print(f'Lines matching card pattern (starts with "GUID"\\tEnglish...): {n_by_guid}')

# So if my count is 2,479, the 2,528 might be a different deck export.
# Look for any other txt files in the project
import os
for root, dirs, files in os.walk(r'C:\Users\admin\Downloads\ankideck'):
    for f in files:
        if f.endswith('.txt') and 'vocabul' in f.lower() or 'anki' in f.lower() or 'card' in f.lower():
            p = os.path.join(root, f)
            size = os.path.getsize(p)
            print(f'  found: {p} ({size} bytes)')

# Also check for any backup
for f in os.listdir(r'C:\Users\admin\Downloads\ankideck'):
    if f.endswith('.txt') and ('backup' in f.lower() or 'anki' in f.lower()):
        print(f'  backup: {f}')

# Check for collection files
for f in os.listdir(r'C:\Users\admin\Downloads\ankideck'):
    if 'collection' in f.lower() or 'anki2' in f.lower():
        print(f'  anki file: {f}')
