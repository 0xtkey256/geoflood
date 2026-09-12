# 🛰️ Geo Flood Agent — Daytona × Nosana × Neo4j

**Ask: "If the lower Arakawa rises 3 m, which facilities are affected?"** and the agent will:

1. **Nosana** — an LLM on decentralized GPUs (OpenAI-compatible endpoint) writes the GIS script for the question
2. **Daytona** — a disposable, isolated sandbox executes that LLM-written code: fetches real elevation tiles from GSI (Geospatial Information Authority of Japan), computes a bathtub flood mask, renders a map PNG
3. **Neo4j** — stores the flood scenario as `FLOODED_IN` edges and answers the question raster analysis cannot: **which facilities stay dry but lose power because their substation is under water** (a 2-hop Cypher query)
4. **Nosana** — turns the results into a briefing an emergency operations center can act on

The UI streams every step over SSE and tags each stage with the platform doing the work, showing **LIVE** or **MOCK** honestly.

Built at Daytona HackSprint Tokyo, 12 September 2026, by [Solafune](https://solafune.com).

## Quick start (5 minutes)

```bash
git clone https://github.com/0xtkey256/geoflood.git && cd geoflood
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # paste your keys (see below)
python3 smoke.py                # one hello-world per platform (~60 s)
python3 -m uvicorn app:app --port 8000
open http://localhost:8000
```

### Credentials (`.env`)

| Platform | Variable | Where to get it |
|---|---|---|
| Nosana | `NOSANA_BASE_URL=https://<job-id>.node.k8s.prd.nos.ci/v1` | Deploy a vLLM/Ollama template from the Nosana dashboard, copy the service URL. Leave `NOSANA_MODEL` empty to auto-discover from `/v1/models` |
| Daytona | `DAYTONA_API_KEY` | app.daytona.io → API Keys |
| Neo4j | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | console.neo4j.io → Free instance (credentials are shown once at creation) |

**Any platform without credentials — or that fails at runtime — falls back to a same-interface mock automatically**
(`USE_NOSANA=0` etc. forces it). The UI badge switches to `mock`; the demo never dies.

### Faster Daytona starts (optional, once)

```bash
python -m agent.sandbox               # builds snapshot "geo-agent-py312" with numpy/matplotlib
echo DAYTONA_SNAPSHOT=geo-agent-py312 >> .env
```
Without it, sandboxes are created from a declarative `Image.debian_slim().pip_install()` that Daytona caches after the first build — run `smoke.py` or one full query before demoing.

## Deploy on Vercel

The repo ships `vercel.json` + `api/index.py`. Import the GitHub repo at vercel.com → add the `.env` variables under
*Settings → Environment Variables* → Deploy. Or from the CLI:

```bash
npm i -g vercel && vercel login && vercel --prod
```

Notes: the local-mock sandbox runs inside the Vercel function (numpy/matplotlib are in `requirements.txt`), Daytona/Neo4j/Nosana
are called over the network, and the function timeout is set to 60 s in `vercel.json`.

## Layout

```
app.py                     FastAPI + SSE endpoint
api/index.py               Vercel entry point (re-exports the FastAPI app)
static/index.html          Demo UI: per-platform pipeline stepper, map, facility table, cascade card, code / Cypher / live log
agent/pipeline.py          Orchestration — yields events for the UI
agent/llm.py               Nosana (OpenAI-compatible) → OpenAI → Anthropic → canned script, in that order
agent/sandbox.py           Daytona: create → upload → exec → download → delete. Falls back to a local subprocess
agent/graph.py             Neo4j: seed / write scenario / cascade Cypher. Falls back to an in-memory graph with the same API
agent/seed_data.py         Sample infrastructure graph (substations, hospitals, shelters; POWERED_BY / BACKUP_OF) — fictional
sandbox_lib/geo_helpers.py Runs inside the sandbox: GSI tile fetch, flood mask, facility sampling, map rendering
smoke.py                   60-second connectivity test for all three platforms
DEMO_SCRIPT.md             The 2-minute demo script
```

## The cascade query (why a graph)

```cypher
MATCH (f:Facility)-[:POWERED_BY]->(sub:Facility)-[fl:FLOODED_IN]->(s:Scenario {id: $sid})
WHERE NOT (f)-[:FLOODED_IN]->(s)
OPTIONAL MATCH (bk:Facility)-[:BACKUP_OF]->(sub)
RETURN f.name, sub.name AS via, fl.depth_m, bk.name AS backup
```

A facility that is not under water but stops working is invisible to raster analysis. You only find it by walking relationships.

## Data

- Elevation: GSI elevation tiles (DEM10B, `cyberjapandata.gsi.go.jp/xyz/dem_png`), fetched at run time. If unreachable, a synthetic DEM is used and labelled `SYNTHETIC`.
- Facilities and power feeds: **fictional sample data** (names carry `(sample)`). Replace `seed_data.py` or load real data into Neo4j.
- Flood model: bathtub (elevation ≤ water level). A demo simplification, not a substitute for official hazard maps.
