"""Manually add pace|noun|B2 row to txt, with new GUID.

The build stage (build_notes.py) only updates existing rows, doesn't add new
ones. Since pace is a new word from this scrape, we need to manually insert
the row. After this, apply_glosses_to_txt will replace the def with the
gloss "speed".
"""
import random
import string

# Generate a random GUID like other entries (10-char alphanumeric+special)
chars = string.ascii_letters + string.digits + '!@#$%^&*()_+-={}[]|:;<>,.?/'
new_guid = ''.join(random.choice(chars) for _ in range(10))

# Pace|noun|B2 row — 16 fields (matches existing schema)
# 0: GUID, 1: NoteType, 2: Deck, 3: Word, 4: POS, 5: empty, 6: Def, 7: Example, 8-9: empty
# 10-11: UK/US audio, 12-13: source, 14: CEFR, 15: Tags

# Use the Oxford defs from the cache (first 2 B2 senses joined by |)
def_text = 'the speed at which somebody/something walks, runs or moves|the speed at which something happens'
example_text = 'She finished the race at a walking pace.|News of the strike spread at a remarkable pace.'

new_row = '\t'.join([
    new_guid,
    'English Academic Vocabulary Model',
    'English Academic Vocabulary::Oxford',
    'pace',
    'noun',
    '',                          # col 5 empty
    def_text,                    # col 6 def (will be replaced with gloss "speed" by apply)
    example_text,                # col 7 example
    '',                          # col 8
    '',                          # col 9
    '[sound:cambridge_uk_pace.mp3]',
    '[sound:cambridge_us_pace.mp3]',
    'Oxford',
    'Oxford',
    'B2',
    'Source::Oxford CEFR::B2 CEFR::oxford Oxford_3000',
]) + '\n'

print(f'New row:')
print(f'  GUID: {new_guid}')
print(f'  Word: pace')
print(f'  POS: noun')
print(f'  CEFR: B2')
print(f'  Def (initial): {def_text[:80]}')
print(f'  Will be replaced with gloss "speed" after apply')

# Append to txt
path = r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt'
with open(path, 'a', encoding='utf-8') as f:
    f.write(new_row)
print(f'\nAppended to {path}')
