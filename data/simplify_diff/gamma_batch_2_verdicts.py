"""γ verdicts for batch 2 (100 clusters).

Reasoned by MiniMax-M3 (this session) 2026-06-16.
"""
VERDICTS = [
    # 1. crisis: time of danger/difficulty vs time at worst point. Same. MERGE.
    {"word": "crisis", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'a time of great difficulty when problems must be solved' — sense 1 is general, sense 2 emphasizes the worst point. Same concept.",
     "examples_substitutable_pct": 90,
     "merged_text": "a time of great danger, difficulty, or doubt, especially when a problem or illness is at its worst point"},
    # 2. belief: 3 senses (strong feeling of truth / opinion / religious belief). [0,1] similar, [2] religion. SPLIT.
    {"word": "belief", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 2 (religious belief) is a distinct context from senses 0+1 (general feeling/opinion). 3 senses, conservative split.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 3. depressed: very sad vs clinically depressed. Same. MERGE.
    {"word": "depressed", "decision": "merge", "confidence": 0.95,
     "reasoning": "Sense 1 is the everyday feeling, sense 2 is the medical condition. Both = 'in a state of depression'.",
     "examples_substitutable_pct": 95,
     "merged_text": "very sad and without hope, whether as a passing feeling or as a medical condition"},
    # 4. guess: 3 senses (try to answer / find the right answer / 'guess what'). [0,1] same, [2] exclamation. SPLIT.
    {"word": "guess", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 2 is an exclamation usage ('Guess what!') which is distinct from the verb senses 0+1 (estimating or finding).",
     "examples_substitutable_pct": 60, "merged_text": None},
    # 5. radio: 4 senses (broadcasting / equipment / process / equipment on ships). SPLIT.
    {"word": "radio", "decision": "split", "confidence": 0.85,
     "reasoning": "Four senses — broadcasting activity, receiver device, transmission process, ship/plane radio. Each is a distinct facet.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 6. tread: 3 senses (put foot down / move with feet / walk). [0,1] close, [2] walk distinct. SPLIT.
    {"word": "tread", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 2 (walk somewhere) is broader/different from senses 0+1 which are about foot pressure/pressing.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 7. rescue: act of saving vs occasion. Same. MERGE.
    {"word": "rescue", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'the saving of someone from a dangerous situation' — sense 1 is the abstract act/fact, sense 2 is a specific instance.",
     "examples_substitutable_pct": 95,
     "merged_text": "the act or occasion of saving someone from a dangerous or difficult situation"},
    # 8. linger: continue to exist vs stay somewhere longer. Different. SPLIT.
    {"word": "linger", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is about a thing (smell, war) persisting. Sense 2 is about a person staying somewhere (lingering over breakfast). Different subjects.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 9. action: process of doing vs thing done. Different. SPLIT.
    {"word": "action", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is the process/act of doing, sense 2 is a specific thing that is done. Process vs result.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 10. shadow: shape from blocking light vs darkness. Different. SPLIT.
    {"word": "shadow", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is the silhouette of an object blocking light, sense 2 is darkness in a place. Different (object vs condition).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 11. loyalty: quality of being constant vs feeling of support. Same. MERGE.
    {"word": "loyalty", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'the quality of being loyal/supportive' — sense 1 is the abstract quality, sense 2 is the specific feeling.",
     "examples_substitutable_pct": 95,
     "merged_text": "the quality or feeling of being constant and supportive in your allegiance to someone or something"},
    # 12. presence: fact of being in a place (both senses). MERGE.
    {"word": "presence", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'the fact of being present in a place' — sense 1 is human, sense 2 is in something (a substance, a market). Same concept.",
     "examples_substitutable_pct": 100,
     "merged_text": "the fact of being present in a particular place or thing"},
    # 13. operational: connected with workings vs ready to use. Different. SPLIT.
    {"word": "operational", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is descriptive (operational costs, activities), sense 2 is a state of readiness (fully operational). Different uses.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 14. coffee: 3 senses (beans/powder / drink / cup of drink). SPLIT.
    {"word": "coffee", "decision": "split", "confidence": 0.85,
     "reasoning": "3 senses: raw form, prepared drink, individual cup. Each has different contexts.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 15. professional: doing as paid job vs done as paid job. Same. MERGE.
    {"word": "professional", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'relating to a paid occupation' — sense 1 is the person, sense 2 is the activity. Same adjective.",
     "examples_substitutable_pct": 100,
     "merged_text": "doing something as a paid job rather than as a hobby, or relating to such work"},
    # 16. costume: traditional/historical clothes vs actor's clothes. Different. SPLIT.
    {"word": "costume", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is for cultural/historical clothing, sense 2 is for theatrical/disguise clothing. Different uses.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 17. region: area without limits vs administrative division. Different. SPLIT.
    {"word": "region", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is informal (mountainous regions), sense 2 is formal/administrative (autonomous regions). Different precision.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 18. duty: work that is your job vs tasks of your job. Same. MERGE.
    {"word": "duty", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'tasks or work that are part of your job' — sense 1 emphasizes the job itself, sense 2 emphasizes the tasks.",
     "examples_substitutable_pct": 100,
     "merged_text": "the work or tasks that are part of your job"},
    # 19. nod: 3 senses (agreement / greeting / pointing direction). SPLIT.
    {"word": "nod", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: agreement (head nod), greeting (nod to crowd), and pointing direction (nod towards kitchen). Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 20. rate: speed of happening vs frequency per period. Different. SPLIT.
    {"word": "rate", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is speed (rate of inflation), sense 2 is frequency over time (crime rate). Different (rate per unit vs events per period).",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 21. lend: give something to return vs give money to return with interest. Same. MERGE.
    {"word": "lend", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'give something temporarily with the expectation of return' — sense 1 is anything, sense 2 is money with interest.",
     "examples_substitutable_pct": 95,
     "merged_text": "to give something to someone who must return it later, including money that must be repaid with interest"},
    # 22. relationship: way people behave towards each other vs romantic friendship. Different. SPLIT.
    {"word": "relationship", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is general (working, customer), sense 2 is specifically romantic/sexual. Distinct.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 23. right: correct for situation vs in good condition. Different. SPLIT.
    {"word": "right", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is 'correct', sense 2 is 'in normal/good condition'. Different semantics.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 24. invitation: act of inviting vs paper card. Same. MERGE.
    {"word": "invitation", "decision": "merge", "confidence": 0.9,
     "reasoning": "Sense 1 is the act of inviting, sense 2 is the physical card. Both = 'a request to come to something'.",
     "examples_substitutable_pct": 90,
     "merged_text": "the act of inviting someone, or a card that asks someone to come to an event"},
    # 25. climate: regular pattern of weather vs area with particular weather. Different. SPLIT.
    {"word": "climate", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is the abstract weather pattern, sense 2 is a specific area/region. Different (pattern vs place).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 26. powerful: 3 senses (great power / strong effect on body / physically strong). SPLIT.
    {"word": "powerful", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: mechanical/force, mental/physical effect, and physical strength. Each is distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 27. interview: 3 senses (job interview / journalist interview / private meeting). SPLIT.
    {"word": "interview", "decision": "split", "confidence": 0.8,
     "reasoning": "Three distinct uses: job application, journalistic questioning, and private Q&A meeting.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 28. emotional: 3 senses (connected with feelings / causing feelings / showing strong feelings). SPLIT.
    {"word": "emotional", "decision": "split", "confidence": 0.85,
     "reasoning": "Three distinct senses: relating to feelings, evoking feelings, and expressing feelings strongly.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 29. analogy: comparison of features vs process of comparing. Different. SPLIT.
    {"word": "analogy", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is the result (a similar feature), sense 2 is the process (the act of comparing).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 30. best: 3 senses (most excellent / happiest / most suitable). SPLIT.
    {"word": "best", "decision": "split", "confidence": 0.8,
     "reasoning": "Three distinct senses: highest quality, happiest moment, most suitable. Different evaluation criteria.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 31. shower: equipment for washing vs act of washing. Different. SPLIT.
    {"word": "shower", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is the physical equipment/room, sense 2 is the activity. Different (thing vs action).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 32. competitive: situation of competing vs person who tries hard. Different. SPLIT.
    {"word": "competitive", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is about a situation/environment, sense 2 is about a person's character. Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 33. soft: less hard vs smooth to touch. Different. SPLIT.
    {"word": "soft", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is hardness/softness (soft cheese), sense 2 is texture/touch (soft skin). Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 34. moon: astronomical object vs appearance in sky. Same. MERGE.
    {"word": "moon", "decision": "merge", "confidence": 0.9,
     "reasoning": "Sense 1 is the actual moon, sense 2 is how it appears. Same celestial object.",
     "examples_substitutable_pct": 90,
     "merged_text": "the round object that orbits the earth, or its appearance in the sky at a particular time"},
    # 35. political: connected with state vs connected with parties. Different. SPLIT.
    {"word": "political", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is broader (state, government), sense 2 is specifically about political parties/competition. Different focus.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 36. quantity: amount/number vs measurement by amount. Same. MERGE.
    {"word": "quantity", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are about 'how much of something there is' — sense 1 is the amount, sense 2 is the measurement.",
     "examples_substitutable_pct": 100,
     "merged_text": "an amount or number of something, or the measurement of how much of it there is"},
    # 37. forget: unable to remember vs deliberately stop thinking. Different. SPLIT.
    {"word": "forget", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is involuntary (can't remember), sense 2 is deliberate (choose to stop thinking). Very different psychological processes.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 38. stock: goods for sale vs supply available. Same. MERGE.
    {"word": "stock", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a supply of something available' — sense 1 is commercial (goods in a shop), sense 2 is general (food stocks).",
     "examples_substitutable_pct": 100,
     "merged_text": "a supply of something that is available for use or sale"},
    # 39. investigation: official criminal vs scientific. Different. SPLIT.
    {"word": "investigation", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is criminal/legal (police investigation), sense 2 is scientific/academic. Different domains.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 40. instrument: tool for task vs device for measuring in vehicle. Different. SPLIT.
    {"word": "instrument", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is general (surgical, scientific tool), sense 2 is specifically a vehicle/machine measuring device.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 41. guideline: rules/instructions vs help for decision. Same. MERGE.
    {"word": "guideline", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'something that guides a decision or action' — sense 1 is official rules, sense 2 is a general reference.",
     "examples_substitutable_pct": 90,
     "merged_text": "a rule, instruction, or reference that helps you make a decision or do something"},
    # 42. racism: unfair treatment vs belief in race superiority. Different. SPLIT.
    {"word": "racism", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is the action (discrimination), sense 2 is the belief system. Different (behavior vs ideology).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 43. interactive: 2-way computer communication vs people working together. Different. SPLIT.
    {"word": "interactive", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is technical (computer), sense 2 is social (people). Different domains.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 44. cynical: believe selfish motives vs no hope for good. Same. MERGE.
    {"word": "cynical", "decision": "merge", "confidence": 0.85,
     "reasoning": "Both senses are 'distrustful of others' — sense 1 is about human motives, sense 2 is about outcomes/hope.",
     "examples_substitutable_pct": 85,
     "merged_text": "believing that people act mainly in self-interest, or that something is unlikely to succeed or be valuable"},
    # 45. prison: building vs system. Different. SPLIT.
    {"word": "prison", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is the physical building, sense 2 is the prison system. Different (place vs institution).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 46. paint: cover with paint vs make picture with paint. Different. SPLIT.
    {"word": "paint", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is about applying paint to a surface, sense 2 is about creating art. Different activities.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 47. meditation: focusing mind in silence vs serious thoughts. Different. SPLIT.
    {"word": "meditation", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is a practice/activity, sense 2 is a written/spoken reflection. Different forms.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 48. survive: continue to live vs continue despite danger. Same. MERGE.
    {"word": "survive", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'continue to live or exist' — sense 1 is general, sense 2 emphasizes surviving a dangerous event.",
     "examples_substitutable_pct": 95,
     "merged_text": "to continue to live or exist, especially after a dangerous event or time"},
    # 49. pollution: process/state vs substances. Different. SPLIT.
    {"word": "pollution", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is the process/condition, sense 2 is the actual pollutants. Different (action vs substance).",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 50. consent: permission vs agreement. Different. SPLIT.
    {"word": "consent", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is permission from authority, sense 2 is general agreement. Different (hierarchical vs mutual).",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 51. informal: 3 senses (relaxed / for conversation / for casual wear). SPLIT.
    {"word": "informal", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: relaxed atmosphere, casual speech, casual clothing. Each distinct context.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 52. precedent: official action for future vs similar past event. Different. SPLIT.
    {"word": "precedent", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a binding example (legal precedent), sense 2 is any past event (no precedent for this disaster).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 53. apartment: rooms for living vs rooms for holiday. Different. SPLIT.
    {"word": "apartment", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is a regular dwelling, sense 2 is specifically holiday accommodation. Different contexts.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 54. occurrence: something that happens vs the fact of happening. Same. MERGE.
    {"word": "occurrence", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'something that happens' — sense 1 is the event itself, sense 2 is the fact of it happening.",
     "examples_substitutable_pct": 100,
     "merged_text": "something that happens or exists, or the fact of something happening"},
    # 55. aggressive: angry/threatening vs determined/forceful. Different. SPLIT.
    {"word": "aggressive", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is hostile/threatening, sense 2 is determined/forceful (aggressive marketing). Very different connotations.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 56. personal: your own vs between people who know each other. Different. SPLIT.
    {"word": "personal", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is individual/private (personal effects), sense 2 is interpersonal (personal relationships). Different.",
     "examples_substitutable_pct": 40, "merged_text": None},
    # 57. lonely: 3 senses (no friends / sad alone / deserted place). SPLIT.
    {"word": "lonely", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: lacking friends, emotional solitude, and physically isolated (lonely beach). Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 58. charity: organization for helping vs the group/concept. Same. MERGE.
    {"word": "charity", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are about charitable organizations — sense 1 is a specific org, sense 2 is the collective concept.",
     "examples_substitutable_pct": 95,
     "merged_text": "an organization for helping people in need, or such organizations considered as a group"},
    # 59. implicate: show involvement of person vs cause of something bad. Different. SPLIT.
    {"word": "implicate", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is about people (implicated in crime), sense 2 is about things (hygiene implicated in outbreak).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 60. rebuild: build again vs make strong again. Same. MERGE.
    {"word": "rebuild", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'build or make complete again' — sense 1 is physical, sense 2 is emotional/abstract.",
     "examples_substitutable_pct": 100,
     "merged_text": "to build or make something complete and strong again, whether physically or figuratively"},
    # 61. question: sentence asking info vs task to test knowledge. Different. SPLIT.
    {"word": "question", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is any sentence asking info, sense 2 is specifically a test/exam question. Different uses.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 62. recruit: person joining military/police vs joining any organization. Same. MERGE.
    {"word": "recruit", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'a new member of an organization' — sense 1 is military/police, sense 2 is general.",
     "examples_substitutable_pct": 95,
     "merged_text": "a person who has recently joined an organization, especially the armed forces, police, or a profession"},
    # 63. mobilize: 3 senses (organize for aim / find resources / army ready for war). SPLIT.
    {"word": "mobilize", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: organize for political/social action, gather resources, prepare military. Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 64. conservative: opposed to change vs Conservative Party. Different. SPLIT.
    {"word": "conservative", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is general (traditional views), sense 2 is specifically the British Conservative Party. Different.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 65. regret: feel sorry about what done vs polite expression of sorrow. Same. MERGE.
    {"word": "regret", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'feel sorry about something' — sense 1 is personal, sense 2 is formal/polite expression.",
     "examples_substitutable_pct": 90,
     "merged_text": "to feel sorry about something you have done, or to express sorrow formally about a situation"},
    # 66. centre: middle of something vs main part of town. Different. SPLIT.
    {"word": "centre", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is the middle of any shape/space, sense 2 is specifically a town center. Different.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 67. monster: very large/ugly thing vs cruel person. Different. SPLIT.
    {"word": "monster", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is physical (size/ugliness), sense 2 is moral (cruelty). Different (appearance vs character).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 68. bubble: air in liquid vs soap bubble. Different. SPLIT.
    {"word": "bubble", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is any gas ball in liquid/solid, sense 2 is specifically soap bubbles. Different (gas pocket vs soap film).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 69. suspicion: 3 senses (feeling of wrongdoing / feeling of truth / distrust). SPLIT.
    {"word": "suspicion", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: of wrongdoing, of truth, and general distrust. Each has different objects.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 70. liberty: freedom to live as you choose vs not being prisoner. Same. MERGE.
    {"word": "liberty", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'freedom' — sense 1 is general civil liberty, sense 2 is freedom from imprisonment.",
     "examples_substitutable_pct": 95,
     "merged_text": "the freedom to live as you choose without excessive limits from authority, or the state of not being imprisoned"},
    # 71. glance: look quickly at vs read quickly. Same. MERGE.
    {"word": "glance", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'look at something quickly' — sense 1 is at a thing/person, sense 2 is at text.",
     "examples_substitutable_pct": 100,
     "merged_text": "to look at something quickly, whether a person, place, or written material"},
    # 72. bar: place to buy drinks vs place specializing in food/drink. Same. MERGE.
    {"word": "bar", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a place that serves drinks/food' — sense 1 is general, sense 2 is specialized (sushi bar).",
     "examples_substitutable_pct": 100,
     "merged_text": "a place that serves alcoholic drinks or specializes in a particular type of food or drink"},
    # 73. silence: lack of noise vs no one speaking. Different. SPLIT.
    {"word": "silence", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is absence of noise, sense 2 is absence of speech. Different (sound vs speech).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 74. shine: produce/reflect light vs aim light. Different. SPLIT.
    {"word": "shine", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is light being produced/reflected (sun shines), sense 2 is actively aiming a light (shine a flashlight).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 75. handle: door/window handle vs object handle. Same. MERGE.
    {"word": "handle", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a part of an object that you hold or use to operate it' — sense 1 is door/window, sense 2 is tool/cup.",
     "examples_substitutable_pct": 100,
     "merged_text": "the part of an object that you use to hold, carry, or open it"},
    # 76. imagination: 3 senses (creating mental pictures / imagined thing / new ideas). SPLIT.
    {"word": "imagination", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: mental ability to picture things, an imagined thing, and creative new ideas. Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 77. reader: person who reads vs reader of publication. Same. MERGE.
    {"word": "reader", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a person who reads' — sense 1 is general (with manner like fast/slow), sense 2 is a specific publication's reader.",
     "examples_substitutable_pct": 95,
     "merged_text": "a person who reads, especially a regular reader of a particular publication"},
    # 78. competent: enough skill vs good but not great. Different. SPLIT.
    {"word": "competent", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is 'having enough skill', sense 2 is 'good but not excellent'. Different levels of proficiency.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 79. candidate: person applying for job/election vs person taking exam. Different. SPLIT.
    {"word": "candidate", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is for jobs/elections, sense 2 is for exams. Different contexts.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 80. dissolve: solid mix with liquid vs make solid mix. Different. SPLIT.
    {"word": "dissolve", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is intransitive (substance dissolves), sense 2 is transitive (you dissolve it). Different grammatical uses, but learners may need both.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 81. translate: express in different language vs be changed to another language. Same. MERGE.
    {"word": "translate", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'change from one language to another' — sense 1 is active (you translate), sense 2 is passive (it translates).",
     "examples_substitutable_pct": 100,
     "merged_text": "to express the meaning of speech or writing in a different language, or to be changed from one language to another"},
    # 82. float: move on water/air vs stay on surface. Different. SPLIT.
    {"word": "float", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is moving (floating by), sense 2 is staying (wood floats). Different (motion vs buoyancy).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 83. religious: connected with religion vs believing in religion. Different. SPLIT.
    {"word": "religious", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is descriptive (religious beliefs), sense 2 is personal (a religious person). Different (adjective of thing vs adjective of person).",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 84. domain: area of knowledge vs internet domain. Different. SPLIT.
    {"word": "domain", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is a field of knowledge/responsibility, sense 2 is a website group (.com, .org). Completely different.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 85. exclude: 3 senses (not include / prevent from / rule out possibility). SPLIT.
    {"word": "exclude", "decision": "split", "confidence": 0.85,
     "reasoning": "Three senses: deliberate omission, physical prevention, and ruling out possibility. Each distinct.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 86. corrupt: willing to use power dishonestly vs not honest/moral. Same. MERGE.
    {"word": "corrupt", "decision": "merge", "confidence": 0.9,
     "reasoning": "Both senses are 'dishonest' — sense 1 emphasizes using power for money, sense 2 is general dishonesty.",
     "examples_substitutable_pct": 90,
     "merged_text": "dishonest or immoral, especially in the use of power or position for personal gain"},
    # 87. manipulate: control dishonestly vs control with skill. Different. SPLIT.
    {"word": "manipulate", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 has a negative connotation (manipulate people), sense 2 is neutral/skillful (manipulate gears). Different valences.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 88. dispute: question truth/legality vs argue strongly. Same. MERGE.
    {"word": "dispute", "decision": "merge", "confidence": 0.85,
     "reasoning": "Both senses are 'argue or question' — sense 1 is about facts/legality, sense 2 is interpersonal disagreement.",
     "examples_substitutable_pct": 90,
     "merged_text": "to argue or disagree with someone about something, or to question whether something is true or valid"},
    # 89. girl: female child vs daughter vs young woman. SPLIT.
    {"word": "girl", "decision": "split", "confidence": 0.8,
     "reasoning": "Three senses: female child, daughter (any age), and young woman. Different.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 90. apparatus: tools for activity vs structure of system. Different. SPLIT.
    {"word": "apparatus", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is physical equipment, sense 2 is a system/organization. Different (things vs structure).",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 91. conference: large official meeting vs formal discussion meeting. Same. MERGE.
    {"word": "conference", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'a meeting for discussion' — sense 1 is a large official one, sense 2 is any formal meeting.",
     "examples_substitutable_pct": 100,
     "merged_text": "a meeting, often formal or official, at which people discuss topics of common interest"},
    # 92. explicit: clear and easy to understand vs said openly. Same. MERGE.
    {"word": "explicit", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'clear and openly stated' — sense 1 is generally clear, sense 2 emphasizes saying it openly.",
     "examples_substitutable_pct": 100,
     "merged_text": "said or stated clearly, openly, and in detail, leaving no doubt about the meaning"},
    # 93. insist: demand something happen vs state something true. Different. SPLIT.
    {"word": "insist", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is demanding action (insist on going), sense 2 is asserting truth (insist on innocence). Different.",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 94. indicate: show something is true vs be a sign of something. Same. MERGE.
    {"word": "indicate", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'show or suggest something' — sense 1 is direct evidence, sense 2 is a sign/indicator.",
     "examples_substitutable_pct": 100,
     "merged_text": "to show that something is true, exists, or is likely; to be a sign of something"},
    # 95. friendship: relationship between friends vs feeling of being friends. Same. MERGE.
    {"word": "friendship", "decision": "merge", "confidence": 0.95,
     "reasoning": "Both senses are 'the state or relationship of being friends' — sense 1 is the relationship, sense 2 is the feeling.",
     "examples_substitutable_pct": 100,
     "merged_text": "the relationship, feeling, or state of being friends with someone"},
    # 96. impose: introduce law/rule vs force burden. Different. SPLIT.
    {"word": "impose", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is introducing authority (impose a tax), sense 2 is forcing a burden (impose restrictions). Different (action vs consequence).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 97. hunger: state of not having food vs feeling of needing to eat. Different. SPLIT.
    {"word": "hunger", "decision": "split", "confidence": 0.95,
     "reasoning": "Sense 1 is a serious state (starvation), sense 2 is the everyday feeling of needing food. Different.",
     "examples_substitutable_pct": 20, "merged_text": None},
    # 98. authority: power to give orders vs power/right to do something. Different. SPLIT.
    {"word": "authority", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is about commanding people (position of authority), sense 2 is about having the right/power to act.",
     "examples_substitutable_pct": 50, "merged_text": None},
    # 99. lock: device for door vs device for vehicle/machine. Different. SPLIT.
    {"word": "lock", "decision": "split", "confidence": 0.9,
     "reasoning": "Sense 1 is for door/window/box, sense 2 is for vehicle/machine safety. Different (building vs machine).",
     "examples_substitutable_pct": 30, "merged_text": None},
    # 100. analysis: detailed study vs chemical examination. Different. SPLIT.
    {"word": "analysis", "decision": "split", "confidence": 0.85,
     "reasoning": "Sense 1 is a general study (statistical, data), sense 2 is specifically a chemical/laboratory examination. Different.",
     "examples_substitutable_pct": 40, "merged_text": None},
]


def write_verdicts_json(out_path: str) -> None:
    import json
    from pathlib import Path
    out = {
        "note": "γ verdicts from MiniMax-M3 (this session), 2026-06-16. Batch 2 (100 clusters).",
        "verdicts": VERDICTS,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    write_verdicts_json('data/simplify_diff/gamma_batch_2_verdicts.json')
    print(f'Wrote {len(VERDICTS)} verdicts to data/simplify_diff/gamma_batch_2_verdicts.json')
