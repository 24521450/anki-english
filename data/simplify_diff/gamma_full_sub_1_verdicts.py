"""γ verdicts for FULL-RUN sub-batch 1 (100 clusters).

Reasoned by MiniMax-M3 (this session) 2026-06-16.
Schema frozen.
"""
VERDICTS = [
    # 1. devil: most powerful evil being vs evil spirit. Same. MERGE.
    {"word": "devil", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'an evil supernatural being' — sense 1 is THE Devil, sense 2 is devils (plural). Same concept.",
     "examples_substitutable_pct": 95,
     "merged_text": "an evil spirit, or the most powerful evil being (often called 'the Devil')"},
    # 2. port: town with harbour vs place for ships. Same. MERGE.
    {"word": "port", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a place where ships dock' — sense 1 is the city, sense 2 is the harbor. Same thing.",
     "examples_substitutable_pct": 95,
     "merged_text": "a town or harbor where ships load and unload goods"},
    # 3. challenge (noun): invitation to compete vs statement of refusal. Different. SPLIT.
    {"word": "challenge", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is an invitation (accept a challenge), sense 2 is a refusal statement (legal challenge). Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 4. reminder: thing that makes you remember vs letter for unpaid bill. Different. SPLIT.
    {"word": "reminder", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a memory aid (something reminds you), sense 2 is a specific notice (a bill reminder). Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 5. clue: 3 senses (police evidence / problem-solving / crossword hint). SPLIT.
    {"word": "clue", "decision": "split", "confidence": 0.8,
     "reasoning": "Three distinct uses: police investigation, scientific/life problem, crossword. Each has different contexts.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 6. obscure: not well known vs difficult to understand. Different. SPLIT.
    {"word": "obscure", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is fame (obscure poet), sense 2 is clarity (obscure lecture). Different (familiarity vs clarity).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 7. leadership: 3 senses (state of being leader / ability / group of leaders). SPLIT.
    {"word": "leadership", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: the state, the skill, and the group. Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 8. rule: statement of what may/must not be done vs grammar rule. Different. SPLIT.
    {"word": "rule", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is behavioral (rules of golf), sense 2 is linguistic (grammar rules). Different domains.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 9. merit: quality of being good vs a good feature. Same. MERGE.
    {"word": "merit", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'deserving praise' — sense 1 is the abstract quality, sense 2 is a specific feature.",
     "examples_substitutable_pct": 95,
     "merged_text": "the quality of being good and deserving praise, or a feature of something that deserves praise"},
    # 10. issue (verb): make known formally vs give officially. Same. MERGE.
    {"word": "issue", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'officially give out or make known' — sense 1 is statements, sense 2 is documents/licenses.",
     "examples_substitutable_pct": 100,
     "merged_text": "to officially make something known or to officially give something to someone"},
    # 11. formulate: create carefully vs express carefully. Same. MERGE.
    {"word": "formulate", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'carefully prepare or express' — sense 1 is a plan/policy, sense 2 is ideas in words.",
     "examples_substitutable_pct": 95,
     "merged_text": "to create or express something carefully, paying attention to detail"},
    # 12. explain: make easy to understand vs give a reason. Different. SPLIT.
    {"word": "explain", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is making something clear, sense 2 is justifying. Different (clarification vs justification).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 13. support (verb): agree with vs give help. Different. SPLIT.
    {"word": "support", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is endorsement (support an idea), sense 2 is practical help (support customers). Different.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 14. sailor: ship crew member vs boat sailor. Same. MERGE.
    {"word": "sailor", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a person who works on or sails a boat' — sense 1 is professional, sense 2 is recreational.",
     "examples_substitutable_pct": 100,
     "merged_text": "a person who works on a ship as a crew member, or who sails a boat"},
    # 15. medium: way of communicating vs something used for purpose. Same. MERGE.
    {"word": "medium", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'a means of communication or doing something' — sense 1 is mass media, sense 2 is the vehicle.",
     "examples_substitutable_pct": 95,
     "merged_text": "a way of communicating or doing something, such as a language, a tool, or a mass communication channel"},
    # 16. illusion: false idea/belief vs something that seems to exist. Different. SPLIT.
    {"word": "illusion", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a mental state (under the illusion), sense 2 is something external (mirror gives illusion of space). Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 17. plan: intention vs detailed set of actions. Different. SPLIT.
    {"word": "plan", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is a vague intention (plans for the summer), sense 2 is a detailed action plan. Different (intention vs scheme).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 18. confess: admit wrongdoing formally vs admit embarrassing thing. Same. MERGE.
    {"word": "confess", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'admit something' — sense 1 is crime, sense 2 is personal embarrassment. Same action.",
     "examples_substitutable_pct": 95,
     "merged_text": "to admit that you have done something wrong, illegal, or embarrassing"},
    # 19. ash: powder after burning vs what remains. Same. MERGE.
    {"word": "ash", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'the remains after burning' — sense 1 is the powder form, sense 2 is the larger remnants.",
     "examples_substitutable_pct": 100,
     "merged_text": "the grey or black powder or remains left after something has been burnt"},
    # 20. multiply: add number to itself vs increase. Different. SPLIT.
    {"word": "multiply", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is the mathematical operation, sense 2 is general increase. Different (math vs general).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 21. improvement: act of making better vs change that makes better. Same. MERGE.
    {"word": "improvement", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'the act or result of becoming better' — sense 1 is process, sense 2 is the change.",
     "examples_substitutable_pct": 100,
     "merged_text": "the act of making something better, or the change that makes it better"},
    # 22. spell (verb): 3 senses (write letters / form words / letters form words). SPLIT.
    {"word": "spell", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 0 (say letters) and sense 2 (letters form words) are related but sense 1 (general ability to spell) is about competence.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 23. essay: student writing vs published writing. Different. SPLIT.
    {"word": "essay", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is a student assignment, sense 2 is a published piece. Different contexts.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 24. expectation: 3 senses (belief will happen / hope / strong belief of how). SPLIT.
    {"word": "expectation", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: likelihood belief, hope, and standard/belief of how things should be. Distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 25. suck: 4 senses. SPLIT.
    {"word": "suck", "decision": "split", "confidence": 0.85,
     "reasoning": "Four senses: take in via mouth, keep in mouth and pull, take out (pump), pull by force (whirlpool). Too distinct to merge all.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 26. satisfy: 3 senses. SPLIT.
    {"word": "satisfy", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: please a person, provide what's needed, make certain. Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 27. liberal (noun): open-minded person vs progressive political person. Different. SPLIT.
    {"word": "liberal", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is a personality trait (tolerant), sense 2 is a political position (progressive). Different.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 28. leather: animal skin material vs clothes made of leather. Different. SPLIT.
    {"word": "leather", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is the material, sense 2 is a specific use (motorcycle clothing). Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 29. scare: situation of fear vs sudden feeling of fear. Same. MERGE.
    {"word": "scare", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'a feeling or situation of fear' — sense 1 is prolonged anxiety, sense 2 is a sudden moment.",
     "examples_substitutable_pct": 95,
     "merged_text": "a feeling of fear, or a situation in which people are anxious or frightened"},
    # 30. perception: 2 senses (senses vs understanding). Different. SPLIT.
    {"word": "perception", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is sensory (perception of reality), sense 2 is understanding/insight. Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 31. delicate: 6 senses. SPLIT.
    {"word": "delicate", "decision": "split", "confidence": 0.85,
     "reasoning": "Six senses covering fragility, health, beauty, craftsmanship, sensitivity, lightness. Too many to merge.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 32. route: way to get from place to place vs fixed path for bus. Same. MERGE.
    {"word": "route", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a way from one place to another' — sense 1 is general, sense 2 is a regular/fixed path.",
     "examples_substitutable_pct": 100,
     "merged_text": "a way that you follow to get from one place to another, whether planned or regular"},
    # 33. outlet: shop selling company's goods vs shop selling at reduced prices. Different. SPLIT.
    {"word": "outlet", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is a regular retail store for a brand, sense 2 is a discount store. Different business models.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 34. hollow (noun): lower area in ground vs hole inside something. Different. SPLIT.
    {"word": "hollow", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is an external dip/valley, sense 2 is an internal cavity. Different (outside vs inside).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 35. evolve: develop gradually vs develop over generations. Different. SPLIT.
    {"word": "evolve", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is general development (a company evolves), sense 2 is specifically biological evolution. Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 36. love (noun): 3 senses (caring/romantic/pleasure). SPLIT.
    {"word": "love", "decision": "split", "confidence": 0.8,
     "reasoning": "Three distinct senses: family love, romantic love, passion for activity. Each distinct.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 37. monument: building to remember famous person/event vs building of historical importance. Different. SPLIT.
    {"word": "monument", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is intentional memorial (statue, column), sense 2 is a building that just happened to become historical. Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 38. minimum: smallest possible amount vs extremely small amount. Same. MERGE.
    {"word": "minimum", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'the smallest possible amount' — sense 1 is the required or recorded minimum, sense 2 is a very small amount.",
     "examples_substitutable_pct": 100,
     "merged_text": "the smallest or lowest amount that is possible, required, or recorded"},
    # 39. family: 3 senses. SPLIT.
    {"word": "family", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: nuclear (parents+children), extended (incl. relations), and ancestral (related people). Distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 40. queen: female ruler vs wife of king. Different. SPLIT.
    {"word": "queen", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is a reigning female monarch, sense 2 is a queen consort (king's wife). Different (ruler vs consort).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 41. army: organized group of soldiers vs the military branch. Same. MERGE.
    {"word": "army", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a large organized group of soldiers' — sense 1 is a specific force, sense 2 is the institution.",
     "examples_substitutable_pct": 95,
     "merged_text": "a large organized group of soldiers who are trained to fight on land, considered as a specific force or as a branch of a country's armed forces"},
    # 42. infection: act of causing/getting disease vs illness caused by bacteria/virus. Different. SPLIT.
    {"word": "infection", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is the process (becoming infected), sense 2 is the resulting illness. Different (process vs condition).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 43. phrase: group of words vs small group of words in grammar. Different. SPLIT.
    {"word": "phrase", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is a meaningful word group (idiom, key phrase), sense 2 is a grammar term (noun phrase). Different (meaning vs structure).",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 44. recognition: accepting something is true vs public praise. Different. SPLIT.
    {"word": "recognition", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is acknowledging existence/truth, sense 2 is rewarding someone's work. Different (acknowledgment vs award).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 45. god: 2 senses (single God vs many gods). Different. SPLIT.
    {"word": "god", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is THE God (monotheism), sense 2 is a god within polytheism. Different theological frames.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 46. sail (verb): 3 senses. SPLIT.
    {"word": "sail", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: travel by boat, control/sail as sport, begin journey. Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 47. section: any part vs separate part of document. Different. SPLIT.
    {"word": "section", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is any part (of a road, plane), sense 2 is a division of a document/book. Different (physical vs textual).",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 48. specialist: expert vs medical doctor. Different. SPLIT.
    {"word": "specialist", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a general expert (Japanese history), sense 2 is specifically a medical specialist. Different (general vs medical).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 49. drama: play vs plays as literature. Same. MERGE.
    {"word": "drama", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'plays or the art of plays' — sense 1 is individual play, sense 2 is the literary form.",
     "examples_substitutable_pct": 95,
     "merged_text": "a play for theatre, television, or radio, or plays considered as a form of literature"},
    # 50. garden: area for flowers vs public park. Different. SPLIT.
    {"word": "garden", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a private yard for growing, sense 2 is a public park. Different (private vs public).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 51. strategy: process of planning vs military planning. Different. SPLIT.
    {"word": "strategy", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is general planning, sense 2 is specifically military planning. Different.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 52. earnings: worker's pay vs company profit. Different. SPLIT.
    {"word": "earnings", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is a person's income, sense 2 is a company's profit. Different (person vs company).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 53. protect: make sure not harmed vs make laws against harming. Different. SPLIT.
    {"word": "protect", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is guarding (people, jobs), sense 2 is legal protection (environment, species). Different.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 54. legislation: a law passed vs process of making laws. Different. SPLIT.
    {"word": "legislation", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is the law itself, sense 2 is the lawmaking process. Different (product vs process).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 55. stage: period in development vs separate part of process. Same. MERGE.
    {"word": "stage", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a part or period of a process' — sense 1 is a state, sense 2 is a discrete part. Same concept.",
     "examples_substitutable_pct": 100,
     "merged_text": "a period or a separate part that something passes through while developing or making progress"},
    # 56. provoke: cause reaction vs say something to annoy. Different. SPLIT.
    {"word": "provoke", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is causing a reaction (protest), sense 2 is deliberately annoying (provoked into violence). Different (cause vs provoke).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 57. crew: 3 senses. SPLIT.
    {"word": "crew", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: ship/plane workers, those excluding officers, and a special-skilled group. Distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 58. risk: possibility of something bad vs person/thing causing problems. Different. SPLIT.
    {"word": "risk", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a probability (fire risk), sense 2 is a hazard (the boxes are a fire risk). Different (possibility vs source).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 59. attractive: pleasant to look at (sexual) vs pleasant in general. Different. SPLIT.
    {"word": "attractive", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is physical/sexual attractiveness, sense 2 is general pleasantness (attractive garden, glasses). Different (sexual vs general).",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 60. sensitivity: 5 senses. SPLIT.
    {"word": "sensitivity", "decision": "split", "confidence": 0.85,
     "reasoning": "Five senses (understand others, art/music, easily offended, secret info, react to substances). Too distinct.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 61. memoir: person's life account vs account of place/event. Different. SPLIT.
    {"word": "memoir", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is about a person (his life), sense 2 is about a place/event. Different (person vs thing).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 62. travel (verb): go from place to place vs go at speed/direction. Different. SPLIT.
    {"word": "travel", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is going from one place to another, sense 2 is moving at speed (travel at 50 mph, news travels). Different (journey vs motion).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 63. odds: 3 senses. SPLIT.
    {"word": "odds", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: likelihood, difficult odds, betting ratio. Distinct.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 64. embassy: group of officials vs the building. Different. SPLIT.
    {"word": "embassy", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is the people, sense 2 is the building. Different (group vs place).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 65. sand: substance of fine grains vs large area of sand. Different. SPLIT.
    {"word": "sand", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is the material, sense 2 is a beach/desert area. Different (substance vs place).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 66. ordinary: not unusual vs no interesting features. Different. SPLIT.
    {"word": "ordinary", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is neutral (just normal), sense 2 is mildly negative (boring, plain). Different valences.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 67. isolation: act/state of being separate vs being alone/lonely. Different. SPLIT.
    {"word": "isolation", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is physical/political separation, sense 2 is emotional loneliness. Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 68. confusion: 4 senses. SPLIT.
    {"word": "confusion", "decision": "split", "confidence": 0.85,
     "reasoning": "Four senses: uncertainty, mistake about identity, embarrassment, chaos. Too many.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 69. tendency: likelihood to behave a way vs new custom developing. Different. SPLIT.
    {"word": "tendency", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is individual behavior, sense 2 is societal trend. Different scales.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 70. ruin (verb): damage badly vs make lose money/position. Same. MERGE.
    {"word": "ruin", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'destroy or severely damage' — sense 1 is physical/abstract (trip, chance), sense 2 is financial/social.",
     "examples_substitutable_pct": 90,
     "merged_text": "to damage or destroy something so badly that it loses all value, money, position, or pleasure"},
    # 71. tale: imaginative story vs exciting description of event. Different. SPLIT.
    {"word": "tale", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a written/literary tale, sense 2 is an oral account that may not be true. Different (literary vs oral).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 72. preference: greater interest vs thing liked better. Same. MERGE.
    {"word": "preference", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a liking for one thing over another' — sense 1 is the abstract state, sense 2 is the specific thing.",
     "examples_substitutable_pct": 100,
     "merged_text": "a greater liking for one thing over another, or the thing that is liked better"},
    # 73. exception: person/thing not included in general vs thing not following a rule. Different. SPLIT.
    {"word": "exception", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is exclusion from a statement, sense 2 is a deviation from a rule. Different (general exclusion vs rule violation).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 74. sin: offence against God vs act of breaking religious law. Same. MERGE.
    {"word": "sin", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a violation of religious or moral law' — sense 1 is the specific offence, sense 2 is the abstract concept.",
     "examples_substitutable_pct": 100,
     "merged_text": "an act that breaks a religious or moral law, or the concept of doing so"},
    # 75. flavour: how food tastes vs particular type of taste. Different. SPLIT.
    {"word": "flavour", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is the general taste characteristic, sense 2 is a specific type/variety. Different (quality vs variety).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 76. slam: shut with force vs put/push with force. Different. SPLIT.
    {"word": "slam", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is about closing (door), sense 2 is about placing/throwing (slam phone, brakes). Different actions.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 77. ideal (noun): perfect idea/standard vs perfect person/thing. Same. MERGE.
    {"word": "ideal", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'a perfect example or standard' — sense 1 is abstract (ideals), sense 2 is a concrete person/thing.",
     "examples_substitutable_pct": 95,
     "merged_text": "a perfect idea, standard, or example that is worth trying to achieve"},
    # 78. mail: 3 senses. SPLIT.
    {"word": "mail", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: postal system, letters/packages, email. Different (system, physical, digital).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 79. item: thing on a list vs single object. Different. SPLIT.
    {"word": "item", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is a list entry (agenda item), sense 2 is a generic single object. Different (list vs object).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 80. creative: 2 senses (involving skill/imagination vs having skill). Different. SPLIT.
    {"word": "creative", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is about an activity (creative writing), sense 2 is about a person (creative artist). Different.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 81. scratch: 3 senses. SPLIT.
    {"word": "scratch", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: rub with nails, cut/damage skin, damage surface. Distinct actions.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 82. credit: pay later arrangement vs bank loan. Different. SPLIT.
    {"word": "credit", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a store/shop arrangement (buy on credit), sense 2 is bank lending. Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 83. closure: permanent shutdown vs temporary closing. Different. SPLIT.
    {"word": "closure", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is permanent (factory closure), sense 2 is temporary (road closure). Different (permanent vs temporary).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 84. autonomy: freedom to govern independently vs ability to act independently. Different. SPLIT.
    {"word": "autonomy", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is political/organizational, sense 2 is personal. Different scales.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 85. import (noun): product brought in vs act of bringing in. Different. SPLIT.
    {"word": "import", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is the product itself, sense 2 is the action. Different (thing vs act).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 86. artificial: 3 senses. SPLIT.
    {"word": "artificial", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: not natural (substitute), created by people (barriers), not genuine (emotion). Distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 87. succeed: achieve a goal vs be successful in life. Different. SPLIT.
    {"word": "succeed", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is achieving a specific thing (succeeded in getting a place), sense 2 is general life success. Different (specific vs general).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 88. poisonous: causes death if swallowed vs produces poison. Different. SPLIT.
    {"word": "poisonous", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is direct harm (chemicals), sense 2 is producing poison (snakes). Different mechanisms.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 89. citizen: legal right to country vs person in a place. Different. SPLIT.
    {"word": "citizen", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is legal nationality, sense 2 is residency in a place. Different (legal vs locational).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 90. concede: admit after resisting vs admit losing vs give away. SPLIT.
    {"word": "concede", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: admit truth, admit defeat, give unwillingly. Each distinct.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 91. machinery: machines as group vs parts inside a machine. Different. SPLIT.
    {"word": "machinery", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is machines collectively, sense 2 is the internal workings of a machine. Different (whole vs parts).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 92. patient (noun): person receiving treatment vs doctor-specific person. Different. SPLIT.
    {"word": "patient", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is any person receiving treatment, sense 2 is specifically a doctor/dentist's roster. Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 93. population: all people in an area vs particular group. Different. SPLIT.
    {"word": "population", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is total population of an area, sense 2 is a specific sub-group (adult, urban). Different (whole vs subset).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 94. cooperate: work together to achieve vs be helpful by doing what's asked. Different. SPLIT.
    {"word": "cooperate", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is joint effort toward a goal, sense 2 is complying with a request. Different (collaboration vs compliance).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 95. conscience: 3 senses. SPLIT.
    {"word": "conscience", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: moral sense, guilty feeling, sense of right behavior. Distinct.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 96. alliance: agreement between parties vs the group itself. Different. SPLIT.
    {"word": "alliance", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is the agreement, sense 2 is the resulting group/organization. Different (agreement vs entity).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 97. insert: put into something vs add to writing. Same. MERGE.
    {"word": "insert", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'put something into something else' — sense 1 is physical, sense 2 is textual.",
     "examples_substitutable_pct": 100,
     "merged_text": "to put something into something else, whether a physical object or a piece of writing"},
    # 98. boss: person in charge at work vs person in charge of large organization. Same. MERGE.
    {"word": "boss", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a person in charge of others' — sense 1 is day-to-day supervisor, sense 2 is a senior executive.",
     "examples_substitutable_pct": 100,
     "merged_text": "a person who is in charge of other people at work, whether as a direct supervisor or as the head of a large organization"},
    # 99. broadcaster: person presenting on TV/radio vs company sending programmes. Different. SPLIT.
    {"word": "broadcaster", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is an individual, sense 2 is a company. Different (person vs organization).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 100. representative (adj): typical of group vs containing examples of all types. Different. SPLIT.
    {"word": "representative", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is being typical/characteristic, sense 2 is being inclusive/diverse. Different (typical vs comprehensive).",
     "examples_substitutable_pct": 30, "merged_text": None},
]


def write_verdicts_json(out_path: str) -> None:
    import json
    from pathlib import Path
    out = {
        "note": "γ verdicts from MiniMax-M3 (this session), 2026-06-16. FULL-RUN sub-batch 1 (100 clusters).",
        "verdicts": VERDICTS,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    write_verdicts_json('data/simplify_diff/gamma_full_sub_1_verdicts.json')
    print(f'Wrote {len(VERDICTS)} verdicts to data/simplify_diff/gamma_full_sub_1_verdicts.json')
