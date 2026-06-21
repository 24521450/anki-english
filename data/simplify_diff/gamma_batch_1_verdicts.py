"""γ verdicts for batch 1 (100 clusters).

Reasoned by MiniMax-M3 (this session) 2026-06-16.

Schema per cluster:
{
  "cluster_hash": "...",
  "word": "...",
  "decision": "merge" | "split" | "unsure",
  "confidence": 0.0-1.0,
  "reasoning": "1 sentence",
  "examples_substitutable_pct": 0-100,
  "merged_text": "..." | null
}
"""
VERDICTS = [
    # 1. organized: 3 senses (large groups/arranged well/individual person organized). [0,1] are about systems/events, [2] is personal. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "organized",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 2 (person who is organized) is distinct from senses 0+1 (groups/systems/events that are well-planned).",
        "examples_substitutable_pct": 60, "merged_text": None,
    },
    # 2. recover: get well vs return to normal state. Both = "return to normal after bad state". MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "recover",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses mean 'return to a normal state after something bad' — one is physical (illness), the other is general (economy, emotions).",
        "examples_substitutable_pct": 95,
        "merged_text": "to return to a normal or healthy state after being ill, hurt, or having a difficult experience",
    },
    # 3. supporter: political party vs sports team. Different domains. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "supporter",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is political/ideological support, sense 2 is sports fandom. Distinct domains.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 4. dealer: business selling products vs drug seller. Different (one legal, one not). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "dealer",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is a legitimate businessperson, sense 2 is an illegal drug seller. Different register, different contexts.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 5. red: red color vs red-brown. Both = "red". MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "red",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'having a red color' — sense 1 is the basic red, sense 2 is red-brown (which is still a kind of red). A 'red color' definition covers both.",
        "examples_substitutable_pct": 90,
        "merged_text": "having the color of blood or fire, including red-brown shades",
    },
    # 6. democracy: system vs country. The system defines the country. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "democracy",
        "decision": "merge", "confidence": 0.85,
        "reasoning": "Sense 1 is the political system, sense 2 is a country that uses that system. A 'country with democratic government' definition covers both.",
        "examples_substitutable_pct": 90,
        "merged_text": "a system of government in which people vote to elect their representatives, or a country that has this system",
    },
    # 7. sail (noun): cloth vs trip. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "sail",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is the cloth that catches wind, sense 2 is a boat trip. Different objects.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 8. bottle: container vs amount. Same thing (amount in container). MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "bottle",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Sense 1 is the container, sense 2 is the amount inside. Learners naturally use 'bottle' to mean both ('a bottle of wine' = the container or its contents).",
        "examples_substitutable_pct": 95,
        "merged_text": "a glass or plastic container with a narrow neck used for storing liquids, or the amount of liquid it contains",
    },
    # 9. sell: give for money vs offer for sale. Same action. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "sell",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'exchange something for money' — sense 1 emphasizes the seller giving, sense 2 the offer. Same action, different perspective.",
        "examples_substitutable_pct": 100,
        "merged_text": "to give something to someone in exchange for money, or to offer something for people to buy",
    },
    # 10. encounter: experience difficulty vs meet new. Different (negative vs neutral). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "encounter",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 emphasizes difficulty/problems, sense 2 is neutral meeting (a remarkable woman, a phenomenon). Different valence.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 11. moment: short period vs exact point. Both = "a precise time". MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "moment",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Sense 1 is a very short period, sense 2 is a precise point in time. Both relate to 'a brief or exact instant' — one emphasizes duration, the other pinpoint.",
        "examples_substitutable_pct": 90,
        "merged_text": "a very short period of time, or an exact point in time",
    },
    # 12. horror: unpleasant experience vs nature of something unpleasant. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "horror",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Sense 1 is an unpleasant event, sense 2 is the unpleasant nature of something. Both = 'a terrible, frightening experience or quality'.",
        "examples_substitutable_pct": 95,
        "merged_text": "a very unpleasant or frightening experience, or the very unpleasant nature of something that shocks or frightens you",
    },
    # 13. nest: bird's home vs insects' home. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "nest",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'a place where an animal makes its home and raises its young' — sense 1 is birds, sense 2 is insects/other creatures.",
        "examples_substitutable_pct": 100,
        "merged_text": "a structure or place that an animal makes or chooses for laying its eggs in, sheltering its young, or living in",
    },
    # 14. evacuate: move people from danger vs leave. Same action. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "evacuate",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Sense 1 is moving others from danger, sense 2 is leaving oneself. Both = 'leave a dangerous place' (one transitive, one intransitive).",
        "examples_substitutable_pct": 95,
        "merged_text": "to move people out of a place of danger to a safer place, or to leave a dangerous place",
    },
    # 15. loop: shape vs piece of rope. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "loop",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'a curve or circle shape' — sense 1 is a line/road, sense 2 is a piece of rope. Same geometric concept.",
        "examples_substitutable_pct": 95,
        "merged_text": "a shape like a curve or circle, made by a line, rope, wire, etc. that curves back on itself",
    },
    # 16. sanity: healthy mind vs being sensible. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "sanity",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Sense 1 is mental health, sense 2 is reasonableness. Both relate to 'a sound, rational state of mind'.",
        "examples_substitutable_pct": 90,
        "merged_text": "the state of having a healthy, sound, or sensible mind",
    },
    # 17. identity: who you are vs characteristics. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "identity",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is about identifying a specific person (police discovering identity), sense 2 is about personal/cultural characteristics. Different uses.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 18. location: place/position vs film location. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "location",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is any place/position, sense 2 is specifically a film-shooting site. The film context is too specific to merge.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 19. investment: act of investing vs money invested vs worth buying thing. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "investment",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 2 (worth buying thing) is broader and slightly different — a microwave is a good investment, but you don't 'invest' in a microwave. Different framing.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 20. noisy: making noise vs full of noise. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "noisy",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'full of noise' — sense 1 describes the source (noisy children), sense 2 describes the place (noisy classroom). Same concept.",
        "examples_substitutable_pct": 100,
        "merged_text": "making a lot of noise, or full of noise",
    },
    # 21. rich: person has money vs country has wealth. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "rich",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'having a lot of wealth' — sense 1 is for people, sense 2 is for countries. Same concept at different scales.",
        "examples_substitutable_pct": 95,
        "merged_text": "having a lot of money, property, or wealth",
    },
    # 22. slavery: state of being a slave vs practice of owning slaves. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "slavery",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'the system in which people are forced to work as slaves' — sense 1 emphasizes the individual's state, sense 2 the practice/system.",
        "examples_substitutable_pct": 100,
        "merged_text": "the state or practice of being forced to work as a slave, owned by another person",
    },
    # 23. charge: criminal claim vs accusation. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "charge",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'a formal accusation of wrongdoing' — sense 1 is the police charge, sense 2 is a broader accusation. Same concept.",
        "examples_substitutable_pct": 95,
        "merged_text": "an official or formal claim that someone has done something wrong or committed a crime",
    },
    # 24. ironic: saying opposite vs opposite of expected. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "ironic",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is verbal irony (saying the opposite of what you mean), sense 2 is situational irony (events being the opposite of what was expected). Different phenomena.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 25. memorial: statue/structure vs thing that reminds. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "memorial",
        "decision": "merge", "confidence": 0.85,
        "reasoning": "Both senses are 'something that serves as a reminder of a person or event' — sense 1 is physical (statue), sense 2 is broader (painting, lasting memory).",
        "examples_substitutable_pct": 90,
        "merged_text": "something that is built, made, or kept to remind people of an important person or event",
    },
    # 26. brown: color of earth/coffee vs tanned skin. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "brown",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is the general brown color, sense 2 is specifically about sun-tanned skin. Different focuses, different examples.",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 27. miracle: religious act vs lucky event. Different (supernatural vs lucky). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "miracle",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is a supernatural/religious event (caused by God), sense 2 is a lucky/unexpected event (economic miracle). Different conceptual frames.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 28. ignore: pay no attention to something vs pretend not to see someone. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "ignore",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is about ignoring a thing (advice, sign), sense 2 is about ignoring a person. The 'pretend not to see' nuance is distinct.",
        "examples_substitutable_pct": 60, "merged_text": None,
    },
    # 29. ingrained: long-standing vs under surface. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "ingrained",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'deeply established and difficult to remove' — sense 1 is about long-standing beliefs, sense 2 is about surface-level dirt/habits.",
        "examples_substitutable_pct": 90,
        "merged_text": "deeply established and difficult to change or remove",
    },
    # 30. fragile: 3 senses (easily broken / weak-uncertain / not strong-ill). [0,1] = "easily damaged", [2] = "frail". SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "fragile",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 2 (frail, likely to become ill) is a different context from senses 0+1 (physically or relationally delicate).",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 31. deny: say not true vs refuse to admit. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "deny",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'refuse to admit or accept that something is true' — sense 1 is a specific denial, sense 2 is a broader refusal to admit.",
        "examples_substitutable_pct": 95,
        "merged_text": "to say that something is not true, or to refuse to admit or accept something",
    },
    # 32. arise: happen/start to exist vs happen as a result. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "arise",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is 'occur/start' (an opportunity arose), sense 2 is 'result from' (problems arising from a cause). Different semantic frames.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 33. ideology: economic/political system vs general beliefs. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "ideology",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is specifically the ideology of a system (Marxist, capitalist), sense 2 is a group's general beliefs. Different scope.",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 34. danger: 3 senses (possibility of harm / possibility of bad thing / person-thing causing harm). [0,1] = "risk", [2] = "hazard". SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "danger",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Senses 0+1 are about 'possibility of harm' (risk), sense 2 is about 'a person/thing that causes harm' (hazard). Different uses.",
        "examples_substitutable_pct": 60, "merged_text": None,
    },
    # 35. process: 3 senses (series of actions to achieve / series of natural changes / industrial method). SPLIT — too distinct.
    {
        "cluster_hash": "PLACEHOLDER", "word": "process",
        "decision": "split", "confidence": 0.8,
        "reasoning": "Sense 2 (industrial method) is meaningfully different from senses 0+1 (series of actions).",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 36. exploit: selfish advantage vs unfair labor. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "exploit",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is using a situation/person for selfish advantage (one-off), sense 2 is systemic unfair labor. Different registers.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 37. tin: 3 senses (food can / paint can / cooking pan). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "tin",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 3 (cooking pan) is structurally different from senses 0+1 (cylindrical storage containers).",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 38. storm: bad weather (both senses). MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "storm",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'very bad weather with strong winds and rain' — sense 1 is general, sense 2 is the same phenomenon in a specific form (ice storm).",
        "examples_substitutable_pct": 100,
        "merged_text": "very bad weather with strong winds and rain, and often thunder and lightning",
    },
    # 39. sympathetic: approving/supporting vs easy to like. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "sympathetic",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is showing approval/support, sense 2 is about a character being likable. Different uses.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 40. service: 3 senses (public system / organization / business). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "service",
        "decision": "split", "confidence": 0.8,
        "reasoning": "Three distinct senses: the system (ambulance service), the organization (BBC), and the business type (financial services). Each has different examples.",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 41. subtle: not obvious vs clever/indirect. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "subtle",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 describes the thing itself (subtle colors), sense 2 describes the method (subtle plan). Different uses.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 42. classification: act of classifying vs group/class. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "classification",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is the process of classifying, sense 2 is the resulting category. Different (process vs result).",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 43. prosecutor: public official vs lawyer in court. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "prosecutor",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'a lawyer who leads the case against a defendant in court' — sense 1 is the public/state title, sense 2 is the courtroom lawyer role.",
        "examples_substitutable_pct": 100,
        "merged_text": "a lawyer (especially a public official) who leads the case against a defendant in court",
    },
    # 44. therapy: physical/medical vs mental health talk. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "therapy",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is physical/medical treatment (drug therapy, cancer therapy), sense 2 is talk-based mental health treatment. Very different modalities.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 45. alcohol: drinks vs the liquid. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "alcohol",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'the liquid in beer, wine, etc.' — sense 1 emphasizes the drinks, sense 2 emphasizes the chemical substance. Same thing.",
        "examples_substitutable_pct": 95,
        "merged_text": "drinks such as beer or wine that can make people drunk, or the clear liquid they contain",
    },
    # 46. audience: gathered group vs general watchers. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "audience",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'a group of people who watch, read, or listen to something' — sense 1 is at a specific event, sense 2 is a general demographic.",
        "examples_substitutable_pct": 90,
        "merged_text": "a group of people who watch, read, or listen to the same thing, whether at a specific event or in general",
    },
    # 47. procedure: way of doing vs medical operation. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "procedure",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is any way of doing something (administrative procedure), sense 2 is specifically a medical operation. Different domains.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 48. ban: not allowed vs not allowed to do/go. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "ban",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'officially prohibit' — sense 1 is for things (banned substances), sense 2 is for people (banned from driving). Same official prohibition.",
        "examples_substitutable_pct": 90,
        "merged_text": "to officially prohibit something or order someone not to do something",
    },
    # 49. parking: act vs space. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "parking",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is the act of parking (no parking here), sense 2 is the space (ample parking). Different (action vs place).",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 50. storage: 3 senses (general storage / data storage / paid furniture storage). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "storage",
        "decision": "split", "confidence": 0.8,
        "reasoning": "3 senses — general storage (0), data storage (1), and furniture storage (2) are distinct enough that a learner needs separate cards.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 51. pack: clothes for trip vs put in container. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "pack",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'put things into a container' — sense 1 is specifically for a trip, sense 2 is general (storage, transport, sale).",
        "examples_substitutable_pct": 90,
        "merged_text": "to put things into a bag, box, or other container, especially in preparation for a trip or for storage",
    },
    # 52. afraid: 3 senses (fear / worried about consequences / worried about others). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "afraid",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 0 is fear of physical harm, sense 1 is worry about what might happen, sense 2 is worry about others. Different emotional frames.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 53. requirement: need/want vs must-have. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "requirement",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is something you need or want (desire), sense 2 is something you must have (mandatory). Different (need vs must).",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 54. invasion: 3 senses (military / people arriving / unwelcome act). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "invasion",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Three distinct senses: military, demographic, and privacy/act. Each is clearly different.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 55. stranger: unknown person vs new to a place. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "stranger",
        "decision": "merge", "confidence": 0.85,
        "reasoning": "Both senses are 'a person you don't know or are not familiar with' — sense 1 is general, sense 2 is specifically unfamiliar with a place.",
        "examples_substitutable_pct": 90,
        "merged_text": "a person whom you do not know, or a person who is in an unfamiliar place",
    },
    # 56. disappear: 3 senses (can't see / stop existing / lost). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "disappear",
        "decision": "split", "confidence": 0.8,
        "reasoning": "Three senses: visually disappear (behind a cloud), cease to exist (countryside disappearing), and become lost (pens disappear). Each has different examples.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 57. potent: strong effect vs powerful. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "potent",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'having a strong effect or power' — sense 1 emphasizes body/mind, sense 2 is general (potent force, potent symbol).",
        "examples_substitutable_pct": 95,
        "merged_text": "having a strong effect or power",
    },
    # 58. sheet: 2 senses (flat piece of material vs wide flat area). Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "sheet",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is a piece of material (glass, plywood), sense 2 is a covering area (sheet of ice, water). Different.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 59. fit: right shape/size vs right size to go somewhere. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "fit",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'be the right size/shape' — sense 1 for clothing/object, sense 2 for things fitting into a space. Same concept.",
        "examples_substitutable_pct": 100,
        "merged_text": "to be the right shape or size for someone or something, or to be small enough to go into a particular space",
    },
    # 60. politics: power dynamics vs personal views. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "politics",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is about power dynamics in groups, sense 2 is about a person's political beliefs. Different.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 61. goods: things to sell vs possessions. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "goods",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is commercial (manufactured goods), sense 2 is personal possessions (worldly goods). Different contexts.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 62. neighbourhood: district vs surrounding area. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "neighbourhood",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'a local area' — sense 1 is a defined district with residents, sense 2 is the area near a place. Same concept of 'local area'.",
        "examples_substitutable_pct": 95,
        "merged_text": "a district or area of a town, or the area surrounding a particular place",
    },
    # 63. patrol: act vs group. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "patrol",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is the act of patrolling, sense 2 is a group of people who patrol. Different (action vs entity).",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 64. advise: tell what to do vs give help/info. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "advise",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is giving directives (advise against going), sense 2 is providing expert information (advise on technology). Different.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 65. crystal: small piece of substance vs clear mineral/jewelry. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "crystal",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is a naturally formed piece (ice/salt crystals), sense 2 is a specific mineral used decoratively (quartz, crystal earrings). Different.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 66. sun: star vs light/heat from it. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "sun",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is the star itself, sense 2 is the light/heat it produces. A learner needs both for different usages.",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 67. corridor: building passage vs train passage. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "corridor",
        "decision": "merge", "confidence": 0.85,
        "reasoning": "Both senses are 'a long narrow passage' — sense 1 is in a building, sense 2 is in a train. Same concept.",
        "examples_substitutable_pct": 95,
        "merged_text": "a long narrow passage in a building, train, or other structure, with doors or compartments on the sides",
    },
    # 68. acquisition: 3 senses (act of getting / thing bought / company bought). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "acquisition",
        "decision": "split", "confidence": 0.8,
        "reasoning": "Three senses: act of acquiring (0), a thing acquired (1), and a business acquisition (2). Distinct enough.",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 69. date: arrangement to meet vs romantic meeting. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "date",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'a meeting arranged with someone' — sense 1 is general, sense 2 is romantic. Same core concept.",
        "examples_substitutable_pct": 90,
        "merged_text": "an arrangement to meet someone at a particular time, whether for social, business, or romantic purposes",
    },
    # 70. rebel: 3 senses (vs government / vs party authority / non-conformist). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "rebel",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Three distinct senses: armed rebel, party rebel, and non-conformist. Different contexts.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 71. principal: college head vs school head. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "principal",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'a person in charge of a school' — sense 1 is college, sense 2 is school. Same role.",
        "examples_substitutable_pct": 95,
        "merged_text": "a person who is in charge of a school, college, or other educational institution",
    },
    # 72. deficit: amount over budget vs amount too small. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "deficit",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is when spending exceeds earnings, sense 2 is when something is too small. Different meanings.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 73. output: amount produced vs information from computer. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "output",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is production output (manufacturing), sense 2 is computer data output. Different domains.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 74. half: 2 equal parts vs period of game. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "half",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is a fraction/division, sense 2 is a period of a game. Different uses.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 75. step: action toward goal vs part of process. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "step",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'one of a series of things done as part of a process or to achieve a goal'. Same concept.",
        "examples_substitutable_pct": 100,
        "merged_text": "one of a series of things that you do in order to achieve something, or that form part of a process",
    },
    # 76. capital: wealth/property vs amount invested. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "capital",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'money or wealth used for investment or business' — sense 1 is general capital, sense 2 is a specific amount.",
        "examples_substitutable_pct": 100,
        "merged_text": "wealth or money that is owned by a person or business and can be used to invest or start a business",
    },
    # 77. boat: small water vehicle vs any ship. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "boat",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is specifically small vessels (smaller than a ship), sense 2 is any water vessel including ferries. Different.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 78. designate: name/describe officially vs choose for a job. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "designate",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is about naming/classifying (designated as a National Park), sense 2 is about choosing for a role (designate a successor). Different actions.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 79. support: 3 senses (thing that holds / act of holding / wearable support). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "support",
        "decision": "split", "confidence": 0.8,
        "reasoning": "3 senses: physical object (1), abstract act of holding (2), and medical device (3). Each is distinct enough.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 80. same: not different vs exactly like. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "same",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'identical' — sense 1 is the same particular one, sense 2 is of the same type. Both covered by 'identical'.",
        "examples_substitutable_pct": 95,
        "merged_text": "exactly the one referred to, or exactly like another; not different",
    },
    # 81. attend: be present vs go regularly. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "attend",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is one-time presence (attend a wedding), sense 2 is regular attendance (attend school). Different framings.",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 82. dry: not wet vs little rain. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "dry",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'lacking water or moisture' — sense 1 is a thing being dry, sense 2 is weather with little rain. Same concept.",
        "examples_substitutable_pct": 95,
        "merged_text": "not wet, or having very little rain or moisture",
    },
    # 83. mood: how you feel vs atmosphere. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "mood",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is an individual's feeling, sense 2 is the feeling/atmosphere of a group. Different scopes.",
        "examples_substitutable_pct": 40, "merged_text": None,
    },
    # 84. listener: person who listens vs radio listener. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "listener",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'a person who listens' — sense 1 is general (good listener), sense 2 is a radio/podcast audience. Same person-who-listens concept.",
        "examples_substitutable_pct": 90,
        "merged_text": "a person who listens, especially to a radio programme, podcast, or speaker",
    },
    # 85. ambiguous: multiple meanings vs not clearly defined. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "ambiguous",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'not clear or having multiple possible interpretations' — sense 1 is word/statement, sense 2 is a role/situation. Same concept.",
        "examples_substitutable_pct": 95,
        "merged_text": "able to be understood in more than one way, or not clearly stated or defined",
    },
    # 86. intuitive: 3 senses (using feelings / able to use feelings / easy to use). [0,1] similar, [2] different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "intuitive",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 2 (easy to use, e.g. software) is distinct from senses 0+1 (about using feelings rather than facts).",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 87. secret: known by few vs actions hidden. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "secret",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'kept hidden from others' — sense 1 is for things/info, sense 2 is for actions/behavior. Same hidden concept.",
        "examples_substitutable_pct": 90,
        "merged_text": "known about by only a few people and deliberately kept hidden from others",
    },
    # 88. agency: business providing service vs government department. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "agency",
        "decision": "merge", "confidence": 0.85,
        "reasoning": "Both senses are 'an organization that provides a service' — sense 1 is private/commercial, sense 2 is government.",
        "examples_substitutable_pct": 90,
        "merged_text": "an organization (public or private) that provides a particular service on behalf of others",
    },
    # 89. sanction: order limiting trade vs punishment for disobedience. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "sanction",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is a punitive trade restriction against a country, sense 2 is a coercive measure to enforce behavior. Different mechanisms.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 90. consistent: same behavior/opinions vs same way over time. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "consistent",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'unchanging in pattern or behavior' — sense 1 is over actions, sense 2 is over time. Same constancy concept.",
        "examples_substitutable_pct": 100,
        "merged_text": "always behaving in the same way, or continuing in the same way without changing",
    },
    # 91. transform: change form vs change appearance/character. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "transform",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is literal physical change (light into electricity), sense 2 is broad aesthetic/life change (transform my life). Different magnitudes.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 92. productive: producing goods/crops vs doing a lot. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "productive",
        "decision": "merge", "confidence": 0.85,
        "reasoning": "Both senses are 'producing a lot' — sense 1 emphasizes tangible output (farming, manufacturing), sense 2 emphasizes achievement (productive meeting).",
        "examples_substitutable_pct": 90,
        "merged_text": "producing or achieving a lot, especially in terms of goods, crops, or work done",
    },
    # 93. mix: combine substances vs prepare by combining. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "mix",
        "decision": "split", "confidence": 0.85,
        "reasoning": "Sense 1 is substances combining on their own or being combined (oil and water), sense 2 is the act of preparing a mixture. Different.",
        "examples_substitutable_pct": 50, "merged_text": None,
    },
    # 94. clinic: 4 senses (building for treatment / period of treatment / private hospital / shared doctors' building). SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "clinic",
        "decision": "split", "confidence": 0.85,
        "reasoning": "4 senses, each with distinct context: building, period, private hospital, doctors' building. Conservative: keep separate.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 95. rise: increase in amount/level vs increase in pay. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "rise",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is a general increase (tax rise, price rise), sense 2 is specifically a pay increase. Different.",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
    # 96. shame: make feel ashamed vs make lose honor. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "shame",
        "decision": "merge", "confidence": 0.9,
        "reasoning": "Both senses are 'make someone feel disgraced or dishonored' — sense 1 is personal feeling, sense 2 is loss of honor. Same humiliation.",
        "examples_substitutable_pct": 95,
        "merged_text": "to make someone feel ashamed, or to cause someone to lose honor or respect",
    },
    # 97. detention: state of being kept in prison vs school punishment. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "detention",
        "decision": "split", "confidence": 0.95,
        "reasoning": "Sense 1 is a legal/criminal context (prison, arrest), sense 2 is a school discipline context. Different domains.",
        "examples_substitutable_pct": 20, "merged_text": None,
    },
    # 98. meal: occasion of eating vs food eaten. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "meal",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'food eaten at a sitting' — sense 1 is the occasion, sense 2 is the food itself. Same concept.",
        "examples_substitutable_pct": 95,
        "merged_text": "an occasion when people sit down to eat, or the food that is eaten on such an occasion",
    },
    # 99. endless: very large amount vs continuing long time. Same. MERGE.
    {
        "cluster_hash": "PLACEHOLDER", "word": "endless",
        "decision": "merge", "confidence": 0.95,
        "reasoning": "Both senses are 'seeming to have no end' — sense 1 is in size/amount, sense 2 is in time. Same concept.",
        "examples_substitutable_pct": 100,
        "merged_text": "very large in size or amount, or continuing for a long time, in a way that seems to have no end",
    },
    # 100. child: young human vs son/daughter. Different. SPLIT.
    {
        "cluster_hash": "PLACEHOLDER", "word": "child",
        "decision": "split", "confidence": 0.9,
        "reasoning": "Sense 1 is a young human (not yet adult), sense 2 is a son or daughter of any age. Different (age scope).",
        "examples_substitutable_pct": 30, "merged_text": None,
    },
]


def write_verdicts_json(out_path: str) -> None:
    import json
    from pathlib import Path
    out = {
        "note": "γ verdicts from MiniMax-M3 (this session), 2026-06-16. Batch 1 (100 clusters).",
        "verdicts": VERDICTS,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    write_verdicts_json('data/simplify_diff/gamma_batch_1_verdicts.json')
    print(f'Wrote {len(VERDICTS)} verdicts to data/simplify_diff/gamma_batch_1_verdicts.json')
