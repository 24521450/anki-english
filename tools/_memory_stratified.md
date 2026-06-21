### Stratified rate vs diluted rate — don't average across applicability (2026-06-18)
Type: discipline-rule

**The trap (verified 2026-06-18, ielts-deck):** Spot-audit reported "2% Rule A violation rate" but the 100 samples were 98% 1-sense (Rule A inapplicable) + 2% multi-sense (Rule A applicable). True rates:
- 1-sense: 1% tone/accuracy issues
- multi-sense: 52.6% Rule A violations
- "2% overall" is meaningless — different denominators, different categories

**Rule:** when reporting a rate, ALWAYS stratify by whether the rule applies to the sample. A 2% rate on 100 mixed samples hides a 50% rate on the 5 actually-applicable samples. Don't dilute.

**Anti-pattern (my mistake):** "98% are 1-chunk for genuinely 1-sense defs. No Rule B under-collapse evidence." — looked like good news, but actually meant: my sample was selection-biased toward cases where Rule B literally couldn't fire. Sample size of the APPLICABLE subset (Rule B cases) was 0, so I had 0% rate by construction, not by quality.

**Fix:** for any rate measurement:
1. Stratify: separate sample into (rule-applicable, rule-not-applicable)
2. Report both rates separately with N for each
3. Conditional rate on applicable subset is the meaningful number
4. Overall rate is just a weighted average (less useful)

**Cross-project:** any time the rule has different denominators (e.g. "Rule X only fires on multi-class problems", "anomaly only detectable in subset Y"), stratify before reporting. Otherwise the number is misleading.

**Companion discipline:** when user pushes back on a rate with "but the rule doesn't apply to N% of samples", always re-stratify. Don't defend the original sample as "still valid".
