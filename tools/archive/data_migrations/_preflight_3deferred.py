"""Pre-flight audit for Issue 2: 3 deferred cards (tackle, trace, hook).

For each word:
- List all cards in deck with that word
- Show col14 (declared_cefr), col15 (tags), col4 (pos), col6 (senses), col7 (examples)
- Identify B2 vs C1 cards
- Show sense count per card
- Show sense text overlaps (which senses appear in multiple cards)

The merge plan: move verb senses from B2 card to C1 card, drop B2 card if empty.
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

DECK = r'English Academic Vocabulary.txt'

# 3 deferred words with their line_nos
DEFERRED = {
    'tackle': [1414, 1635, 2741, 2742, 2792],  # C1 (noun) x3, B2 (verb) x1, C1 (noun)... wait
    'trace': [1450, 1637, 2749, 2793],         # C1 (noun) x2, B2 (verb) x1
    'hook': [859, 1631, 2658, 2796],           # C1 (noun) x2, B2 (verb) x1
}

# Load deck
all_cards = []
with open(DECK, 'r', encoding='utf-8', newline='') as f:
    reader = csv.reader(f, delimiter='\t')
    for line_no, row in enumerate(reader, 1):
        if not row or row[0].startswith('#') or len(row) < 16:
            continue
        all_cards.append({
            'line_no': line_no,
            'word': row[3].strip(),
            'pos': row[4].strip(),
            'senses_raw': row[6],
            'senses': [s.strip() for s in row[6].split('|') if s.strip()],
            'col14': row[14].strip(),
            'col15': row[15],
        })

# Filter to deferred words
for word, line_nos in DEFERRED.items():
    print(f'\n{"="*80}')
    print(f'WORD: {word}')
    print(f'{"="*80}')

    word_cards = [c for c in all_cards if c['word'] == word]
    print(f'\nAll cards for {word} ({len(word_cards)}):')
    for c in word_cards:
        cefr = c['col14']
        print(f'  L{c["line_no"]:>4} [{cefr}] pos={c["pos"]:<20} n_senses={len(c["senses"])}')
        for i, s in enumerate(c['senses'], 1):
            print(f'         sense {i}: {s[:100]}{"..." if len(s) > 100 else ""}')

    # Identify B2 vs C1 cards
    b2_cards = [c for c in word_cards if c['col14'] == 'B2']
    c1_cards = [c for c in word_cards if c['col14'] == 'C1']

    print(f'\n  B2 cards: {len(b2_cards)} (will be source of verb senses to move)')
    for c in b2_cards:
        print(f'    L{c["line_no"]}: n_senses={len(c["senses"])}')

    print(f'  C1 cards: {len(c1_cards)} (will be destination of verb senses)')
    for c in c1_cards:
        print(f'    L{c["line_no"]}: n_senses={len(c["senses"])}')

    # Check sense text overlap
    def norm(s):
        s = s.strip()
        s = re.sub(r'^\s*\[[^\]]+\]\s*', '', s)
        s = re.sub(r'\bsth\.?\b', 'something', s, flags=re.IGNORECASE)
        s = re.sub(r'\bsb\.?\b', 'somebody', s, flags=re.IGNORECASE)
        s = re.sub(r'\s+', ' ', s)
        return s.rstrip('.').strip().lower()

    sense_index: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
    for c in word_cards:
        cefr = c['col14']
        for i, s in enumerate(c['senses'], 1):
            n = norm(s)
            sense_index[n].append((c['line_no'], cefr, i))

    overlaps = {n: locs for n, locs in sense_index.items() if len(locs) > 1}
    if overlaps:
        print(f'\n  Sense overlaps (same normalized text in 2+ cards):')
        for n, locs in overlaps.items():
            locs_str = ', '.join(f'L{ln}({cefr})#{i}' for ln, cefr, i in locs)
            print(f'    "{n[:80]}{"..." if len(n) > 80 else ""}" appears in: {locs_str}')

    # Specifically: what senses are in B2 that are NOT in any C1 (i.e. unique verb senses to move)
    b2_senses_norm = set()
    for c in b2_cards:
        for s in c['senses']:
            b2_senses_norm.add(norm(s))
    c1_senses_norm = set()
    for c in c1_cards:
        for s in c['senses']:
            c1_senses_norm.add(norm(s))
    unique_to_b2 = b2_senses_norm - c1_senses_norm
    if unique_to_b2:
        print(f'\n  Senses unique to B2 (these would be moved to C1):')
        for n in unique_to_b2:
            print(f'    "{n[:80]}{"..." if len(n) > 80 else ""}"')
    else:
        print(f'\n  No senses unique to B2 (all B2 senses already exist in C1)')

    shared_b2_c1 = b2_senses_norm & c1_senses_norm
    if shared_b2_c1:
        print(f'  Senses shared between B2 and C1 (do NOT duplicate):')
        for n in shared_b2_c1:
            print(f'    "{n[:80]}{"..." if len(n) > 80 else ""}"')

    # After-move sense count for each card
    print(f'\n  After-merge state (move unique B2 senses to first C1 card):')
    if c1_cards:
        c1_main = c1_cards[0]
        # Get the senses in the move plan
        new_c1_senses = list(c1_main['senses'])
        for c in b2_cards:
            for s in c['senses']:
                if norm(s) in unique_to_b2:
                    new_c1_senses.append(s)
        print(f'    L{c1_main["line_no"]} (C1) new n_senses: {len(new_c1_senses)} (was {len(c1_main["senses"])}, gain {len(new_c1_senses) - len(c1_main["senses"])})')
    for c in b2_cards:
        # After moving unique senses, what's left?
        remaining = [s for s in c['senses'] if norm(s) not in unique_to_b2]
        if remaining:
            print(f'    L{c["line_no"]} (B2) remaining senses: {len(remaining)} (move would NOT empty this card)')
            for s in remaining:
                print(f'      remain: "{s[:80]}{"..." if len(s) > 80 else ""}"')
        else:
            print(f'    L{c["line_no"]} (B2) would become empty -> tag _DELETE')
