"""Fix 117 narrow self-ref card verdicts by updating gloss_all_verdicts.json."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))
from src.deck_builder.gloss_llm import GlossVerdict, detect_category, validate_verdict

VERDICTS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_all_verdicts.json'

REPLACEMENTS = {
    ("contractor", "noun", "C1"): ("hired worker; service provider", "2sense_samedomain"),
    ("coordination", "noun", "C1"): ("efficient cooperation", ""),
    ("creativity", "noun", "B2"): ("inventiveness; imagination", "2sense_samedomain"),
    ("delegation", "noun", "C1"): ("representative group; deputation", "2sense_samedomain"),
    ("deprivation", "noun", "UNCLASSIFIED"): ("hardship; extreme poverty", "2sense_samedomain"),
    ("diagnosis", "noun", "C1"): ("identifying illness", ""),
    ("disposal", "noun", "C1"): ("discarding; throwing away", "2sense_samedomain"),
    ("dominance", "noun", "C1"): ("superiority; powerful control", "2sense_samedomain"),
    ("effectiveness", "noun", "C1"): ("producing success; efficiency", "2sense_samedomain"),
    ("enforcement", "noun", "C1"): ("compelling obedience", ""),
    ("excellence", "noun", "C1"): ("high quality; greatness", "2sense_samedomain"),
    ("exclusion", "noun", "C1"): ("barring entry | school ban", "2sense_distinct"),
    ("exhausted", "adjective", "UNCLASSIFIED"): ("extremely tired; worn out", "2sense_samedomain"),
    ("fame", "noun", "B2"): ("celebrity status; renown", "2sense_samedomain"),
    ("fermentation", "noun", "UNCLASSIFIED"): ("chemical change to alcohol", ""),
    ("formation", "noun", "B2"): ("creation; development", "2sense_samedomain"),
    ("frustration", "noun", "C1"): ("feeling annoyed; disappointment", "2sense_samedomain"),
    ("goodness", "noun", "B2"): ("moral excellence; kindness", "2sense_samedomain"),
    ("harassment", "noun", "C1"): ("intimidation; aggressive pressure", "2sense_samedomain"),
    ("honesty", "noun", "B2"): ("truthfulness; integrity", "2sense_samedomain"),
    ("hunger", "noun", "B2"): ("starvation | desire to eat", "2sense_distinct"),
    ("implementation", "noun", "C1"): ("execution; putting into practice", "2sense_samedomain"),
    ("imprisonment", "noun", "C1"): ("confinement; locking up", "2sense_samedomain"),
    ("inability", "noun", "C1"): ("lack of capability", ""),
    ("insertion", "noun", "C1"): ("placing inside; added piece", "2sense_samedomain"),
    ("interaction", "noun", "B2"): ("communication; socializing", "2sense_samedomain"),
    ("interference", "noun", "C1"): ("unwanted involvement; meddling", "2sense_samedomain"),
    ("invasion", "noun", "B2"): ("military entry; hostile takeover", "2sense_samedomain"),
    ("investigator", "noun", "C1"): ("detective; fact finder", "2sense_samedomain"),
    ("ironic", "adjective", "C1"): ("sarcastic | unexpected and funny", "2sense_distinct"),
    ("irony", "noun", "C1"): ("situational twist | sarcastic language", "2sense_distinct"),
    ("long-time", "adjective", "C1"): ("lasting many years; enduring", "2sense_samedomain"),
    ("magical", "adjective", "C1"): ("mystical | wonderful", "2sense_distinct"),
    ("mediocre", "adjective", "UNCLASSIFIED"): ("average; second-rate", "2sense_samedomain"),
    ("membership", "noun", "B2"): ("belonging to a group", ""),
    ("merger", "noun", "C1"): ("combining businesses; union", "2sense_samedomain"),
    ("merit", "noun", "C1"): ("worth; deserving praise", "2sense_samedomain"),
    ("minimal", "adjective", "C1"): ("smallest possible; tiny", "2sense_samedomain"),
    ("mining", "noun", "C1"): ("underground resource extraction", ""),
    ("moderate", "adjective", "C1"): ("reasonable; middle-of-the-road", "2sense_samedomain"),
    ("momentum", "noun", "C1"): ("forward drive; speed of movement", "2sense_samedomain"),
    ("mundane", "adjective", "UNCLASSIFIED"): ("ordinary; boring", "2sense_samedomain"),
    ("nod", "verb", "C1"): ("signal agreement with head", ""),
    ("nomination", "noun", "C1"): ("proposing candidate; award suggestion", "2sense_samedomain"),
    ("nominee", "noun", "C1"): ("proposed person; award candidate", "2sense_samedomain"),
    ("non-profit", "adjective", "C1"): ("charitable; not for gain", "2sense_samedomain"),
    ("notable", "adjective", "C1"): ("remarkable; significant", "2sense_samedomain"),
    ("nutritious", "adjective", "UNCLASSIFIED"): ("healthy; nourishing", "2sense_samedomain"),
    ("outsourcing", "noun", "UNCLASSIFIED"): ("subcontracting services", ""),
    ("ownership", "noun", "B2"): ("possession; legal title", "2sense_samedomain"),
    ("participation", "noun", "B2"): ("taking part; involvement", "2sense_samedomain"),
    ("patience", "noun", "B2"): ("staying calm; endurance", "2sense_samedomain"),
    ("perception", "noun", "B2"): ("mental image; understanding", "2sense_samedomain"),
    ("permission", "noun", "A2"): ("authorization; consent", "2sense_samedomain"),
    ("philosopher", "noun", "C1"): ("thinker; ethical scholar", "2sense_samedomain"),
    ("precision", "noun", "C1"): ("accuracy; exactness", "2sense_samedomain"),
    ("pregnancy", "noun", "C1"): ("state of expecting baby", ""),
    ("presence", "noun", "B2"): ("attendance; being there", "2sense_samedomain"),
    ("preservation", "noun", "C1"): ("conservation; keeping safe", "2sense_samedomain"),
    ("prevalence", "noun", "C1"): ("commonness; wide occurrence", "2sense_samedomain"),
    ("prevention", "noun", "C1"): ("stopping bad events", ""),
    ("privatization", "noun", "C1"): ("selling state assets", ""),
    ("productive", "adjective", "C1"): ("fruitful; high-yielding", "2sense_samedomain"),
    ("programming", "noun", "B2"): ("writing software", ""),
    ("prosperity", "noun", "C1"): ("wealth; financial success", "2sense_samedomain"),
    ("publication", "noun", "B2"): ("releasing book; printed work", "2sense_samedomain"),
    ("pursuit", "noun", "B2"): ("chasing; seeking", "2sense_samedomain"),
    ("rebuild", "verb", "B2"): ("reconstruct; restore", "2sense_samedomain"),
    ("recognition", "noun", "B2"): ("identification; remembering", "2sense_samedomain"),
    ("recovery", "noun", "B2"): ("healing; getting better", "2sense_samedomain"),
    ("redistribution", "noun", "UNCLASSIFIED"): ("reallocating shares; sharing out", "2sense_samedomain"),
    ("registration", "noun", "B2"): ("signing up; official logging", "2sense_samedomain"),
    ("rehabilitation", "noun", "C1"): ("recovery therapy; training", "2sense_samedomain"),
    ("reluctance", "noun", "UNCLASSIFIED"): ("unwillingness; hesitation", "2sense_samedomain"),
    ("removal", "noun", "C1"): ("taking away; extraction", "2sense_samedomain"),
    ("reportedly", "adverb", "C1"): ("allegedly; supposedly", "2sense_samedomain"),
    ("retaliate", "verb", "UNCLASSIFIED"): ("strike back; take revenge", "2sense_samedomain"),
    ("retirement", "noun", "B2"): ("stopping work; pension years", "2sense_samedomain"),
    ("risky", "adjective", "B2"): ("dangerous; unsafe", "2sense_samedomain"),
    ("sabotage", "noun", "C2"): ("deliberate destruction; disruption", "2sense_samedomain"),
    ("sabotage", "noun", "UNCLASSIFIED"): ("deliberate destruction; disruption", "2sense_samedomain"),
    ("sanity", "noun", "UNCLASSIFIED"): ("healthy mind; rationality", "2sense_samedomain"),
    ("screening", "noun", "B2"): ("movie showing; broadcasting", "2sense_samedomain"),
    ("self-preservation", "noun", "UNCLASSIFIED"): ("protecting oneself; survival instinct", "2sense_samedomain"),
    ("shrug", "verb", "C1"): ("raise shoulders in indifference", ""),
    ("slouch", "verb", "UNCLASSIFIED"): ("sit lazily; stoop forward", "2sense_samedomain"),
    ("solitude", "noun", "UNCLASSIFIED"): ("peaceful isolation; being alone", "2sense_samedomain"),
    ("specialized", "adjective", "C1"): ("custom-made; focused", "2sense_samedomain"),
    ("speculation", "noun", "B2"): ("conjecture; guessing", "2sense_samedomain"),
    ("storage", "noun", "C1"): ("keeping items | data saving", "2sense_distinct"),
    ("structural", "adjective", "C1"): ("organizational; construction-related", "2sense_samedomain"),
    ("stunning", "adjective", "B2"): ("beautiful; impressive", "2sense_samedomain"),
    ("subtle", "adjective", "C1"): ("hard to notice | clever and indirect", "2sense_distinct"),
    ("successive", "adjective", "C1"): ("consecutive; sequential", "2sense_samedomain"),
    ("super", "adjective", "B2"): ("excellent; wonderful", "2sense_samedomain"),
    ("surveillance", "noun", "C1"): ("monitoring suspects; observation", "2sense_samedomain"),
    ("survival", "noun", "B2"): ("continuing to exist; living on", "2sense_samedomain"),
    ("symbolic", "adjective", "C1"): ("representational; figurative", "2sense_samedomain"),
    ("tactical", "adjective", "C1"): ("strategic; plan-related", "2sense_samedomain"),
    ("terrain", "noun", "C1"): ("ground landscape; land features", "2sense_samedomain"),
    ("terrify", "verb", "B2"): ("frighten greatly; scare", "2sense_samedomain"),
    ("theatrical", "adjective", "C1"): ("drama-related; stage-related", "2sense_samedomain"),
    ("theoretical", "adjective", "C1"): ("conceptual; speculative", "2sense_samedomain"),
    ("therapist", "noun", "B2"): ("treatment specialist; counselor", "2sense_samedomain"),
    ("toxicity", "noun", "C2"): ("poisonous nature; poison level", "2sense_samedomain"),
    ("toxicity", "noun", "UNCLASSIFIED"): ("poisonous nature; poison level", "2sense_samedomain"),
    ("transparency", "noun", "C1"): ("openness; ease of understanding", "2sense_samedomain"),
    ("typical", "adjective", "A2"): ("usual; characteristic", "2sense_samedomain"),
    ("uncertainty", "noun", "B2"): ("lack of conviction; doubt", "2sense_samedomain"),
    ("unfairness", "noun", "UNCLASSIFIED"): ("injustice; biased treatment", "2sense_samedomain"),
    ("unity", "noun", "B2"): ("oneness; cooperation", "2sense_samedomain"),
    ("validity", "noun", "C1"): ("legal status | logical truth", "2sense_distinct"),
    ("voting", "noun", "B2"): ("casting a ballot; election choice", "2sense_samedomain"),
    ("vulnerability", "noun", "C1"): ("weakness; susceptibility", "2sense_samedomain"),
    ("warming", "noun", "B2"): ("heating up; rising temperature", "2sense_samedomain"),
    ("willingness", "noun", "C1"): ("readiness; eager consent", "2sense_samedomain"),
    ("wisdom", "noun", "B2"): ("good judgement; insight", "2sense_samedomain")
}


def main():
    print(f"Loading {VERDICTS_PATH}")
    with open(VERDICTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    verdicts = data["verdicts"]
    print(f"Loaded {len(verdicts)} verdicts")
    
    # Track which replacements matched
    matched_keys = set()
    
    updated_count = 0
    for v in verdicts:
        key = (v["word"], v["pos"], v["cefr"])
        if key in REPLACEMENTS:
            gloss, rule = REPLACEMENTS[key]
            
            # Validate before saving
            sep = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
            chunks = [c.strip() for c in gloss.replace('|', ';').split(';') if c.strip()]
            errs = validate_verdict(v["word"], gloss, sep, len(chunks))
            if errs:
                print(f"⚠️ Validation error for {key}: {errs}")
                sys.exit(1)
            
            # Update fields
            old_gloss = v.get("gloss", "")
            v["gloss"] = gloss
            v["decision"] = "gloss"
            v["confidence"] = 1.0
            v["reasoning"] = f"SELF-REF fix: {old_gloss!r} -> {gloss!r}"
            v["rule_applied"] = rule
            
            # Re-detect category
            # We need the definition to detect category. Let's find it in the jobs or use empty.
            # But we can just detect it or keep the original. Let's keep original or detect.
            # Wait, let's look up in the jobs file to get the definition for detect_category.
            
            matched_keys.add(key)
            updated_count += 1
            
    print(f"Updated {updated_count} verdicts")
    
    # Warn about unmatched keys
    unmatched = set(REPLACEMENTS.keys()) - matched_keys
    if unmatched:
        print(f"⚠️ Unmatched keys: {unmatched}")
        sys.exit(1)
        
    # Backup
    backup_path = VERDICTS_PATH.with_name("gloss_all_verdicts.json.bak_pre_self_ref_117_fix")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Backup saved to {backup_path.name}")
    
    # Save
    with open(VERDICTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {VERDICTS_PATH}")


if __name__ == "__main__":
    main()
