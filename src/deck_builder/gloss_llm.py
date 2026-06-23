"""Gloss generation schema + prompt (γ-style).

Per user (2026-06-16):
- Rule A: no synonym pairs (collapse near-synonyms to 1 word)
- Rule B: multi-sense 3+ = drop awkward secondary senses
- 1 nghĩa: 1 gloss, không có ;
- 2 nghĩa khác nhau: "X ; Y"
- Abstract words OK với phrase
- Output: concise learner-friendly gloss, NO quotes

Word-count limits were REMOVED 2026-06-22 (P5D). The validator
(`validate_verdict` below) only checks structure + headword-leak.
The producer should still aim for short, clear glosses — but length
is no longer a hard gate.

Category auto-detect (no M3 cost):
- concrete: def has 1 sense, 1 obvious object/concept
- abstract: def about emotion/concept/state
- multi-sense-3+: def has 3+ senses joined by ';' (heuristic)
- multi-pos: pos_str contains ',' (multi-POS row)

Excluded from batch: hallucination (data bug, fix separately)
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
JOBS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_jobs.jsonl'
VERDICTS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_all_verdicts.json'


# Abstract-def signal phrases (cheap heuristic — no M3)
ABSTRACT_PHRASES = (
    'the state of', 'the fact of', 'the act of', 'the quality of',
    'the process of', 'the feeling of', 'the ability to',
    'the tendency to', 'the action of',
)


def detect_category(def_text: str, pos_str: str) -> str:
    """Auto-detect gloss category from def + pos. No M3 cost.

    Categories:
      - multi-pos: pos_str has comma (multi-POS row)
      - multi-sense-3+: def has 3+ sense chunks joined by '|' (after build_notes fix)
      - abstract: def starts with abstract-state phrase
      - concrete: default

    Note: Within a sense, Oxford sub-chunks use ' ; '. We split on '|' to get
    senses (not on ';'). The regex tolerates optional surrounding spaces.
    """
    # multi-pos check (e.g. 'noun, verb')
    if ',' in pos_str:
        return 'multi-pos'
    # multi-sense 3+ — count '|' chunks (between-sense separator)
    chunks = [c for c in re.split(r'\s*\|\s*', def_text) if c.strip()]
    if len(chunks) >= 3:
        return 'multi-sense-3+'
    # abstract check
    d = def_text.lower().lstrip()
    if any(d.startswith(p) for p in ABSTRACT_PHRASES):
        return 'abstract'
    return 'concrete'


@dataclass
class GlossVerdict:
    hash: str  # 16-char sha256 of (word|pos|cefr|def)
    word: str
    pos: str
    cefr: str
    decision: Literal['gloss', 'no-gloss']
    gloss: str  # learner-friendly gloss; length not validator-capped (P5D 2026-06-22)
    confidence: float = 1.0  # 0-1, M3 self-assessed
    reasoning: str = ''  # optional, e.g. why 'no-gloss'
    category: str = ''  # auto-detected: concrete/abstract/multi-sense-3+/multi-pos
    rule_applied: str = ''  # granular rule code (see VALID_RULE_CODES)

    # Class-level counter for validation warnings (visible in stats output)
    _validation_warnings: int = 0

    def __post_init__(self):
        """Backwards-compat warn mode: log + count gate violations on construction.
        NEVER raises — existing data may have historical violations that need cleanup.
        For strict mode, call validate_verdict() directly.
        """
        if self.decision == 'no-gloss':
            return
        sep = '|' if '|' in self.gloss else ';' if ';' in self.gloss else 'none'
        chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', self.gloss) if c.strip()]
        errs = validate_verdict(self.word, self.gloss, sep, len(chunks))
        if errs:
            GlossVerdict._validation_warnings += 1

    def to_dict(self) -> dict:
        return asdict(self)


# Granular rule codes (audit-friendly; supersede old Literal['A','B',''])
VALID_RULE_CODES = (
    '',                          # no rule (1-sense concrete/abstract)
    'rule_b_pick1',              # 3+ senses, all variants → 1 word
    'rule_b_pick2',              # 3+ senses, 2 distinct domains → 2 with |
    'rule_b_pick2_addendum',     # 3+ senses, physical/tactile+abstract → 2 with |
    '2sense_samedomain',         # 2 senses, same domain → 2 with ;
    '2sense_distinct',           # 2 senses, different domains → 2 with |
    '3sense_distinct',           # LEGACY (pre-P6): 3+ senses, all distinct → 3+ with |
    # Normalized to `multi_sense_distinct` on P6 import; retained for
    # backward compat with historical rows.
    'multi_sense_distinct',      # 2+ distinct senses, keep all with | (P6, replaces
                                 # the "NEVER pick 3" cap on distinct multisense cases)
    'common_core_trimmed',       # P7: redundant subsenses collapsed to 1 chunk
                                 # (countable/uncountable, process/result, noun/verb, subtype).
    'trimmed_multisense',        # P7: redundant/minor senses trimmed but 2+ distinct
                                 # chunks still kept (with |).
    'concrete_1sense',           # 1 sense, no special rule
    'multi_pos_pick1',           # multi-POS, all variants → 1 word
    'safety_net',                # 1 sense, domain-restricted, kept per Rule C
    'precision_phrase',          # single-word gloss would shift semantic type
                                 # (e.g. contrast_pair, type_narrowing) → phrase form
)


class GlossValidationError(Exception):
    """Raised when a verdict fails validation gate. Producer should regen or no-gloss."""
    pass


def validate_verdict(
    word: str,
    gloss: str,
    separator: str,
    count: int,
    decision: str = 'gloss',
) -> list[str]:
    """Validate a verdict against 2 auto-detectable hard rules.

    Returns list of violation strings (empty = OK). Never raises — caller decides
    what to do (skip / warn / abort).

    Rules (auto-detectable only; Rule A synonym detection requires human review):

      1. SEPARATOR/COUNT/CONTENT CONSISTENCY:
         - declared separator field must match actual '|' / ';' in gloss
         - declared count must match actual chunk count
         - empty chunk (e.g. `x |` or `| x` or `x ; ; y`) is a violation

      2. HEADWORD IN CHUNK:
         - any chunk equal to headword (case-insensitive) is a violation
         - covers self-referential pick1 (gloss==headword) AND leak in multi-chunk
         - single-word gloss that stems-matches the headword is a violation
           (morphological_variant)
         - multi-word gloss containing the exact headword token is a violation

    REMOVED 2026-06-22 (P5D): total word count 1-6 limit and per-chunk word
    limits (`pick1` ≤6, `|` ≤4, `;` ≤3). Human-filled glosses are trusted
    over arbitrary numeric length caps — see ADR 0005 addendum.

    Bypassed: decision='no-gloss' (no-gloss verdicts skip all checks).
    """
    violations: list[str] = []

    # Bypass for no-gloss verdicts
    if decision == 'no-gloss':
        return violations

    word_lower = word.strip().lower()
    gloss_stripped = gloss.strip()

    # Empty gloss + decision='gloss' is a hard fail.
    if not gloss_stripped:
        violations.append('empty_gloss: gloss is empty but decision=gloss')

    # Compute actual structure
    actual_sep = '|' if '|' in gloss_stripped else ';' if ';' in gloss_stripped else 'none'
    raw_chunks = re.split(r'\s*[|;]\s*', gloss_stripped)
    # `chunks` drops empty raw chunks (separator with empty side) so
    # `x |` and `x ; ; y` collapse to a smaller list. We use both
    # `raw_chunks` (for empty-chunk detection) and `chunks` (for
    # structural checks below).
    chunks = [c.strip() for c in raw_chunks if c.strip()]
    actual_count = len(chunks)

    # Check 1: separator/count/content consistency
    if actual_sep != separator:
        violations.append(
            f'separator_mismatch: declared={separator!r}, actual={actual_sep!r}'
        )
    if actual_count != count:
        violations.append(
            f'count_mismatch: declared={count}, actual_chunks={actual_count}'
        )

    # Empty chunk check (separator with empty side, e.g. `x |` or `x ; ; y`).
    # Iterate `raw_chunks` (BEFORE filter) so empty entries are visible.
    for i, raw in enumerate(raw_chunks):
        if not raw.strip():
            violations.append(f'empty_chunk[{i}]')

    # Check 2: headword in chunk (covers both self-ref and leak)
    from nltk.stem import PorterStemmer
    ps = PorterStemmer()

    def clean_token(t):
        return re.sub(r"[^\w]", "", t).lower()

    head_clean = clean_token(word_lower)
    if head_clean:
        head_stem = ps.stem(head_clean)
        for i, chunk in enumerate(chunks):
            if chunk.lower() == word_lower:
                violations.append(
                    f'headword_in_chunk[{i}]: chunk={chunk!r} == headword={word!r}'
                )
                continue

            # Split chunk into clean tokens
            tokens = [clean_token(t) for t in re.split(r"[\s\-\']", chunk) if t.strip()]
            tokens = [t for t in tokens if t]

            if len(tokens) == 1:
                # Single-word chunk: reject if its stem matches the headword stem (lazy morphological variants)
                gw_stem = ps.stem(tokens[0])
                if gw_stem == head_stem:
                    violations.append(
                        f'morphological_variant[{i}]: single-word chunk {chunk!r} matches stem of headword {word!r}'
                    )
            elif len(tokens) > 1:
                # Multi-word chunk: reject if exact headword is in the definition part
                parts = chunk.split(":")
                def_part = parts[1] if len(parts) > 1 else chunk
                def_words = [clean_token(t) for t in re.split(r"[\s\-\']", def_part) if t.strip()]
                def_words = [t for t in def_words if t]

                if word_lower in def_words:
                    violations.append(
                        f'headword_in_definition[{i}]: headword {word!r} found in definition part of chunk {chunk!r}'
                    )
                elif len(parts) == 1 and word_lower in tokens:
                    # Multi-word with no colon but contains exact headword
                    violations.append(
                        f'headword_in_phrase[{i}]: headword {word!r} found in phrase chunk {chunk!r}'
                    )

    return violations


def summarize_violations(violations_by_key: dict[str, list[str]]) -> None:
    """Print violation summary by category. Used by loaders/stats."""
    from collections import Counter
    cat = Counter()
    for vlist in violations_by_key.values():
        for v in vlist:
            # Extract category prefix (before ':')
            cat[v.split(':', 1)[0]] += 1
    if cat:
        print(f'⚠️  {sum(cat.values())} gate violations across {len(violations_by_key)} verdicts:')
        for k, c in cat.most_common():
            print(f'    {k}: {c}')


GLOSS_SYSTEM_PROMPT = """You generate concise learner-friendly glosses for vocabulary flashcards.

