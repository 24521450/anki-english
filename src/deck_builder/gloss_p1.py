"""P1 semantic gloss fixer.

Per user plan (2026-06-21, "P1 Semantic Gloss Cleanup"):

Fixes bad glosses (after P0 hygiene) so they pass ``validate_verdict()``:

  - total words: 1-6
  - '|' chunks: 1-4 words each
  - ';' chunks: 1-3 words each
  - no headword in chunk
  - no morphological near-self
  - no visible POS labels like 'noun:' / 'verb:'

Strategy (in order):

  1. Strip POS labels from chunks (mechanical regex)
  2. Apply per-(word,pos,cefr) FIXES override (manual decisions)
  3. Apply morphological_variant replacements (per-word lookup)
  4. Apply headword_in_definition replacements (per-word lookup)
  5. Heuristic shortening: pick first N content words per chunk
  6. Heuristic shortening: drop redundant chunks (3+ -> 2)

Each step re-validates. If still failing, mark for manual override.

Not in scope:
  - 5 duplicate (word,pos,cefr) keys (P2)
  - Adding new senses not already in current_gloss or def_before
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = paths.root
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.gloss_hygiene import normalize_gloss  # noqa: E402
from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

POS_LABEL_RE = re.compile(
    r'(?:^|(?<=[|;]))'
    r'(?:'
    r'noun|verb|adjective|adverb|adj|adv|'
    r'preposition|prep|pronoun|determiner|conjunction|'
    r'exclamation|modal|auxiliary|phrasal verb|'
    r'(?:noun|verb|adjective|adverb|adj|adv)\s*/\s*'
    r'(?:noun|verb|adjective|adverb|adj|adv)'
    r')\s*:',
    re.IGNORECASE,
)

# Stop words (won't be picked by "first content word" heuristic).
# Note: 'not', 'no', and 'to' are excluded to prevent dropping semantic words.
STOP_WORDS = frozenset({
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'for', 'and', 'or', 'but',
    'with', 'by', 'is', 'are', 'be', 'as', 'that', 'this', 'it', 'its',
    'or', 'if', 'so', 'do', 'does', 'did',
})

NEGATIONS = frozenset({
    'not', 'no', 'never', 'neither', 'nor', 'without', 'except', 'non',
    'unlikely', 'unable', 'unwilling', 'cannot'
})

VAGUE_WORDS = frozenset({
    'heavy', 'light', 'big', 'small', 'large', 'tiny', 'huge',
    'good', 'bad', 'new', 'old', 'great', 'high', 'low',
    'main', 'major', 'minor', 'short', 'long', 'quick', 'slow',
    'easy', 'hard', 'soft', 'strong', 'weak', 'hot', 'cold',
    'come', 'go', 'make', 'take', 'get', 'give', 'keep', 'let',
    'thing', 'things', 'person', 'people', 'someone', 'something',
    'way', 'place', 'time', 'part', 'parts',
})


def contains_negation(text: str) -> bool:
    words = re.findall(r'\b\w+\b', text.lower())
    return any(w in NEGATIONS for w in words)


def strip_pos_labels(gloss: str) -> str:
    r"""Strip 'POS:' prefixes from chunks.

    Removes the entire ``(^|[|;])POS:`` group including the colon.
    After this, the surrounding ``|`` and ``;`` separators stay compact
    (the lookbehind doesn't consume them).
    """
    out = POS_LABEL_RE.sub('', gloss)
    # Re-tighten pipe/semi spacing (in case POS label strip left extra space).
    out = re.sub(r'\s*\|\s*', '|', out)
    out = re.sub(r'\s*;\s*', ';', out)
    return out.strip()


def chunk_count(g: str) -> int:
    return len([c for c in re.split(r'\s*[|;]\s*', g.strip()) if c.strip()])


def is_valid(word: str, gloss: str) -> bool:
    """Returns True if gloss passes validator + no POS label."""
    res = normalize_gloss(gloss)
    has_pos = bool(POS_LABEL_RE.search(res.gloss))
    if has_pos:
        return False

    # Forbid duplicate chunks
    sep = res.separator
    if sep != 'none':
        sides = [s.strip().lower() for s in res.gloss.split(sep) if s.strip()]
        if len(sides) != len(set(sides)):
            return False

    # Forbid low-content/vague single-word chunks
    chunks = res.gloss.split(sep) if sep != 'none' else [res.gloss]
    for c in chunks:
        c_words = [w.lower().strip('.,;:!?()') for w in c.split() if w.strip()]
        if len(c_words) == 1 and c_words[0] in VAGUE_WORDS:
            return False

    v = validate_verdict(word, res.gloss, res.separator, chunk_count(res.gloss))
    return not v


def shorten_chunk(chunk: str, max_words: int) -> str:
    """Reduce a chunk to <= max_words content words.

    Strategy:
      1. Strip trailing punctuation, parens, etc.
      2. Remove stopwords (always, even when under limit)
      3. Truncate to max_words

    If we end up with fewer than 1 word, keep at least 1 (the first).
    """
    chunk = chunk.strip()
    # Remove parenthetical remarks: 'sudden surge (of something bad)' -> 'sudden surge'
    chunk = re.sub(r'\s*\([^)]*\)\s*', ' ', chunk).strip()

    words = chunk.split()
    # Filter out stopwords (always — cleanest gloss first).
    content = [w for w in words if w.lower().strip('.,;:') not in STOP_WORDS]
    if not content:
        shortened = words[0] if words else chunk  # all stopwords; keep first
    elif len(content) <= max_words:
        shortened = ' '.join(content)
    else:
        shortened = ' '.join(content[:max_words])

    # Negation loss guard
    if contains_negation(chunk) and not contains_negation(shortened):
        return chunk  # Return original to fail validation and force manual override
    return shortened


def shorten_gloss(gloss: str, def_before: str = '') -> str:
    """Shorten a gloss to fit validator limits.

    Rules:
      - '|' separator: max 4 words per side, max 2 sides
      - ';' separator: max 3 words per side, max 2 sides
      - no separator: max 6 words total
    """
    res = normalize_gloss(gloss)
    g = res.gloss

    if '|' in g:
        sides = g.split('|')
        sides = [shorten_chunk(s, 3) for s in sides]
        # Deduplicate
        seen = []
        for s in sides:
            s_clean = s.strip().lower()
            if s_clean not in [x.strip().lower() for x in seen]:
                seen.append(s)
        sides = seen
        # Drop redundant chunks beyond 2
        if len(sides) > 2:
            sides = sides[:2]
        return '|'.join(sides)
    elif ';' in g:
        sides = g.split(';')
        sides = [shorten_chunk(s, 3) for s in sides]
        # Deduplicate
        seen = []
        for s in sides:
            s_clean = s.strip().lower()
            if s_clean not in [x.strip().lower() for x in seen]:
                seen.append(s)
        sides = seen
        if len(sides) > 2:
            sides = sides[:2]
        return ';'.join(sides)
    else:
        return shorten_chunk(g, 6)


# ============================================================================
# Per-word synonym / replacement maps
# ============================================================================
# These are hand-curated for cases where the validator flags
# morphological_variant or headword_in_definition.

# Single-word gloss replacements (for morphological_variant cases).
# Map: headword -> {current_word: replacement}
MORPHOLOGICAL_REPLACEMENTS = {
    'generic': {'general': 'broad'},
    'intent': {'intention': 'purpose'},
    'limitation': {'limit': 'constraint'},
    'line-up': {'lineup': 'roster'},
    'listing': {'list': 'directory'},
    'ranking': {'rank': 'standing'},
    'acid': {'acidic': 'sour'},
}

# Multi-word chunk replacements (for headword_in_definition).
# Map: headword -> {chunk: replacement}
HEADWORD_CHUNK_REPLACEMENTS = {
    'domain': {
        'field of activity': 'field of activity',
        'internet domain name': 'web address',
    },
    'hip': {
        'hip joint': 'leg joint',
        'side of the body at the waist': 'waist side',
    },
    'installation': {
        'setup': 'setup',
        'large installed equipment': 'large equipment',
        'art installation': 'art display',
    },
    'margin': {
        'page edge': 'page edge',
        'difference between amounts (profit/win)': 'profit difference',
        'margin of error': 'error tolerance',
    },
    'passive': {
        'not taking action': 'not taking action',
        'relating to passive voice (grammar)': 'about grammar voice',
    },
    'rocket': {
        'vehicle or weapon propelled by jet thrust': 'jet-propelled craft',
        'firework rocket': 'firework',
    },
    'cult': {
        'noun: devoted following or extreme religious group': 'devoted following',
        'adj: having a cult following': 'having devoted fans',
    },
    'filter': {
        'a device that removes unwanted substances from liquid or light': 'purification device',
        'to pass through a filter': 'to strain',
        'a setting that limits what you see': 'content filter',
    },
    'gear': {
        'vehicle gear mechanism': 'transmission part',
        'equipment for a particular activity': 'equipment',
    },
    'operator': {
        'a person who controls a machine': 'machine operator',
        'a company that runs a business': 'business operator',
        'a telephone operator': 'phone operator',
    },
    'cult': {
        'noun: devoted following or extreme religious group': 'devoted following',
        'adj: having a cult following': 'having devoted fans',
    },
    'reverse': {
        'adj: opposite': 'opposite',
        'noun: the opposite': 'the opposite',
        'reverse gear': 'reverse gear',
        'verb: go backwards': 'go backwards',
        'change to opposite': 'reverse',
    },
    'rail': {
        'metal bar as barrier or support': 'metal bar',
        'railway (travel by rail)': 'railway',
    },
    'spin': {
        'noun: fast turning motion': 'fast rotation',
        'biased presentation of information': 'biased account',
        'verb: rotate fast': 'rotate fast',
        'put spin on': 'add spin',
    },
    'screw': {
        'noun: metal fastener with spiral thread': 'threaded fastener',
        'verb: fasten with a screw': 'fasten with screw',
        'twist to tighten': 'twist to tighten',
    },
    'whip': {
        'strike with a whip': 'strike',
        'move suddenly': 'move suddenly',
    },
    'cult': {
        'noun: devoted following or extreme religious group': 'devoted following',
        'adj: having a cult following': 'having devoted fans',
    },
    'pump': {
        'a device that forces liquid or gas through a pipe': 'liquid pump',
        'to move liquid or gas using a pump': 'to pump',
    },
    'passing': {
        'the passage of time': 'passage',
        "somebody's death (polite)": 'death',
        'the passing of a law': 'law enactment',
    },
}

# Per-(word,pos,cefr) explicit FIXES map. Applied before heuristics.
# Use these when neither regex nor heuristic can produce a valid gloss.
# Keys: (word, pos, cefr) tuple. Values: dict with 'gloss' field.
EXPLICIT_FIXES = {
    # Multi-sense 3+ collapses — pick 1 best gloss
    ('absence', 'noun', 'C1'): 'being away',
    ('abuse', 'noun, verb', 'C1'): 'mistreatment',
    ('acceptance', 'noun', 'C1'): 'willingness',
    ('adapt', 'verb', 'B2'): 'adjust behavior|modify for new use',
    ('admission', 'noun', 'C1'): 'right to enter|confession',
    ('aesthetic', 'adjective', 'C1'): 'relating to beauty and art',
    ('acid', 'adjective', 'C1'): 'sour',
    ('acute', 'adjective', 'C1'): 'very serious',
    ('alien', 'adjective', 'C1'): 'foreign',
    ('alert', 'adjective, noun, verb', 'C1'): 'watchful|warning',
    ('amateur', 'adjective, noun', 'C1'): 'non-professional',
    ('anchor', 'noun', 'C1'): 'heavy weight for ships|TV/radio host',
    ('altogether', 'adverb', 'B2'): 'completely',
    ('animation', 'noun', 'B2'): 'moving images',
    ('anticipate', 'verb', 'B2'): 'expect',
    ('appreciate', 'verb', 'C1'): 'value',  # not in list; skip
    ('appreciation', 'noun', 'C1'): 'gratitude',
    ('assault', 'noun, verb', 'C1'): 'violent attack',
    ('assemble', 'verb', 'C1'): 'gather together|fit parts together',
    ('assembly', 'noun', 'C1'): 'gathering',
    ('attribute', 'noun, verb', 'C1'): 'quality',
    ('availability', 'noun', 'C1'): 'accessibility',
    ('bare', 'adjective', 'C1'): 'uncovered',
    ('betray', 'verb', 'C1'): 'be disloyal',
    ('bid', 'noun, verb', 'B2'): 'offer',
    ('blast', 'noun, verb', 'C1'): 'explosion|blow up',
    ('blend', 'noun, verb', 'C1'): 'mixture',
    ('blessing', 'noun', 'C1'): 'approval',
    ('boost', 'noun, verb', 'B2'): 'increase',
    ('bow', 'noun, verb', 'C1'): 'bend forward',
    ('breach', 'noun, verb', 'C1'): 'violation',
    ('breakdown', 'noun', 'C1'): 'failure',
    ('breed', 'noun, verb', 'C1'): 'animal type',
    ('briefly', 'adverb', 'B2'): 'for a short time',
    ('bug', 'noun', 'B2'): 'insect',
    ('bulk', 'noun', 'C1'): 'main part',
    ('byproducts', 'noun', 'UNCLASSIFIED'): 'secondary product',
    ('cheer', 'noun, verb', 'B2'): 'shout joy',
    ('chronic', 'adjective', 'C1'): 'long-lasting',
    ('circulation', 'noun', 'C1'): 'flow',
    ('civilization', 'noun', 'B2'): 'society',
    ('clerk', 'noun', 'B2'): 'office worker',
    ('closure', 'noun', 'C1'): 'shutdown',
    ('cluster', 'noun', 'C1'): 'group',
    ('compelling', 'adjective', 'C1'): 'convincing',
    ('compensation', 'noun', 'C1'): 'payment',
    ('complement', 'verb', 'C1'): 'go well with',
    ('compromise', 'noun, verb', 'C1'): 'agreement',
    ('conceive', 'verb', 'C1'): 'imagine',
    ('confront', 'verb', 'C1'): 'face',
    ('consultation', 'noun', 'C1'): 'meeting',
    ('contemplate', 'verb', 'C1'): 'consider',
    ('converse', 'adjective, noun', 'UNCLASSIFIED'): 'opposite',
    ('correspondence', 'noun', 'C1'): 'letters',
    ('coup', 'noun', 'C1'): 'takeover',
    ('crack', 'noun, verb', 'B2'): 'break',
    ('crown', 'noun', 'C1'): 'royal headpiece',
    ('cult', 'adjective, noun', 'C1'): 'devoted following',
    ('curious', 'adjective', 'B2'): 'inquisitive',
    ('dairy', 'adjective, noun', 'B2'): 'milk product',
    ('decisive', 'adjective', 'C1'): 'resolute',
    ('defensive', 'adjective', 'C1'): 'protective',
    ('defy', 'verb', 'C1'): 'resist',
    ('democratic', 'adjective', 'B2'): 'elected',
    ('deployment', 'noun', 'C1'): 'positioning',
    ('deposit', 'noun', 'C1'): 'money in bank|underground layer',
    ('deposit', 'noun, verb', 'C1'): 'payment',
    ('differentiate', 'verb', 'C1'): 'distinguish',
    ('dimension', 'noun', 'C1'): 'measurement',
    ('disclosure', 'noun', 'C1'): 'revelation',
    ('disconnect', 'verb', 'C1'): 'detach',
    ('dispute', 'noun, verb', 'C1'): 'argument',
    ('distinct', 'adjective', 'B2'): 'different',
    ('distress', 'noun, verb', 'C1'): 'suffering',
    ('distribution', 'noun', 'B2'): 'delivery',
    ('dive', 'noun, verb', 'B2'): 'jump',
    ('divorce', 'noun, verb', 'B2'): 'marriage end',
    ('domain', 'noun', 'C1'): 'field',
    ('domestic', 'adjective', 'B2'): 'household',
    ('dramatic', 'adjective', 'B2'): 'sudden',
    ('ease', 'noun, verb', 'C1'): 'lack of difficulty',
    ('echo', 'noun, verb', 'C1'): 'repeated sound',
    ('efficient', 'adjective', 'B2'): 'effective',
    ('empower', 'verb', 'C1'): 'authorize',
    ('engagement', 'noun', 'C1'): 'agreement',
    ('epidemic', 'noun', 'C1'): 'outbreak',
    ('equation', 'noun', 'C1'): 'math statement',
    ('establishment', 'noun', 'C1'): 'institution',
    ('eventual', 'adjective', 'C1'): 'final',
    ('excess', 'adjective, noun', 'C1'): 'surplus',
    ('exclusive', 'adjective', 'C1'): 'limited',
    ('exploitation', 'noun', 'C1'): 'unfair use',
    ('expose', 'verb', 'B2'): 'reveal',
    ('extend', 'verb', 'B2'): 'lengthen',
    ('fibre', 'noun', 'C1'): 'thread',
    ('filter', 'noun, verb', 'C1'): 'strainer',
    ('firm', 'adjective', 'B2'): 'solid|unlikely to change',
    ('firm', 'adjective, noun, verb', 'B2'): 'solid',
    ('forge', 'verb', 'C1'): 'fake copy',
    ('formula', 'noun', 'C1'): 'recipe',
    ('foundation', 'noun', 'B2'): 'basis',
    ('freely', 'adverb', 'B2'): 'openly',
    ('frustration', 'noun', 'C1'): 'annoyance',
    ('fulfil', 'verb', 'B2'): 'achieve',
    ('gear', 'noun', 'C1'): 'equipment',
    ('generic', 'adjective', 'C1'): 'broad',
    ('glory', 'noun', 'C1'): 'fame',
    ('goodness', 'noun', 'B2'): 'morality',
    ('grasp', 'noun, verb', 'C1'): 'hold',
    ('grid', 'noun', 'C1'): 'network',
    ('grip', 'noun, verb', 'C1'): 'hold',
    ('gross', 'adjective', 'C1'): 'total',
    ('guilt', 'noun', 'C1'): 'blame',
    ('harassment', 'noun', 'C1'): 'bullying',
    ('harmony', 'noun', 'C1'): 'agreement',
    ('harsh', 'adjective', 'C1'): 'severe',
    ('harvest', 'noun, verb', 'C1'): 'crop gathering',
    ('haunt', 'verb', 'C1'): 'trouble',
    ('heal', 'verb', 'B2'): 'cure',
    ('hint', 'noun, verb', 'C1'): 'suggestion',
    ('hip', 'noun', 'B2'): 'body side',
    ('horizon', 'noun', 'C1'): 'skyline',
    ('hostile', 'adjective', 'C1'): 'unfriendly',
    ('identification', 'noun', 'C1'): 'ID',
    ('ignorant', 'adjective', 'UNCLASSIFIED'): 'uninformed',
    ('illusion', 'noun', 'B2'): 'false belief',
    ('impulse', 'noun', 'UNCLASSIFIED'): 'urge',
    ('inclined', 'adjective', 'C1'): 'tending',
    ('inflammation', 'noun', 'C2'): 'swelling',
    ('installation', 'noun', 'B2'): 'setup',
    ('integrate', 'verb', 'B2'): 'combine',
    ('integrated', 'adjective', 'C1'): 'combined',
    ('intent', 'noun', 'C1'): 'purpose',
    ('interface', 'noun', 'C1'): 'connection',
    ('intervention', 'noun', 'C1'): 'interference',
    ('invoke', 'verb', 'C1'): 'cite',
    ('irony', 'noun', 'C1'): 'opposite result',
    ('isolated', 'adjective', 'B2'): 'alone',
    ('landing', 'noun', 'B2'): 'touchdown',
    ('landlord', 'noun', 'C1'): 'property owner',
    ('landmark', 'noun', 'C1'): 'reference point',
    ('lane', 'noun', 'B2'): 'path',
    ('lap', 'noun', 'C1'): 'top of thighs',
    ('latter', 'adjective, noun', 'C1'): 'second',
    ('leak', 'noun, verb', 'C1'): 'escape',
    ('leap', 'noun, verb', 'C1'): 'jump',
    ('legend', 'noun', 'B2'): 'myth',
    ('leverage', 'verb', 'C2'): 'use advantage',
    ('liberal', 'adjective, noun', 'C1'): 'open-minded',
    ('limitation', 'noun', 'B2'): 'constraint',
    ('line-up', 'noun', 'C1'): 'roster',
    ('linger', 'verb', 'C1'): 'stay',
    ('listing', 'noun', 'C1'): 'directory',
    ('lobby', 'noun, verb', 'C1'): 'entrance hall',
    ('log', 'noun, verb', 'C1'): 'record',
    ('loom', 'verb', 'C1'): 'impend',
    ('mainland', 'adjective', 'UNCLASSIFIED'): 'main land',
    ('mandate', 'noun', 'C1'): 'authority',
    ('manipulation', 'noun', 'C1'): 'control',
    ('march', 'noun, verb', 'C1'): 'walk',
    ('margin', 'noun', 'B2'): 'edge',
    ('mate', 'noun, verb', 'B2'): 'partner',
    ('mature', 'adjective, verb', 'C1'): 'grown up',
    ('maximize', 'verb', 'C1'): 'increase',
    ('mechanism', 'noun', 'B2'): 'machinery parts',
    ('memoir', 'noun', 'C1'): 'autobiography',
    ('mere', 'adjective', 'C1'): 'minor',
    ('metaphor', 'noun', 'B2'): 'figure of speech',
    ('migrate', 'verb', 'B2'): 'move',
    ('migrate', 'verb', 'C1'): 'move',
    ('migration', 'noun', 'C1'): 'movement',
    ('militant', 'adjective, noun', 'C1'): 'activist',
    ('minimize', 'verb', 'C1'): 'reduce',
    ('mobility', 'noun', 'C1'): 'movement',
    ('modest', 'adjective', 'B2'): 'humble',
    ('momentum', 'noun', 'C1'): 'impetus',
    ('mortality', 'noun', 'UNCLASSIFIED'): 'death rate',
    ('motion', 'noun', 'B2'): 'movement',
    ('narrative', 'noun', 'B1'): 'story',
    ('navigate', 'verb', 'B2'): 'find way',
    ('navigate', 'verb', 'C1'): 'find way',
    ('neglect', 'noun, verb', 'C1'): 'disregard',
    ('nerve', 'noun', 'B2'): 'fiber',
    ('niche', 'noun', 'C1'): 'specialty',
    ('nursery', 'noun', 'C1'): 'childcare',
    ('oblivion', 'noun', 'UNCLASSIFIED'): 'forgetfulness',
    ('occupation', 'noun', 'B2'): 'job',
    ('occupy', 'verb', 'B2'): 'take up',
    ('operator', 'noun', 'B2'): 'worker',
    ('organic', 'adjective', 'B2'): 'natural',
    ('orientation', 'noun', 'C1'): 'direction',
    ('outlet', 'noun', 'C1'): 'store',
    ('outlook', 'noun', 'C1'): 'attitude',
    ('outrage', 'noun, verb', 'C1'): 'anger',
    ('outstanding', 'adjective', 'B2'): 'excellent',
    ('overlook', 'verb', 'C1'): 'miss',
    ('overwhelm', 'verb', 'C1'): 'overcome',
    ('parallel', 'adjective, noun', 'B2'): 'similar',
    ('part-time', 'adjective, adverb', 'B2'): 'not full-time',
    ('passing', 'noun', 'C1'): 'passage',
    ('passive', 'adjective', 'C1'): 'inactive',
    ('patrol', 'noun, verb', 'C1'): 'guard',
    ('peak', 'noun', 'C1'): 'summit',
    ('perceive', 'verb', 'B2'): 'sense',
    ('persistent', 'adjective', 'C1'): 'continuing',
    ('phenomenon', 'noun', 'B2'): 'event',
    ('philosophy', 'noun', 'B2'): 'belief',
    ('pile', 'noun, verb', 'B2'): 'stack',
    ('pipeline', 'noun', 'C1'): 'channel',
    ('pirate', 'noun', 'C1'): 'sea thief',
    ('plead', 'verb', 'C1'): 'beg',
    ('plug', 'noun, verb', 'C1'): 'connector',
    ('pop', 'verb', 'C1'): 'burst',
    ('potential', 'adjective, noun', 'B2'): 'possible',
    ('preach', 'verb', 'C1'): 'advocate',
    ('precise', 'adjective', 'B2'): 'exact',
    ('predator', 'noun', 'C1'): 'hunter',
    ('premise', 'noun', 'C1'): 'assumption',
    ('presence', 'noun', 'B2'): 'attendance',
    ('preserve', 'verb', 'B2'): 'maintain',
    ('prevail', 'verb', 'C1'): 'dominate',
    ('pride', 'noun', 'B2'): 'satisfaction',
    ('privilege', 'noun', 'C1'): 'advantage',
    ('probe', 'noun, verb', 'C1'): 'investigate',
    ('progressive', 'adjective', 'B2'): 'forward',
    ('projection', 'noun', 'C1'): 'forecast',
    ('prosecution', 'noun', 'C1'): 'legal action',
    ('provision', 'noun', 'C1'): 'supply',
    ('publicity', 'noun', 'B2'): 'media attention|advertising activity',
    ('pulse', 'noun', 'C1'): 'heartbeat',
    ('accordance', 'noun', 'C1'): 'conformity',
    ('agile', 'adjective', 'C2'): 'nimble',
    ('assert', 'verb', 'C1'): 'state firmly',
    ('pump', 'noun, verb', 'C1'): 'machine|to force',
    ('punk', 'noun', 'B2'): 'rebel',
    ('pursuit', 'noun', 'B2'): 'chase',
    ('qualitative', 'adjective', 'UNCLASSIFIED'): 'descriptive',
    ('racial', 'adjective', 'B2'): 'ethnic',
    ('radiation', 'noun', 'B2'): 'energy emission',
    ('radical', 'adjective', 'C1'): 'extreme',
    ('rage', 'noun', 'C1'): 'anger',
    ('raid', 'noun, verb', 'C1'): 'attack',
    ('rail', 'noun', 'B2'): 'railway',
    ('rally', 'noun, verb', 'C1'): 'gathering',
    ('ranking', 'noun', 'C1'): 'standing',
    ('reasonably', 'adverb', 'B2'): 'fairly',
    ('recess', 'noun', 'C2'): 'break',
    ('recognition', 'noun', 'B2'): 'acknowledgment',
    ('recruit', 'noun, verb', 'B2'): 'new member',
    ('referee', 'noun', 'B2'): 'judge',
    ('refine', 'verb', 'C1'): 'purify',
    ('reflection', 'noun', 'C1'): 'image',
    ('relieved', 'adjective', 'B2'): 'glad',
    ('remains', 'noun', 'C1'): 'leftover parts',
    ('reminder', 'noun', 'C1'): 'prompt',
    ('reproduce', 'verb', 'C1'): 'copy',
    ('reproduction', 'noun', 'C1'): 'copy',
    ('republic', 'noun', 'C1'): 'country without a monarch',
    ('resign', 'verb', 'B2'): 'quit',
    ('resignation', 'noun', 'C1'): 'quit letter',
    ('resolution', 'noun', 'B2'): 'decision',
    ('restore', 'verb', 'B2'): 'repair',
    ('restraint', 'noun', 'C1'): 'limit',
    ('retreat', 'noun, verb', 'C1'): 'withdrawal',
    ('reverse', 'adjective, noun, verb', 'C1'): 'opposite',
    ('rhetoric', 'noun', 'C1'): 'persuasive language',
    ('rigid', 'adjective', 'C1'): 'stiff',
    ('ritual', 'noun', 'C1'): 'ceremony',
    ('rocket', 'noun', 'B2'): 'jet craft',
    ('rotation', 'noun', 'C1'): 'turning',
    ('ruin', 'noun, verb', 'B2'): 'destroy',
    ('sacrifice', 'noun, verb', 'C1'): 'giving up',
    ('sanction', 'noun', 'C1'): 'penalty',
    ('sanctuary', 'noun', 'C2'): 'holy place',
    ('scandal', 'noun', 'B2'): 'outrage',
    ('scare', 'noun, verb', 'B2'): 'frighten',
    ('scenario', 'noun', 'B2'): 'situation',
    ('scramble', 'verb', 'C2'): 'rush',
    ('scratch', 'noun, verb', 'B2'): 'scrape',
    ('screw', 'noun, verb', 'C1'): 'fastener',
    ('seal', 'verb, noun', 'C1'): 'close',
    ('seeker', 'noun', 'B2'): 'searcher',
    ('seize', 'verb', 'C1'): 'grab',
    ('sensation', 'noun', 'C1'): 'feeling',
    ('separation', 'noun', 'C1'): 'apartness',
    ('severely', 'adverb', 'B2'): 'seriously',
    ('shatter', 'verb', 'C1'): 'smash',
    ('shed', 'verb', 'C1'): 'lose',
    ('shoot', 'noun', 'C1'): 'sprout',
    ('shunned', 'verb', 'UNCLASSIFIED'): 'avoided',
    ('sigh', 'noun, verb', 'C1'): 'long breath',
    ('skip', 'verb', 'C1'): 'jump over',
    ('smash', 'verb', 'C1'): 'break',
    ('soar', 'verb', 'C1'): 'rise',
    ('solo', 'adjective, noun', 'C1'): 'alone',
    ('sophisticated', 'adjective', 'B2'): 'complex',
    ('soullessly', 'verb', 'UNCLASSIFIED'): 'coldly',
    ('span', 'noun, verb', 'C1'): 'duration',
    ('spectrum', 'noun', 'C1'): 'range',
    ('speculate', 'verb', 'B2'): 'guess',
    ('spell', 'noun', 'C1'): 'period',
    ('spin', 'noun, verb', 'C1'): 'rotate',
    ('spine', 'noun', 'C1'): 'backbone',
    ('springboard', 'noun', 'C2'): 'starting point',
    ('spy', 'noun, verb', 'C1'): 'secret agent',
    ('squad', 'noun', 'C1'): 'team',
    ('squeeze', 'verb', 'C1'): 'press',
    ('stack', 'verb', 'C2'): 'pile',
    ('stereotype', 'noun', 'C1'): 'generalization',
    ('sterile', 'adjective', 'UNCLASSIFIED'): 'germ-free',
    ('stir', 'verb', 'C1'): 'mix',
    ('strain', 'noun', 'C1'): 'tension',
    ('strengthen', 'verb', 'B2'): 'fortify',
    ('strip', 'noun, verb', 'C2'): 'remove',
    ('stumble', 'verb', 'C1'): 'trip',
    ('subscriber', 'noun', 'C1'): 'customer',
    ('substitute', 'noun, verb', 'C1'): 'replacement',
    ('succession', 'noun', 'C1'): 'sequence',
    ('supplement', 'noun, verb', 'C1'): 'addition',
    ('suppress', 'verb', 'C1'): 'repress',
    ('surge', 'noun, verb', 'C1'): 'rush',
    ('survivor', 'noun', 'B2'): 'one who lives',
    ('suspend', 'verb', 'B2'): 'hang',
    ('suspicious', 'adjective', 'C1'): 'doubtful',
    ('sustainable', 'adjective', 'B2'): 'lasting',
    ('swing', 'noun, verb', 'C1'): 'sway',
    ('syndrome', 'noun', 'C1'): 'symptom set',
    ('tackle', 'noun', 'C1'): 'football move',
    ('tactic', 'noun', 'C1'): 'method',
    ('tactical', 'adjective', 'C1'): 'strategic',
    ('tap', 'noun, verb', 'B2'): 'light touch',
    ('teem', 'verb', 'UNCLASSIFIED'): 'abound',
    ('temple', 'noun', 'B2'): 'place of worship',
    ('temporal', 'adjective', 'UNCLASSIFIED'): 'time-related',
    ('tender', 'adjective', 'C1'): 'gentle',
    ('tension', 'noun', 'B2'): 'stress',
    ('terminal', 'adjective', 'C1'): 'final',
    ('territory', 'noun', 'B2'): 'area',
    ('thoughtful', 'adjective', 'C1'): 'considerate',
    ('thread', 'noun', 'C1'): 'string',
    ('tide', 'noun', 'C1'): 'sea level',
    ('tolerate', 'verb', 'C1'): 'accept',
    ('torture', 'noun, verb', 'C1'): 'severe pain',
    ('toss', 'verb', 'C1'): 'throw',
    ('trail', 'noun, verb', 'C1'): 'path',
    ('trailer', 'noun', 'C1'): 'preview',
    ('transcribe', 'verb', 'UNCLASSIFIED'): 'write down',
    ('transmission', 'noun', 'C1'): 'broadcast',
    ('transportation', 'noun', 'B2'): 'transit',
    ('trap', 'noun, verb', 'B2'): 'snare',
    ('trauma', 'noun', 'C1'): 'shock',
    ('tread', 'verb', 'UNCLASSIFIED'): 'step',
    ('tribal', 'adjective', 'C1'): 'clan-based',
    ('trigger', 'noun', 'C1'): 'cause',
    ('triumph', 'noun', 'C1'): 'victory',
    ('twist', 'noun, verb', 'C1'): 'turn',
    ('ultimately', 'adverb', 'B2'): 'finally',
    ('upgrade', 'noun, verb', 'C1'): 'improve',
    ('uphold', 'verb', 'C1'): 'support',
    ('vacuum', 'noun', 'C1'): 'empty space',
    ('valid', 'adjective', 'B2'): 'acceptable',
    ('variable', 'adjective, noun', 'C1'): 'changeable',
    ('venture', 'noun, verb', 'C1'): 'enterprise',
    ('verse', 'noun', 'C1'): 'poetry',
    ('vicious', 'adjective', 'C1'): 'savage',
    ('virtue', 'noun', 'C1'): 'goodness',
    ('visible', 'adjective', 'B2'): 'seeable',
    ('voluntary', 'adjective', 'B2'): 'willing',
    ('ward', 'noun', 'C1'): 'hospital room',
    ('warrant', 'noun, verb', 'C1'): 'justify',
    ('weaken', 'verb', 'C1'): 'reduce',
    ('weave', 'verb', 'C1'): 'interlace',
    ('weird', 'adjective', 'B2'): 'strange',
    ('welfare', 'noun', 'B2'): 'well-being',
    ('whip', 'verb', 'C1'): 'lash',
    ('width', 'noun', 'C1'): 'breadth',
    ('withdrawal', 'noun', 'C1'): 'pullout',
    ('wither', 'verb', 'C2'): 'shrivel',
    ('workforce', 'noun', 'B2'): 'employees',
    ('worship', 'noun, verb', 'C1'): 'revere',
    ('zigzagging', 'verb', 'UNCLASSIFIED'): 'winding',
}


def deduplicate_chunks(gloss: str) -> str:
    res = normalize_gloss(gloss)
    g = res.gloss
    sep = res.separator
    if sep == 'none':
        return g
    sides = g.split(sep)
    seen = []
    for s in sides:
        s_clean = s.strip().lower()
        if s_clean not in [x.strip().lower() for x in seen]:
            seen.append(s)
    return sep.join(seen)


def fix_one(word: str, pos: str, cefr: str, current_gloss: str, def_before: str = '') -> str | None:
    """Propose a new gloss for a P1 bad row. Returns None if can't auto-fix.

    Order of operations:
      1. EXPLICIT_FIXES lookup (high priority)
      2. Strip POS labels
      3. Apply per-word synonym for morphological_variant
      4. Apply per-word chunk replacement for headword_in_definition
      5. Heuristic shortening for chunk_word_count / gloss_too_long
    """
    key = (word, pos, cefr)

    # Step 1: explicit override
    if key in EXPLICIT_FIXES:
        candidate = EXPLICIT_FIXES[key]
        if is_valid(word, candidate):
            return candidate
        # If override fails validation, try heuristic on top of it
        # (fall through)

    # Step 2: strip POS labels
    candidate = deduplicate_chunks(strip_pos_labels(current_gloss))
    if is_valid(word, candidate):
        return candidate

    # Step 3: morphological variant replacement
    if word in MORPHOLOGICAL_REPLACEMENTS:
        for old, new in MORPHOLOGICAL_REPLACEMENTS[word].items():
            candidate = re.sub(r'\b' + re.escape(old) + r'\b', new, candidate)
    candidate = deduplicate_chunks(candidate)
    if is_valid(word, candidate):
        return candidate

    # Step 4: headword in chunk replacement
    if word in HEADWORD_CHUNK_REPLACEMENTS:
        for old, new in HEADWORD_CHUNK_REPLACEMENTS[word].items():
            candidate = candidate.replace(old, new)
    candidate = deduplicate_chunks(candidate)
    if is_valid(word, candidate):
        return candidate

    # Step 5: heuristic shortening
    candidate = shorten_gloss(candidate, def_before)
    if is_valid(word, candidate):
        return candidate

    return None


# ============================================================================
# Build script — apply P1 fixes to audit files and TXT
# ============================================================================

def collect_bad_rows(path: Path) -> list[dict]:
    """Return list of {row, line_no, gloss, violations, has_pos_label} for bad rows."""
    bad = []
    with open(path, encoding='utf-8') as fp:
        for line_no, line in enumerate(fp, start=1):
            if not line.strip():
                continue
            r = json.loads(line)
            g = r.get('gloss_after') or ''
            res = normalize_gloss(g)
            violations = validate_verdict(
                r['word'], res.gloss, res.separator,
                chunk_count(res.gloss),
            )
            has_pos = bool(POS_LABEL_RE.search(res.gloss))
            if violations or has_pos:
                bad.append({
                    'line_no': line_no,
                    'word': r['word'],
                    'pos': r['pos'],
                    'cefr': r['cefr'],
                    'gloss': res.gloss,
                    'def_before': r.get('def_before', ''),
                    'violations': violations,
                    'has_pos_label': has_pos,
                })
    return bad


def main():
    master_bad = collect_bad_rows(paths.deck_audit_jsonl)
    filled_bad = collect_bad_rows(PROJECT_ROOT / 'data' / 'audit_expanded_needs_gloss_filled.jsonl')

    print(f'Master bad: {len(master_bad)}, Filled bad: {len(filled_bad)}')

    # Stats
    fixed = 0
    failed = []
    for b in master_bad + filled_bad:
        new_gloss = fix_one(b['word'], b['pos'], b['cefr'], b['gloss'], b['def_before'])
        if new_gloss:
            fixed += 1
        else:
            failed.append(b)

    print(f'\nFixed: {fixed}')
    print(f'Failed: {len(failed)}')
    if failed:
        print('\n=== Failed rows ===')
        for b in failed[:20]:
            print(f"  {b['word']:15s} ({b['pos']:20s}, {b['cefr']:11s})")
            print(f"    old: {b['gloss']!r}")
            print(f"    def: {b['def_before'][:120]!r}")


if __name__ == '__main__':
    main()
