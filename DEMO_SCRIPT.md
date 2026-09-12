# 2-minute demo script

**[0:00 – Slide 2, "The problem"]**
"Everyone builds flood maps. But when a flood hits, the facility that hurts most is often the one that is *not* under water. A hospital on high ground still goes dark if its substation sits in the lowlands. That cascade never shows up in raster analysis — you have to walk the relationships. So we built an agent you can just ask."

**[0:20 – switch to the UI, click the first example]**
"One question: *If the lower Arakawa rises three meters, which facilities are affected?*"

**[0:25 – point at the stepper as each stage lights up]**
"First stage: the language model on **Nosana**'s decentralized GPUs writes the GIS script for this question — the generated code is right here."
"Second: we pull the facility nodes from **Neo4j**."
"Third: that LLM-written code runs in a **Daytona** sandbox — it fetches real elevation tiles from the Geospatial Information Authority of Japan, computes the flood mask, renders the map, and the sandbox is destroyed. Arbitrary generated code never touches our machine."
(map appears) "Red markers are facilities under water — about 100 square kilometers at plus three meters."

**[1:05 – the cascade card]**
"Now the part only a graph can answer. We write the scenario back into **Neo4j** and run a two-hop query: facility → powered by → substation → flooded. This shelter is dry — but its substation is under three meters of water, so it loses power. The query even tells us whether the backup substation is flooded too."

**[1:25 – the briefing]**
"Finally, the model on Nosana turns all of it into a briefing an emergency operations center can read as-is."

**[1:35 – Slide 5, "Where we are"]**
"Honest status: Neo4j is live. Daytona sign-up was blocked from this venue by anomaly detection for our whole team — confirmed with support — so today the same script runs through a local fallback; the integration is thirty lines and goes live by pasting a key. Nosana uses the OpenAI-compatible client, endpoint pending."

**[1:50 – close]**
"Three platforms, each doing the one thing the others can't: Daytona runs untrusted code safely, Nosana runs the inference, Neo4j reasons over relationships. Swap in a city's real grid data and this runs in an EOC tomorrow. Thank you."

## Pre-flight
- [ ] `python3 smoke.py` — anything failing → `USE_<X>=0` in `.env`, demo with the mock and say so
- [ ] Run one full query before the demo (warms the Daytona image / snapshot cache)
- [ ] One browser tab, zoom 125 %, stepper readable from the back of the room
- [ ] Say the platform names out loud — judges don't read code