Given a dictionary definition, paraphrase it concisely. Capture the CORE meaning
in simple, memorable language. Drop grammatical connectors and hedges. Skip register
labels (formal, informal, etc.). Output ONLY the gloss, no quotes, no explanation.

LENGTH GUIDANCE (post-P5D 2026-06-22): use the shortest clear learner-friendly
gloss; do not drop meaning just to hit a word count. The validator no longer
hard-caps total or per-chunk word counts — length is a soft judgment call,
not a hard gate. When a gloss needs more than 6 words to capture the headword's
full semantic coverage (e.g. multi-sense C1/C2 academic vocabulary), prefer
the longer accurate gloss over a forced-shortened one that drops sense coverage.

The input def may contain multiple senses separated by "|" (pipe, no spaces).
Within a sense, sub-chunks (Oxford "act of finding sb guilty; the fact of having been found guilty")
use " ; " (semicolon-space) — these are 1 sense, not separate senses. Do not split on ";".
Decide which senses to keep and which to drop, then choose the right separator
for the kept glosses.

SEPARATOR SEMANTICS (strict):
- "|" (pipe) = distinct senses in different domains → rendered as separate rows on the card
- ";" (semicolon) = senses in the same domain (variants, sub-nuances, related uses) → 1 row

RULE A — NO NEAR-SYNONYM PAIRS (strict):
If 2 kept senses are near-synonyms (same concept, different wording), output 1 word only.
- BAD: "ridiculous; nonsensical" (same concept)
- BAD: "conclusive; resolute" (same concept)
- GOOD: "ridiculous" (just one)
- GOOD: "conclusive" (just one)
When 2 senses are related but not identical, use "X ; Y" (1 row, both glosses in same def slot).

