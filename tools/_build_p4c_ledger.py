"""Generate data/gloss_policy_review_p4c.jsonl from the triage decisions.

This script is a one-time builder — it materializes the P4C ledger as
a JSONL file. The apply/verify/audit tools all read from this file
(single source of truth) instead of carrying the 64-row data in code.
"""
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
LEDGER_PATH = PROJECT_ROOT / 'data' / 'gloss_policy_review_p4c.jsonl'

P4C_VERSION = '2026-06-21'

# Decision: (word, pos, cefr) -> (decision, new_gloss_or_None, reason)
# `new_gloss_or_None` is None for keep_single.
# All other fields (rule_applied, def_before, old_gloss) come from the
# current audit at build time — this guarantees byte-exact match.
DECISIONS: dict[tuple[str, str, str], tuple[str, str | None, str]] = {
    # ── 7 repair_gloss entries ──────────────────────────────────────
    ('curious',    'adjective',     'B2'): ('repair_gloss', 'inquisitive|strange',
        "sense 2 'strange and unusual' (academic usage) is dropped by old gloss"),
    ('decisive',   'adjective',     'C1'): ('repair_gloss', 'pivotal|resolute',
        "sense 1 'decisive factor/moment' (pivotal) is the most common academic use; old 'resolute' only covers sense 2"),
    ('line-up',    'noun',          'C1'): ('repair_gloss', 'roster|schedule',
        "sense 2 'events arranged in order' is a distinct learner meaning (program schedule); old 'roster' only covers sense 1"),
    ('modest',     'adjective',     'B2'): ('repair_gloss', 'moderate|humble',
        "sense 1 'moderate / not large' is a distinct academic meaning (modest income/goal); old 'humble' only covers sense 2"),
    ('attribute',  'noun, verb',    'C1'): ('repair_gloss', 'quality|credit',
        "verb sense (to credit / ascribe) is dropped — common academic use; old 'quality' only covers noun sense"),
    ('bow',        'noun, verb',    'C1'): ('repair_gloss', 'bend|weapon',
        "weapon sense (bow and arrow) is the 2nd most common meaning; old 'bend forward' only covers greeting sense"),
    ('liberal',    'adjective, noun', 'C1'): ('repair_gloss', 'open-minded|progressive',
        "social-democratic sense (progressive policies) is dropped — common in political/IELTS contexts; old 'open-minded' only covers sense 1"),

    # ── 57 keep_single entries ─────────────────────────────────────
    ('briefly',    'adverb',        'B2'): ('keep_single', None,
        "sense 2 'in few words' is a niche writing-style sub-meaning; main 'brief duration' covers the dominant learner use"),
    ('competitive', 'adjective',    'B1'): ('keep_single', None,
        "'wanting to win' covers the main adjective use; the situation sub-sense is implied"),
    ('democratic', 'adjective',     'B2'): ('keep_single', None,
        "'elected' works as a quick learner cover; full 'rule by the people' is a stretch for one word; non-critical for IELTS"),
    ('frustration', 'noun',         'C1'): ('keep_single', None,
        "sub-chunks are within a single sense (Oxford ';' style); 'annoyance' covers the feeling + cause"),
    ('goodness',   'noun',          'B2'): ('keep_single', None,
        "single-sense noun; 'morality' is a fine learner cover"),
    ('harassment', 'noun',          'C1'): ('keep_single', None,
        "single-sense noun; 'bullying' is a reasonable approximation"),
    ('interval',   'noun',          'B2'): ('keep_single', None,
        "sub-chunks are within a single sense (time gap between events / between parts of a performance); one word covers both"),
    ('momentum',   'noun',          'C1'): ('keep_single', None,
        "sub-chunks are within a single sense; 'impetus' is a fine learner cover"),
    ('nutritious', 'adjective',     'B2'): ('keep_single', None,
        "single-sense adjective; verbose gloss but correct"),
    ('precise',    'adjective',     'B2'): ('keep_single', None,
        "sense 2 is meta-emphasis ('at that precise moment'), not a separate academic meaning; 'exact' covers sense 1 which subsumes the use"),
    ('presence',   'noun',          'B2'): ('keep_single', None,
        "sub-chunks are within a single sense; 'attendance' is fine"),
    ('pursuit',    'noun',          'B2'): ('keep_single', None,
        "single-sense noun; 'chase' works for the action"),
    ('recognition', 'noun',         'B2'): ('keep_single', None,
        "single-sense noun; 'acknowledgment' is a fine learner cover"),
    ('severely',   'adverb',        'B2'): ('keep_single', None,
        "sub-chunks are within a single sense (degree / strictness); 'seriously' covers the dominant use"),
    ('tactical',   'adjective',     'C1'): ('keep_single', None,
        "single-sense adjective; 'strategic' is fine"),

    ('abuse',      'noun, verb',    'C1'): ('keep_single', None,
        "noun + verb both center on 'cruel/wrong treatment'; 'mistreatment' covers all senses"),
    ('amateur',    'adjective, noun', 'C1'): ('keep_single', None,
        "all senses collapse to 'non-professional' (adjective of not-expert OR noun of not-expert)"),
    ('assault',    'noun, verb',    'C1'): ('keep_single', None,
        "noun and verb both center on 'violent attack'; abstract uses ('verbal assault', 'assault on a goal') are domain-extensions of the same core"),
    ('bid',        'noun, verb',    'B2'): ('keep_single', None,
        "all 4 senses are 'offer' (price/offer/auction/contract); single word covers all"),
    ('blend',      'noun, verb',    'C1'): ('keep_single', None,
        "all 6 senses collapse to 'mix' / 'mixture'; no distinct domain"),
    ('breach',     'noun, verb',    'C1'): ('keep_single', None,
        "noun and verb both center on 'violation of a rule/agreement'; the relationship sub-sense is a minor extension"),
    ('compromise', 'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'agreement / give up demands'; the 'jeopardize' verb sense is secondary in academic writing; keep gloss concise"),
    ('crack',      'noun, verb',    'B2'): ('keep_single', None,
        "all senses collapse to 'break' (line/space/act-of-breaking); no distinct domain"),
    ('cult',       'adjective, noun', 'C1'): ('keep_single', None,
        "main noun use is 'small group / devoted following'; adj 'cult classic/favorite' shares the same core (popular with a niche group)"),
    ('distress',   'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'suffering / worry'; the ship-in-distress sub-sense is technical and rare in IELTS"),
    ('dive',       'noun, verb',    'B2'): ('keep_single', None,
        "all senses are 'jump' (into water / underwater / downward); the catch-ball sub-sense is rare in academic writing"),
    ('echo',       'noun, verb',    'C1'): ('keep_single', None,
        "noun + verb both center on 'repetition' (sound or idea); one cover works for both"),
    ('grasp',      'noun, verb',    'C1'): ('keep_single', None,
        "physical hold + figurative understanding are metaphorically linked; 'hold' covers both"),
    ('grip',       'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'tight hold'; the abstract extensions (control, attention) are figurative 'holds'"),
    ('hint',       'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'indirect indication'; the 'small amount' and 'advice' sub-senses are minor extensions"),
    ('leak',       'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'escape of substance/information'; the hole sense is the cause"),
    ('leap',       'noun, verb',    'C1'): ('keep_single', None,
        "all senses are 'jump' (physical or figurative increase); no distinct domain"),
    ('log',        'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'record'; the wood-piece sense is a distinct homonym but rare in academic writing"),
    ('march',      'noun, verb',    'C1'): ('keep_single', None,
        "all senses are 'walk' (protest/military/quick); one word covers all"),
    ('mate',       'noun, verb',    'B2'): ('keep_single', None,
        "main noun + verb use center on 'partner'; the 'friend' and 'address' senses are informal/colloquial and not IELTS-relevant"),
    ('mature',     'adjective, verb', 'C1'): ('keep_single', None,
        "adj + verb both center on 'grown up / developed'; the 'behaving sensibly' is the social aspect of being grown up"),
    ('parallel',   'adjective, noun', 'B2'): ('keep_single', None,
        "main adj + noun use center on 'similar'; the geometric 'parallel lines' is a domain-specific use"),
    ('pile',       'noun, verb',    'B2'): ('keep_single', None,
        "main noun + verb use center on 'stack'; 'a lot of' is a figurative extension"),
    ('plug',       'noun, verb',    'C1'): ('keep_single', None,
        "main noun use is 'electrical connector'; the figurative 'plug a gap' is an extension; 'connector' is the unifying concept"),
    ('raid',       'noun, verb',    'C1'): ('keep_single', None,
        "all senses are 'attack' (military/police/crime); one word covers all"),
    ('rally',      'noun, verb',    'C1'): ('keep_single', None,
        "main noun use is 'public gathering' (political); the 'car race' and 'price recovery' are minor / domain-specific"),
    ('recruit',    'noun, verb',    'B2'): ('keep_single', None,
        "all senses are 'new member / enrolling new members'; one phrase covers both"),
    ('retreat',    'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'withdrawal' (military or escape); one word covers both"),
    ('reverse',    'adjective, noun, verb', 'C1'): ('keep_single', None,
        "many meanings but the 'opposite' cover is fine; the noun 'reverse gear' and verb 'reverse a car' are technical/domain-specific extensions"),
    ('ruin',       'noun, verb',    'B2'): ('keep_single', None,
        "main use is 'destroy / destroyed state'; the 'remains' and 'ruin as verb of impoverishment' are sub-senses"),
    ('sacrifice',  'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'giving up something valuable'; the religious sense is rare in IELTS"),
    ('scare',      'noun, verb',    'B2'): ('keep_single', None,
        "'scare' works as both noun and verb in English; 'frighten' is the verb base that the noun form derives from"),
    ('scratch',    'noun, verb',    'B2'): ('keep_single', None,
        "noun and verb are the same action (mark from scraping / act of scraping); 'scrape' covers both"),
    ('screw',      'noun, verb',    'C1'): ('keep_single', None,
        "noun + verb both center on 'screw as fastener'; 'fastener' is the noun base for the verb use"),
    ('seal',       'verb, noun',    'C1'): ('keep_single', None,
        "main verb use is 'close tightly / make definitive'; noun uses (official mark, substance) are technical variants"),
    ('span',       'noun, verb',    'C1'): ('keep_single', None,
        "noun + verb both center on 'time/distance span'; 'duration' covers the noun and the verb follows naturally"),
    ('spin',       'noun, verb',    'C1'): ('keep_single', None,
        "noun + verb both center on 'rotation'; one word covers both"),
    ('surge',      'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'sudden increase / rush'; covers both noun and verb"),
    ('torture',    'noun, verb',    'C1'): ('keep_single', None,
        "noun + verb both center on 'severe pain'; one noun phrase covers both"),
    ('trail',      'noun, verb',    'C1'): ('keep_single', None,
        "main noun use is 'path/route' (countryside trail); verb 'to trail behind' is metaphorically linked"),
    ('trap',       'noun, verb',    'B2'): ('keep_single', None,
        "main noun + verb use center on 'catching / being caught'; 'snare' covers the trap-as-device and trap-as-action"),
    ('twist',      'noun, verb',    'C1'): ('keep_single', None,
        "main noun + verb use center on 'turning / rotation'; the 'unexpected plot twist' is a figurative extension"),
}


def _compute_separator_count(gloss: str) -> tuple[str, int]:
    if '|' in gloss:
        sep = '|'
    elif ';' in gloss:
        sep = ';'
    else:
        sep = 'none'
    chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', gloss) if c.strip()]
    wc = sum(len(c.split()) for c in chunks)
    return sep, wc


def main():
    # Load audit to get exact def_before + rule_applied + old_gloss
    audit_by_key: dict[tuple[str, str, str], dict] = {}
    with AUDIT_PATH.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            k = (r['word'].strip().lower(),
                 r['pos'].strip().lower(),
                 r['cefr'].strip().upper())
            audit_by_key[k] = r

    # Verify DECISIONS covers exactly the policy_review set
    from tools._audit_gloss_policy_coverage import _classify_row
    decision_keys = set(DECISIONS.keys())
    policy_review_keys = {
        (r['word'].lower(), r['pos'].lower(), r['cefr'].upper())
        for r in audit_by_key.values()
        if _classify_row(r)[0] == 'policy_review'
    }
    if decision_keys != policy_review_keys:
        missing = policy_review_keys - decision_keys
        extra = decision_keys - policy_review_keys
        print(f'FATAL: DECISIONS mismatch with current policy_review set')
        if missing:
            print(f'  missing from DECISIONS: {missing}')
        if extra:
            print(f'  extra in DECISIONS: {extra}')
        return 1
    print(f'DECISIONS covers exactly the {len(policy_review_keys)} policy_review rows.')

    # Build JSONL records
    records: list[dict] = []
    for k, (decision, new_gloss, reason) in DECISIONS.items():
        r = audit_by_key[k]
        rec: dict = {
            'word': r['word'],
            'pos': r['pos'],
            'cefr': r['cefr'],
            'rule_applied': r.get('rule_applied', ''),
            'def_before': r.get('def_before', ''),
            'old_gloss': r.get('gloss_after', ''),
            'decision': decision,
            'reason': reason,
            'p4c_version': P4C_VERSION,
        }
        if decision == 'repair_gloss':
            assert new_gloss is not None
            sep, wc = _compute_separator_count(new_gloss)
            rec['new_gloss'] = new_gloss
            rec['separator'] = sep
            rec['gloss_word_count'] = wc
        else:
            rec['new_gloss'] = None
            rec['separator'] = 'none'
            rec['gloss_word_count'] = len(rec['old_gloss'].split())
        records.append(rec)

    # Validate
    from src.deck_builder.gloss_llm import validate_verdict
    for rec in records:
        if rec['decision'] == 'repair_gloss':
            sep = rec['separator']
            chunks = [c.strip() for c in re.split(r'\s*[|;]\s*', rec['new_gloss']) if c.strip()]
            v = validate_verdict(rec['word'], rec['new_gloss'], sep, len(chunks))
            if v:
                print(f'FATAL: repair_gloss {rec["word"]}|{rec["pos"]}|{rec["cefr"]} '
                      f'fails validate_verdict: {v}')
                return 1
            if rec['new_gloss'] == rec['old_gloss']:
                print(f'FATAL: repair_gloss {rec["word"]} has new_gloss == old_gloss')
                return 1
        else:
            if rec['new_gloss'] is not None:
                print(f'FATAL: keep_single {rec["word"]} has new_gloss set')
                return 1
    print(f'All {len(records)} ledger records validated ({sum(1 for r in records if r["decision"] == "repair_gloss")} repair + {sum(1 for r in records if r["decision"] == "keep_single")} keep).')

    # Write
    text = '\n'.join(json.dumps(r, ensure_ascii=False) for r in records) + '\n'
    LEDGER_PATH.write_text(text, encoding='utf-8')
    print(f'Wrote ledger: {LEDGER_PATH} ({len(records)} rows)')
    return 0


if __name__ == '__main__':
    sys.exit(main())