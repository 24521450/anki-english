# Detailed Audit Results

This file lists all discrepancies found when comparing `audit_full_deck_v2.jsonl` with `oxford_merged.jsonl`.

## Summary of Categories

- **Exact / Substring Match**: 2482
- **Wording Difference Only**: 1
- **True Missing Senses**: 10
- **Capped Senses**: 3
- **Word Not Found**: 32

---

## 1. True Missing Senses
There are **10** cases where Oxford definitions are missing/replaced by legacy text in the card definition.

### 1. ambiguous (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `able to be understood in more than one way, or not clearly stated or defined`
- **Expected from Oxford**: ['that can be understood in more than one way; having different meanings', 'not clearly stated or defined']
- **Missing Senses**: ['that can be understood in more than one way; having different meanings']

### 2. corrosive (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `tending to destroy or damage something gradually, whether by chemical action or other means`
- **Expected from Oxford**: ['tending to destroy something slowly by chemical action', 'tending to damage something gradually']
- **Missing Senses**: ['tending to destroy something slowly by chemical action', 'tending to damage something gradually']

### 3. ingrained (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `deeply established and difficult to change or remove`
- **Expected from Oxford**: ['that has existed for a long time and is therefore difficult to change', 'under the surface of something and therefore difficult to get rid of']
- **Missing Senses**: ['that has existed for a long time and is therefore difficult to change', 'under the surface of something and therefore difficult to get rid of']

### 4. potent (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `having a strong effect or power`
- **Expected from Oxford**: ['having a strong effect on your body or mind', 'powerful']
- **Missing Senses**: ['having a strong effect on your body or mind', 'powerful']

### 5. counter (argue against) (verb, C1)
- **Audit Definition (def_before)**: `reply proving wrong; reduce bad effects`
- **Expected from Oxford**: ['to reply to somebody by trying to prove that what they said is not true', 'to do something to reduce or prevent the bad effects of something']
- **Missing Senses**: ['to reply to somebody by trying to prove that what they said is not true', 'to do something to reduce or prevent the bad effects of something']

### 6. counter (long flat surface) (noun, B2)
- **Audit Definition (def_before)**: `service counter`
- **Expected from Oxford**: ['a long flat surface over which goods are sold or business is done in a shop, bank, etc.', 'a flat surface in a kitchen for preparing food on']
- **Missing Senses**: ['a long flat surface over which goods are sold or business is done in a shop, bank, etc.', 'a flat surface in a kitchen for preparing food on']

### 7. grave (for dead person) (noun, C1)
- **Audit Definition (def_before)**: `burial site`
- **Expected from Oxford**: ['a place in the ground where a dead person is buried', 'a way of referring to death or a person’s death']
- **Missing Senses**: ['a place in the ground where a dead person is buried', 'a way of referring to death or a person’s death']

### 8. sanity (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `the state of having a healthy, sound, or sensible mind`
- **Expected from Oxford**: ['the state of having a healthy mind', 'the state of being sensible and reasonable']
- **Missing Senses**: ['the state of having a healthy mind', 'the state of being sensible and reasonable']

### 9. strip (long narrow piece) (noun, C1)
- **Audit Definition (def_before)**: `narrow piece`
- **Expected from Oxford**: ['a long narrow piece of paper, metal, cloth, etc.', 'a long narrow area of land, sea, etc.']
- **Missing Senses**: ['a long narrow area of land, sea, etc.']

### 10. strip (remove clothes/a layer) (verb, C1)
- **Audit Definition (def_before)**: `remove`
- **Expected from Oxford**: ['to take off all or most of your clothes or another person’s clothes', 'to remove a layer from something, especially so that it is completely exposed', 'to remove all the things from a place and leave it empty']
- **Missing Senses**: ['to take off all or most of your clothes or another person’s clothes']

---

## 2. Wording Differences
There are **1** cases where the definition is present but has minor wording/formatting differences.

### 1. grave (serious) (adjective, C1)
- **Audit Definition (def_before)**: `serious`
- **Expected from Oxford**: ['very serious and important; giving you a reason to feel worried']
- **Wording Differences**: 'very serious and important; giving you a reason to feel worried' vs 'serious'

---

## 3. Capped Senses
There are **3** cases where the card definition has $\ge 3$ senses and excess Oxford senses were capped (expected behaviour).

### 1. curse (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `a rude or offensive word or phrase that some people use when they are very angry|a word or phrase that has a magic power to make something bad happen|something that causes harm or evil`
- **Expected from Oxford**: ['a rude or offensive word or phrase that some people use when they are very angry', 'a word or phrase that has a magic power to make something bad happen', 'something that causes harm or evil', 'menstruation (= the process or time of menstruating)']
- **Capped Senses**: ['menstruation (= the process or time of menstruating)']