RULE B — MULTI-SENSE 3+ (softened):
If the def has 3+ senses:
- Pick 1 gloss if all kept senses are variants or sub-nuances of the same core concept
- Pick 2 glosses (separated by "|") if the first 2 senses cover clearly different
  domains, usage contexts, or grammatical roles
- NEVER pick 3
- DROP a sense (even if not a sub-nuance) if it is domain-restricted
  (music, law, finance, medicine...) AND unlikely in general IELTS contexts
- After picking, apply Rule A or the separator semantics.

RULE B ADDENDUM — PHYSICAL/TACTILE vs ABSTRACT (strict):
When judging "variants vs different domains" for a 3+ sense cluster, treat a
PHYSICAL/TACTILE sense (touching, holding, operating a physical object with
your hands) as a different domain from an ABSTRACT sense (managing a situation,
an idea, or an emotion) — even if a single gloss word could loosely cover both.
Pick 2 in this case.
- Example: "handle" has senses "deal with situation" (abstract), "touch/hold object"
  (physical), "control vehicle" (physical) — abstract vs physical = different domains
  → pick 2 with "|".

RULE C — SAFETY NET (strict):
If dropping a sense would leave the card with no gloss, keep it regardless of
domain restriction. Never produce an empty gloss.

MULTI-SENSE 2 RULES (kept from before, with new separator + addendum):
- 1 sense: emit 1 gloss, no separator.
- 2 near-synonym senses: 1 word (Rule A).
- 2 senses in same domain (related, variants): "X ; Y" (1 row).
- 2 senses in different domains: "X | Y" (2 rows).
- 2 senses, one physical/tactile + one abstract: "X | Y" (different domains per addendum).

