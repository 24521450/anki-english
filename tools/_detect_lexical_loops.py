"""P5C Lexical Loop Guard — read-only detector.

Scans audit + P5 ledger + P4C ledger + manual decisions and reports
likely lexical-loop candidates. Does NOT auto-fix. Human review is
required because (a) some loops are intentional (precision_phrase is
the planned fix), and (b) false positives are common (single-word
stem overlap).

Three loop types are reported:
  - word_family_loop: headword stem appears in any gloss chunk stem.
  - antonym_loop: gloss starts with `not|no|never|without|un-` and the
    remainder is an academic-ish word.
  - hard_synonym_drift: 1-chunk, 1-word gloss (treating hyphenated
    compounds as single words) that is NOT a basic-English word and
    does NOT share headword stem. This is the failure mode
    precision_phrase already addresses; the tag lets reporting
    distinguish it from the other loops.

Outputs:
  - Per-key candidate list with loop_type tag.
  - Distribution by loop_type.
  - Sanity check: known cases from the plan (additionally / permanent /
    mediate) produce expected verdicts.

Run: `python -m tools._detect_lexical_loops [--include-all]`:
  - default: only rows whose `gloss_after` looks suspect (heuristic).
  - `--include-all`: scan every audit row (slower).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# Negation prefixes that signal an antonym_loop candidate.
# Two forms:
# - With trailing space: must be followed by space in the gloss
#   (`not present`, `no longer`, `never again`).
# - Bare prefix: attaches directly to a word with optional hyphen
#   (`unfair`, `non-representational`, `nonviolent`).
ANTONYM_PREFIXES_SPACED = (
    'not ', 'no ', 'never ', 'without ',
)
ANTONYM_PREFIXES_BARE = ('un', 'non')


# Basic-English stoplist (A1/A2 + common connectors + common
# adjectives/adverbs). Used to exempt already-simple gloss words from
# the `hard_synonym_drift` tag. Not exhaustive — the goal is to exempt
# the most common ~150 words that show up as gloss tokens.
BASIC_STOPWORDS: set[str] = {
    # function words / connectors
    'a', 'an', 'the', 'and', 'or', 'but', 'so', 'because', 'since',
    'if', 'when', 'while', 'until', 'before', 'after', 'during',
    'as', 'than', 'that', 'this', 'these', 'those', 'it', 'its',
    'i', 'you', 'he', 'she', 'we', 'they', 'them', 'his', 'her',
    'my', 'your', 'our', 'their', 'me', 'us',
    'in', 'on', 'at', 'by', 'for', 'with', 'from', 'to', 'of', 'into',
    'about', 'between', 'through', 'over', 'under', 'above', 'below',
    'up', 'down', 'out', 'off', 'back', 'away', 'near', 'far',
    'not', 'no', 'never',
    'also', 'too', 'only', 'just', 'even', 'still', 'already', 'yet',
    'always', 'often', 'sometimes', 'usually', 'rarely', 'seldom',
    'here', 'there', 'now', 'then', 'today', 'tomorrow', 'yesterday',
    'again', 'once', 'twice',
    'much', 'many', 'more', 'most', 'less', 'least', 'few', 'fewer',
    'some', 'any', 'all', 'none', 'every', 'each', 'other', 'another',
    'such', 'same', 'different', 'own',
    # basic adjectives / adverbs
    'good', 'bad', 'big', 'small', 'long', 'short', 'high', 'low',
    'old', 'new', 'young', 'fast', 'slow', 'hot', 'cold', 'warm',
    'easy', 'hard', 'simple', 'complex', 'plain', 'clear', 'dark',
    'light', 'clean', 'dirty', 'rich', 'poor', 'full', 'empty',
    'open', 'close', 'closed', 'near', 'far', 'early', 'late',
    'strong', 'weak', 'safe', 'sure', 'real', 'true', 'false',
    'right', 'wrong', 'fine', 'normal', 'usual', 'common', 'rare',
    'great', 'little', 'tiny', 'huge', 'wide', 'narrow', 'deep',
    'soft', 'rough', 'smooth', 'sharp', 'dull', 'thick', 'thin',
    'heavy', 'light', 'loud', 'quiet', 'alive', 'dead', 'awake',
    'asleep', 'happy', 'sad', 'angry', 'glad', 'sorry', 'afraid',
    'tired', 'sick', 'healthy', 'ill',
    # basic verbs
    'go', 'come', 'get', 'give', 'take', 'make', 'do', 'have', 'be',
    'say', 'tell', 'ask', 'see', 'look', 'watch', 'hear', 'listen',
    'feel', 'think', 'know', 'want', 'need', 'like', 'love', 'hate',
    'help', 'try', 'use', 'find', 'keep', 'let', 'put', 'set',
    'turn', 'start', 'stop', 'end', 'begin', 'finish', 'leave',
    'stay', 'move', 'run', 'walk', 'sit', 'stand', 'lie', 'fall',
    'rise', 'drop', 'grow', 'cut', 'break', 'hold', 'catch', 'pull',
    'push', 'carry', 'bring', 'send', 'buy', 'sell', 'pay', 'cost',
    'save', 'spend', 'lose', 'win', 'play', 'work', 'live', 'die',
    'eat', 'drink', 'sleep', 'wake', 'rest', 'talk', 'speak', 'call',
    'show', 'hide', 'open', 'close', 'read', 'write', 'draw',
    'sing', 'dance', 'laugh', 'cry', 'smile',
    # basic nouns
    'man', 'woman', 'boy', 'girl', 'child', 'kid', 'baby', 'person',
    'people', 'friend', 'family', 'mother', 'father', 'brother',
    'sister', 'son', 'daughter', 'husband', 'wife', 'home', 'house',
    'room', 'door', 'window', 'wall', 'floor', 'roof', 'bed', 'table',
    'chair', 'book', 'paper', 'page', 'word', 'name', 'time', 'day',
    'night', 'morning', 'afternoon', 'evening', 'year', 'month',
    'week', 'hour', 'minute', 'second', 'moment', 'thing', 'stuff',
    'place', 'way', 'road', 'street', 'city', 'country', 'world',
    'water', 'food', 'money', 'job', 'work', 'life', 'hand', 'eye',
    'face', 'head', 'body', 'foot', 'leg', 'arm', 'back', 'side',
    'top', 'bottom', 'end', 'middle', 'part', 'group', 'team',
    'number', 'kind', 'type', 'sort',
    # common academic basic words
    'use', 'used', 'using', 'help', 'helping', 'helps', 'show',
    'showing', 'shows', 'make', 'making', 'makes', 'give', 'giving',
    'gives', 'find', 'finding', 'finds', 'change', 'changing',
    'changes', 'keep', 'keeping', 'keeps', 'last', 'lasting', 'lasts',
}


def _tokenize_words(text: str) -> list[str]:
    """Split into words, treating hyphenated compounds as a single word.

    Splits on whitespace, `|`, `;`. Keeps hyphenated compounds like
    `long-lasting` as one token. Lowercases. Drops empties.
    """
    if not text:
        return []
    parts = re.split(r'[\s|;]+', text.strip().lower())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.append(p)
    return out


def _split_compound(token: str) -> list[str]:
    """If a token contains hyphens (compound), split into parts."""
    if '-' in token:
        return [t for t in token.split('-') if t]
    return [token]


def _stems(tokens: list[str]) -> set[str]:
    """Porter-stem a list of tokens. Requires NLTK (already a project dep)."""
    from nltk.stem import PorterStemmer
    ps = PorterStemmer()
    return {ps.stem(t) for t in tokens if t}


def _headword_stem(word: str) -> str:
    """Stem a single headword (uses Porter)."""
    from nltk.stem import PorterStemmer
    return PorterStemmer().stem(word.strip().lower())


def _gloss_chunks(gloss: str) -> list[str]:
    """Split gloss on `|` (distinct senses) or `;` (sub-nuances).

    Returns the list of chunk texts (whitespace-stripped).
    """
    if not gloss:
        return []
    parts = re.split(r'\s*[|;]\s*', gloss.strip())
    return [p.strip() for p in parts if p.strip()]


def detect_loops(
    word: str,
    gloss: str,
) -> list[str]:
    """Return list of loop_type tags that apply to (word, gloss).

    Empty list = no loop detected. Multiple tags may apply if the gloss
    hits more than one failure mode.
    """
    if not gloss or not word:
        return []

    head_stem = _headword_stem(word)
    if not head_stem:
        return []

    chunks = _gloss_chunks(gloss)
    if not chunks:
        return []

    out: list[str] = []

    # 1. word_family_loop: any chunk shares headword stem (split
    #    compounds so 'long-lasting' would match 'last' stem).
    head_stem_set = _stems(_split_compound(word.strip().lower()))
    for chunk in chunks:
        chunk_tokens = _tokenize_words(chunk)
        chunk_stems = set()
        for tok in chunk_tokens:
            chunk_stems.update(_stems(_split_compound(tok)))
        if head_stem_set & chunk_stems:
            out.append('word_family_loop')
            break

    # 2. antonym_loop: chunk starts with a negation prefix.
    #    Two forms: spaced (`not present`) or bare (`unfair`, `non-rep`).
    for chunk in chunks:
        cl = chunk.lower().strip()
        triggered = False
        for prefix in ANTONYM_PREFIXES_SPACED:
            if cl.startswith(prefix):
                rest = cl[len(prefix):].strip()
                if len(rest) >= 3 and re.match(r'^[a-z]', rest):
                    triggered = True
                break
        if not triggered:
            for prefix in ANTONYM_PREFIXES_BARE:
                if cl.startswith(prefix) and len(cl) > len(prefix):
                    # Allow optional hyphen between prefix and root word.
                    rest = cl[len(prefix):]
                    if rest.startswith('-'):
                        rest = rest[1:]
                    if len(rest) >= 3 and re.match(r'^[a-z]', rest):
                        # Don't trigger if the bare-prefix version is
                        # already a basic stopword (e.g. `non` alone).
                        if cl not in BASIC_STOPWORDS:
                            triggered = True
                    break
        if triggered:
            out.append('antonym_loop')
            break

    # 3. hard_synonym_drift: 1-chunk gloss, exactly 1 word (after
    #    treating hyphenated compounds as 1 word), NOT a basic-English
    #    stopword, NOT sharing headword stem, NOT a negation.
    if (
        len(chunks) == 1
        and 'word_family_loop' not in out
        and 'antonym_loop' not in out
    ):
        chunk_tokens = _tokenize_words(chunks[0])
        # Treat hyphenated compound as 1 word: 'long-lasting' -> 1.
        n_words = sum(len(_split_compound(t)) for t in chunk_tokens)
        if n_words == 1:
            single_word = chunk_tokens[0] if chunk_tokens else ''
            if single_word and single_word not in BASIC_STOPWORDS:
                out.append('hard_synonym_drift')

    return out


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def _audit_iter(audit: list[dict]) -> list[tuple[str, str, str, str, dict]]:
    """Yield (word, pos, cefr, gloss_after, audit_row) tuples for each
    audit row that has a non-empty gloss_after."""
    for r in audit:
        gloss = (r.get('gloss_after') or '').strip()
        if not gloss:
            continue
        yield (
            (r.get('word') or '').strip(),
            (r.get('pos') or '').strip(),
            (r.get('cefr') or '').strip(),
            gloss,
            r,
        )


def _looks_suspect(gloss: str) -> bool:
    """Cheap pre-filter: gloss likely to fail. Avoids running the stemmer
    on every row when `--include-all` is not set."""
    cl = gloss.lower().strip()
    # Single short word (likely a hard synonym)
    if ' ' not in cl and '|' not in cl and ';' not in cl and len(cl) <= 14:
        return True
    # Negation prefix (spaced or bare)
    if any(cl.startswith(p) for p in ANTONYM_PREFIXES_SPACED):
        return True
    if any(cl.startswith(p) for p in ANTONYM_PREFIXES_BARE) and len(cl) > 3:
        return True
    # Multi-chunk (possible sub-loop within chunks)
    if '|' in cl or ';' in cl:
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        '--include-all', action='store_true',
        help='Scan every audit row (default: only suspect candidates)',
    )
    args = ap.parse_args()

    print('=' * 72)
    print('P5C LEXICAL LOOP GUARD -- DETECTOR (read-only)')
    print('=' * 72)

    audit = _load_jsonl(PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl')
    print(f'\n  Loaded {len(audit)} audit rows.')

    # Plan's known cases (sanity).
    sanity_cases = [
        ('additionally', 'in addition', ['word_family_loop']),
        ('additionally', 'also', []),
        ('permanent', 'not temporary', ['antonym_loop']),
        ('permanent', 'long-lasting', []),
        ('mediate', 'arbitrate', ['hard_synonym_drift']),
    ]

    print('\n[1] Sanity check: known plan cases...')
    sanity_failures: list[str] = []
    for word, gloss, expected in sanity_cases:
        got = detect_loops(word, gloss)
        ok = got == expected
        status = 'OK' if ok else 'FAIL'
        print(f'  [{status}] {word} -> {gloss!r}: expected {expected}, got {got}')
        if not ok:
            sanity_failures.append(f'  {word} -> {gloss!r}: expected {expected}, got {got}')

    # Full scan.
    print('\n[2] Full scan (loop_type detection)...')
    by_type: Counter[str] = Counter()
    candidates: list[dict] = []
    n_scanned = 0
    for word, pos, cefr, gloss, row in _audit_iter(audit):
        if not args.include_all and not _looks_suspect(gloss):
            continue
        n_scanned += 1
        tags = detect_loops(word, gloss)
        if not tags:
            continue
        for tag in tags:
            by_type[tag] += 1
            candidates.append({
                'word': word,
                'pos': pos,
                'cefr': cefr,
                'gloss_after': gloss,
                'loop_type': tag,
                'rule_applied': row.get('rule_applied', ''),
                'fix_status': row.get('fix_status', ''),
            })

    print(f'  Scanned: {n_scanned} rows')
    print(f'  Loop candidates: {len(candidates)}')
    print(f'  by loop_type:')
    for t, n in by_type.most_common():
        print(f'    {t}: {n}')

    # Show top 10 per loop_type.
    print('\n[3] Sample candidates (top 10 per loop_type)...')
    for t in ('word_family_loop', 'antonym_loop', 'hard_synonym_drift'):
        sample = [c for c in candidates if c['loop_type'] == t][:10]
        if sample:
            print(f'\n  -- {t} --')
            for c in sample:
                print(
                    f"    {c['word']}|{c['pos']}|{c['cefr']}: "
                    f"gloss={c['gloss_after']!r} rule={c['rule_applied']!r}"
                )

    # Final verdict.
    print()
    if sanity_failures:
        print('=' * 72)
        print('FAIL -- P5C sanity cases do not produce expected verdicts:')
        for s in sanity_failures:
            print(s)
        print('=' * 72)
        return 1
    print('=' * 72)
    print(
        f'PASS -- P5C detector scanned {n_scanned} rows, '
        f'found {len(candidates)} loop candidates. '
        f'No auto-fix applied; review the candidate list above.'
    )
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
