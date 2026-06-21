"""γ verdicts for 30-word pilot.

These were reasoned by MiniMax-M3 acting as γ LLM (per user decision 2026-06-16:
'bạn tự làm đi, không cần model bên ngoài').

Schema per cluster:
{
  "cluster_hash": "...",
  "word": "...",
  "decision": "merge" | "split" | "unsure",
  "confidence": 0.0-1.0,
  "reasoning": "1 sentence",
  "examples_substitutable_pct": 0-100,
  "merged_text": "single definition" | null
}
"""
VERDICTS = [
    # 1. abortion: deliberate ending vs medical operation. 100% substitutable. MERGE.
    {
        "cluster_hash": "32d9f8760e03dc21",
        "word": "abortion",
        "decision": "merge",
        "confidence": 0.95,
        "reasoning": "Both senses mean 'ending a pregnancy early' — one is the deliberate act, the other is the medical procedure. A learner can grasp both with one definition.",
        "examples_substitutable_pct": 100,
        "merged_text": "the deliberate ending of a pregnancy, whether by medical operation or other means",
    },
    # 2. absent: not in a place (illness) vs not present in something (abstract)
    {
        "cluster_hash": "5410d88ec50df0b3",
        "word": "absent",
        "decision": "split",
        "confidence": 0.85,
        "reasoning": "Sense 1 is concrete (absent from work), sense 2 is abstract (love absent from childhood). A learner needs separate examples.",
        "examples_substitutable_pct": 50,
        "merged_text": None,
    },
    # 3. absorb: take in liquid vs take in heat/energy. Both = "take in". MERGE.
    {
        "cluster_hash": "8291a0ad6dff780d",
        "word": "absorb",
        "decision": "merge",
        "confidence": 0.9,
        "reasoning": "Both senses are 'take in' — one is substances (liquid, gas), the other is energy (heat, light, sound). A single 'take in' definition covers both.",
        "examples_substitutable_pct": 90,
        "merged_text": "to take in a substance or a form of energy from the surface or space around",
    },
    # 4. abstract: 3 senses (general ideas / exists in thought / artistic non-representational)
    {
        "cluster_hash": "381f9f9377991fba",
        "word": "abstract",
        "decision": "split",
        "confidence": 0.8,
        "reasoning": "Sense 3 (art) is meaningfully different from senses 0+1 (general idea). Conservative: keep 3 separate. (Senses 0+1 could be merged but pipeline requires binary verdict.)",
        "examples_substitutable_pct": 60,
        "merged_text": None,
    },
    # 5. access: opportunity/right to use vs way of entering. Different. SPLIT.
    {
        "cluster_hash": "75576d481abb9bbd",
        "word": "access",
        "decision": "split",
        "confidence": 0.9,
        "reasoning": "Sense 1 is permission/right to use (access to info), sense 2 is a physical entry route (wheelchair access). A learner needs both cards.",
        "examples_substitutable_pct": 30,
        "merged_text": None,
    },
    # 6. accommodation: a place to live vs B&B/overnight. 80% substitutable. MERGE.
    {
        "cluster_hash": "78a1433476b5090f",
        "word": "accommodation",
        "decision": "merge",
        "confidence": 0.8,
        "reasoning": "Sense 1 covers hotels, rented, alternative, first-class — sense 2 (B&B, overnight boat) is a subset. One 'place to stay' definition works for most examples.",
        "examples_substitutable_pct": 85,
        "merged_text": "a place to live, work, or stay, especially when you are away from home",
    },
    # 7. accumulate: gradually get more vs gradually increase. Same. MERGE.
    {
        "cluster_hash": "660571d04b75d7fd",
        "word": "accumulate",
        "decision": "merge",
        "confidence": 0.95,
        "reasoning": "Both senses mean 'to gradually gather more over time'. Sense 1 (collect) and sense 2 (build up) are the same direction of the same concept.",
        "examples_substitutable_pct": 100,
        "merged_text": "to gradually get more and more of something, or to gradually increase in amount, over a period of time",
    },
    # 8. strip: long narrow piece (material) vs long narrow area (land/sea). SPLIT.
    {
        "cluster_hash": "07b2268c1321e791",
        "word": "strip",
        "decision": "split",
        "confidence": 0.95,
        "reasoning": "Sense 1 is a physical object (paper, cloth, meat), sense 2 is a geographic area (Gaza Strip). Different domains.",
        "examples_substitutable_pct": 20,
        "merged_text": None,
    },
    # 9. theoretical: connected with ideas/principles vs could possibly exist (unlikely). SPLIT.
    {
        "cluster_hash": "b8b1c1b644d4997f",
        "word": "theoretical",
        "decision": "split",
        "confidence": 0.95,
        "reasoning": "Sense 1 is academic/philosophical (theoretical physics), sense 2 is hypothetical (theoretical possibility). Different uses.",
        "examples_substitutable_pct": 30,
        "merged_text": None,
    },
    # 10. embarrassing: making you feel shy/ashamed vs causing somebody to look stupid. SPLIT.
    {
        "cluster_hash": "dfe9a6104f6420c7",
        "word": "embarrassing",
        "decision": "split",
        "confidence": 0.8,
        "reasoning": "Sense 1 is personal (an embarrassing moment), sense 2 is reputational/political (an embarrassing position). Different registers, different examples.",
        "examples_substitutable_pct": 50,
        "merged_text": None,
    },
    # 11. independence: 3 senses (political freedom / time of political freedom / personal autonomy). SPLIT.
    {
        "cluster_hash": "a97420ffce986dd8",
        "word": "independence",
        "decision": "split",
        "confidence": 0.85,
        "reasoning": "Senses 0+1 are about a country's political freedom, sense 2 is personal autonomy (financial independence, valuing one's own independence). Different domains.",
        "examples_substitutable_pct": 50,
        "merged_text": None,
    },
    # 12. spring (verb): move suddenly quickly vs move suddenly violently. 95%. MERGE.
    {
        "cluster_hash": "4edcf3f4034c2a2b",
        "word": "spring",
        "decision": "merge",
        "confidence": 0.95,
        "reasoning": "Both senses are 'sudden quick movement' — one emphasizes direction, the other emphasizes force. A single 'sudden quick move' works for both.",
        "examples_substitutable_pct": 95,
        "merged_text": "to move suddenly and quickly, often in one swift motion",
    },
    # 13. inspect: look closely to check vs officially visit to check. SPLIT.
    {
        "cluster_hash": "7133ab448e325104",
        "word": "inspect",
        "decision": "split",
        "confidence": 0.8,
        "reasoning": "Sense 1 is personal examination (inspect your work), sense 2 is official/institutional (inspect a school, hotel). Different context and authority.",
        "examples_substitutable_pct": 50,
        "merged_text": None,
    },
    # 14. station: train stop vs bus stop. Same concept, different vehicle. MERGE.
    {
        "cluster_hash": "a510cd3bc7160d31",
        "word": "station",
        "decision": "merge",
        "confidence": 0.95,
        "reasoning": "Both are 'a place where public transport stops' — train vs bus is incidental. A learner needs one card for 'public transport stop'.",
        "examples_substitutable_pct": 95,
        "merged_text": "a place where public transport vehicles (such as trains or buses) stop to pick up and drop off passengers, and the buildings connected with this",
    },
    # 15. sole: bottom of foot vs bottom of shoe. MERGE.
    {
        "cluster_hash": "a439946d39371f2a",
        "word": "sole",
        "decision": "merge",
        "confidence": 0.9,
        "reasoning": "Both senses are 'the bottom of a foot/shoe'. A learner can grasp both with one definition that covers foot, shoe, and sock bottoms.",
        "examples_substitutable_pct": 90,
        "merged_text": "the bottom part of a foot, shoe, or sock",
    },
    # 16. missing: 4 senses (cannot be found / not at home / not present after accident / not included). SPLIT.
    {
        "cluster_hash": "bf800e4e09e1de88",
        "word": "missing",
        "decision": "split",
        "confidence": 0.95,
        "reasoning": "4 distinct senses spanning 'lost item', 'absent person', 'military MIA', and 'not on a list'. Each needs its own example set.",
        "examples_substitutable_pct": 30,
        "merged_text": None,
    },
    # 17. structure: thing made of parts (building) vs state of being organized. SPLIT.
    {
        "cluster_hash": "3967ae0f18452a1d",
        "word": "structure",
        "decision": "split",
        "confidence": 0.9,
        "reasoning": "Sense 1 is a physical thing (building, sandcastle), sense 2 is the abstract state of being well-organized (essay needs structure). Different POS-like uses.",
        "examples_substitutable_pct": 30,
        "merged_text": None,
    },
    # 18. fond: warm feelings for person vs finding something pleasant. MERGE.
    {
        "cluster_hash": "b40b9af0fa787d9e",
        "word": "fond",
        "decision": "merge",
        "confidence": 0.9,
        "reasoning": "Both senses are 'feeling warm liking/affection' — one is for people, the other is for activities/things. A 'warm liking' definition covers both.",
        "examples_substitutable_pct": 90,
        "merged_text": "feeling warm affection or a strong liking for someone or something",
    },
    # 19. parallel: similar person/situation vs similar features. MERGE.
    {
        "cluster_hash": "8ffd29e5b87799d6",
        "word": "parallel",
        "decision": "merge",
        "confidence": 0.9,
        "reasoning": "Both senses mean 'something very similar' — sense 1 is a noun referring to a person/situation, sense 2 generalizes to features. A 'similar thing' definition covers both.",
        "examples_substitutable_pct": 95,
        "merged_text": "a person, situation, event, or feature that is very similar to another, especially one in a different place or time",
    },
    # 20. tap: hit quickly and lightly vs hit fingers/feet gently. MERGE.
    {
        "cluster_hash": "d84a882ab3c09526",
        "word": "tap",
        "decision": "merge",
        "confidence": 0.95,
        "reasoning": "Both senses are 'hit lightly, often repeatedly' — sense 1 is a single hit (tap a door), sense 2 is repeated/gentle (tapping fingers). Same gesture family.",
        "examples_substitutable_pct": 95,
        "merged_text": "to hit something lightly and quickly, often repeatedly or to a rhythm",
    },
    # 21. epidemic: many disease cases vs rapid increase in bad thing. SPLIT.
    {
        "cluster_hash": "d1e6575d05af04f6",
        "word": "epidemic",
        "decision": "split",
        "confidence": 0.85,
        "reasoning": "Sense 1 is literal medical (flu epidemic), sense 2 is metaphorical (epidemic of crime). A learner needs both contexts.",
        "examples_substitutable_pct": 50,
        "merged_text": None,
    },
    # 22. approval: good/acceptable feeling vs agreement/permission. SPLIT.
    {
        "cluster_hash": "eacc71810ff15eb5",
        "word": "approval",
        "decision": "split",
        "confidence": 0.85,
        "reasoning": "Sense 1 is a positive opinion/feeling (nod in approval), sense 2 is formal consent/permission (committee approval). Different functions.",
        "examples_substitutable_pct": 40,
        "merged_text": None,
    },
    # 23. swim: move through water / spend time swimming / move through water (generic). MERGE.
    {
        "cluster_hash": "bfc3bb8fd669a7b4",
        "word": "swim",
        "decision": "merge",
        "confidence": 0.95,
        "reasoning": "All 3 senses are 'to be in water and move' — sense 1 is the action, sense 2 is the leisure activity, sense 3 is generic motion through water. One definition covers all.",
        "examples_substitutable_pct": 95,
        "merged_text": "to move through water using your arms and legs, or to spend time doing this for pleasure",
    },
    # 24. death: fact of dying/being killed vs end of life/state of being dead. MERGE.
    {
        "cluster_hash": "bc95ba0f7a6692fb",
        "word": "death",
        "decision": "merge",
        "confidence": 0.9,
        "reasoning": "Both senses are 'end of life' — one emphasizes the event, the other the state. A learner can grasp both with 'end of life' definition.",
        "examples_substitutable_pct": 90,
        "merged_text": "the end of life; the fact or state of someone being dead",
    },
]


def write_verdicts_json(out_path: str) -> None:
    import json
    from pathlib import Path
    out = {
        "note": "γ verdicts from MiniMax-M3 (this session), 2026-06-16. Schema per cluster_hash.",
        "verdicts": VERDICTS,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    write_verdicts_json('data/simplify_diff/gamma_pilot_30_verdicts.json')
    print(f'Wrote {len(VERDICTS)} verdicts to data/simplify_diff/gamma_pilot_30_verdicts.json')
