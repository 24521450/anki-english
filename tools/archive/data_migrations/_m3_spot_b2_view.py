"""View samples 25-49 for batch B2."""
import json
samples = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/spot_audit_sample.jsonl', encoding='utf-8')]

for s in samples[25:50]:
    print(f'[{s["sample_idx"]}] {s["word"]} ({s["pos"]}, {s["cefr"]})')
    print(f'    def: {s["def_before"][:120]}')
    print(f'    gloss: {s["gloss_after"]!r} [sep={s.get("separator")}, rule={s.get("rule_applied")}]')
    print()