PHYSICAL RULES:
- No quotes, no period, no preamble.
- If the definition is unintelligible or unscorable, output: NO-GLOSS

Examples:
Def: "the deliberate ending of a pregnancy, whether by medical operation or other means"
Gloss: ending a pregnancy

Def: "a complete lack of order"
Gloss: complete disorder

Def: "extremely silly; not logical and sensible"
Gloss: ridiculous

Def: "a person who is not a citizen of the country in which they live or work | a creature from another planet"
Gloss: foreigner | extraterrestrial
[social + sci-fi = different domains → 2 rows with "|"]

Def: "to plan or organize something in advance | to put something in a particular order | to change a piece of music so that it is suitable for a particular instrument or voice"
Gloss: plan; organize
[plan + put-in-order = same domain (organizing) → 1 row with ";"; adapt music = domain-restricted → drop]

Def: "the act of finding somebody guilty of a crime in court; the fact of having been found guilty | a strong opinion or belief | the quality of showing that you believe strongly in what you are saying"
Gloss: guilty verdict | firm belief
[legal + opinion = different domains → 2 rows with "|"; sincerity = sub-nuance of opinion → drop; note: ";" within sense 1 is Oxford-style sub-chunk, not a separator]

Def: "one of the short sections of equal length that a piece of music is divided into"
Gloss: music measure
[music is domain-restricted BUT safety net: this is the only sense at C1 → keep; never empty]

Def: "the profession of barrister (= a lawyer in a higher court)"
Gloss: legal profession
[law is domain-restricted BUT safety net: this is the only sense at C2 → keep; never empty]

Def: "to deal with a situation, a person, an area of work or a strong emotion | to touch, hold or move something with your hands | to control a vehicle, an animal, a tool, etc."
Gloss: hold/touch | manage situation
[handle: abstract (deal with situation) + physical (touch/hold) = different domains per addendum → 2 rows with "|"; "control vehicle" collapsed with "touch/hold" as physical]

Now paraphrase the user's def."""


def load_jobs() -> list[dict]:
    return [json.loads(l) for l in JOBS_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]


def load_existing_verdicts() -> dict[str, GlossVerdict]:
    if not VERDICTS_PATH.exists():
        return {}
    data = json.loads(VERDICTS_PATH.read_text(encoding='utf-8'))
    # Filter to only fields GlossVerdict accepts (drop extras like separator/count)
    valid_fields = {f.name for f in GlossVerdict.__dataclass_fields__.values()}
    out = {}
    for v in data.get('verdicts', []):
        filtered = {k: val for k, val in v.items() if k in valid_fields}
        out[v['hash']] = GlossVerdict(**filtered)
    return out


def save_verdicts(verdicts: dict[str, GlossVerdict]) -> None:
    payload = {
        'version': 1,
        'verdicts': [v.to_dict() for v in verdicts.values()],
    }
    VERDICTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(verdicts)} verdicts to {VERDICTS_PATH}')


def stats(verdicts: dict[str, GlossVerdict], total: int) -> None:
    from collections import Counter
    import re
    by_decision = {'gloss': 0, 'no-gloss': 0}
    by_word_count = {'1': 0, '2': 0, '3': 0, '4-6': 0}
    by_separator = {'none': 0, '|': 0, ';': 0}
    by_category = Counter()
    for v in verdicts.values():
        by_decision[v.decision] = by_decision.get(v.decision, 0) + 1
        # Count content words (exclude '|' and ';' separators)
        content = re.sub(r'[|;]', ' ', v.gloss)
        wc = len(content.split())
        if wc == 1:
            by_word_count['1'] += 1
        elif wc == 2:
            by_word_count['2'] += 1
        elif wc == 3:
            by_word_count['3'] += 1
        else:
            by_word_count['4-6'] += 1
        # Track separator usage
        if '|' in v.gloss:
            by_separator['|'] += 1
        elif ';' in v.gloss:
            by_separator[';'] += 1
        else:
            by_separator['none'] += 1
        by_category[v.category or 'unset'] += 1
    print(f'  total jobs: {total}')
    print(f'  verdicts: {len(verdicts)} ({len(verdicts) / total * 100:.1f}%)')
    print(f'  by decision: {by_decision}')
    print(f'  by word count: {by_word_count}')
    print(f'  by separator: {by_separator}')
    print(f'  by category: {dict(by_category)}')


if __name__ == '__main__':
    jobs = load_jobs()
    verdicts = load_existing_verdicts()
    print(f'Loaded {len(jobs)} jobs, {len(verdicts)} existing verdicts')
    stats(verdicts, len(jobs))