### 2. sterile (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `not able to produce children or young animals|completely clean and free from bacteria|not producing any useful result`
- **Expected from Oxford**: ['not able to produce children or young animals', 'completely clean and free from bacteria', 'not producing any useful result', 'not having individual personality, imagination or new ideas', 'not good enough to produce crops']
- **Capped Senses**: ['not having individual personality, imagination or new ideas', 'not good enough to produce crops']

### 3. superficially (adverb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `in a way that appears to be true, real or important until you look at it more carefully|not carefully or completely; in a way that only considers what is obvious|not seriously or to a great degree; in a way that only affects the surface`
- **Expected from Oxford**: ['in a way that appears to be true, real or important until you look at it more carefully', 'not carefully or completely; in a way that only considers what is obvious', 'not seriously or to a great degree; in a way that only affects the surface', 'in a way that is not serious or important and lacks any depth of understanding or feeling']
- **Capped Senses**: ['in a way that is not serious or important and lacks any depth of understanding or feeling']

---

## 4. Word Not Found
There are **32** cases where the word could not be found directly in `oxford_merged.jsonl` (usually inflected forms, spelling variations, or idioms).

### 1. accused (noun, C1)
- **Audit Definition (def_before)**: `to say that sb has done sth wrong or is guilty of sth`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 2. blink of an eye (idiom, UNCLASSIFIED)
- **Audit Definition (def_before)**: `extremely quickly.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 3. byproducts (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `a thing that happens, often unexpectedly, as the result of sth else`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 4. carrying capacity (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `The maximum number of people, animals, or crops that a particular area can support.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 5. criteria (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `standards by which sth is judged, decided, or graded.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 6. curated (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `an assistant to a vicar (= a priest, who is in charge of the church or churches in a particular area) | sth that has some good parts and some bad ones`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 7. dabbler (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `a person who follows a pursuit without serious commitment or knowledge`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 8. designated (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `[formal] chosen to do a job but not yet having officially started it`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 9. destabilizing (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `to make a system, country, government, etc. become less well established or successful`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 10. eliminated (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `to stop considering that sb/sth might be responsible for sth or chosen for sth | to defeat a person or a team so that they no longer take part in a competition, etc.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 11. evolved (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `to develop gradually, especially from a simple to a more complicated form; to develop sth in this way | [biology] to develop over time, often many generations, into forms that are better adapted to survive changes in their environment`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 12. extrapolated (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `[formal] to estimate sth or form an opinion about sth, using the facts that you have now and that are relevant to one situation and supposing that they will be relevant to the new one`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 13. foraging (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `food for horses and cows`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 14. gouging (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `a sharp tool for making hollow areas in wood | a deep, narrow hole or cut in a surface`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 15. harbor (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `To contain or keep sth/sb within.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 16. harbor (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `to contain sth, especially sth hidden or dangerous (in this context, to hold or contain life).`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 17. have the floor (phrase, UNCLASSIFIED)
- **Audit Definition (def_before)**: `To have the right to speak at a public meeting or in a debate.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 18. hyperfocus (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `to concentrate on sth very intensely, to the exclusion of other things.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 19. interweave (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `twisted together or connected closely.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 20. invading (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `to enter a place in large numbers, especially in a way that causes damage or problems | to affect sth in an unpleasant or annoying way`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 21. ligaments (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `[formal, informal] a strong band of tissue in the body that connects bones and supports organs and keeps them in position`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 22. logistical (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `Relating to the careful organization of a complicated activity.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 23. randomized (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `[specialist] to use a method in an experiment, a piece of research, etc. that gives every item an equal chance of being considered; to put things in a random order`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 24. relay (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `a device or station that receives a signal and transmits it to another. to pass sth along.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 25. shortsighted (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `lacking imagination or foresight. failing to consider future consequences`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 26. shunned (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `persistently avoided, ignored, or rejected`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 27. soullessly (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `in a way that shows no human influence, sensitivity, or character.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 28. unfiltered (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `not having had anything removed or changed`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 29. untethered (adjective, UNCLASSIFIED)
- **Audit Definition (def_before)**: `not tied or limited to a particular thing.`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 30. vertebrae (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `The small bones that form the spine (backbone).`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 31. wellbeing (noun, UNCLASSIFIED)
- **Audit Definition (def_before)**: `general health and happiness`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl

### 32. zigzagging (verb, UNCLASSIFIED)
- **Audit Definition (def_before)**: `moving by going from side to side, or changing direction frequently`
- **Reason**: Word/Idiom not found in oxford_merged.jsonl
