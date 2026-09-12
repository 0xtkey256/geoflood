"""
60-second smoke test: one hello-world on each sponsor platform. Run BEFORE building anything else.
    python smoke.py
Anything that fails here -> flip its USE_* flag to 0 in .env and demo with the mock.
"""
import sys
import time

from agent import config

ok = True


def step(name):
    print(f"\n=== {name} ===")


# --- Nosana -------------------------------------------------------------
step("Nosana (OpenAI-compatible endpoint)")
if not config.USE_NOSANA:
    print("skipped: NOSANA_BASE_URL not set")
else:
    try:
        from agent import llm
        t = time.time()
        prov, txt = llm.chat([{"role": "user", "content": "Reply with the single word: pong"}], max_tokens=10)
        print(f"{prov}: {txt!r}  ({time.time()-t:.1f}s)  model={config.NOSANA_MODEL or 'auto'}")
        ok &= prov == "nosana"
    except Exception as e:  # noqa: BLE001
        ok = False; print("FAIL:", e)

# --- Daytona ------------------------------------------------------------
step("Daytona (sandbox create + exec + delete)")
if not config.USE_DAYTONA:
    print("skipped: DAYTONA_API_KEY not set")
else:
    try:
        from daytona import Daytona, DaytonaConfig
        t = time.time()
        d = Daytona(DaytonaConfig(api_key=config.DAYTONA_API_KEY))
        sb = d.create(timeout=120)
        r = sb.process.exec("python3 -c 'import platform;print(\"pong from\", platform.python_version())'")
        print(f"sandbox {sb.id}: {r.result.strip()} exit={r.exit_code} ({time.time()-t:.1f}s)")
        sb.delete()
        ok &= r.exit_code == 0
    except Exception as e:  # noqa: BLE001
        ok = False; print("FAIL:", e)

# --- Neo4j --------------------------------------------------------------
step("Neo4j (connect + 1 Cypher)")
if not config.USE_NEO4J:
    print("skipped: NEO4J_URI / NEO4J_PASSWORD not set")
else:
    try:
        from neo4j import GraphDatabase
        t = time.time()
        drv = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        with drv.session() as s:
            print("RETURN 'pong' ->", s.run("RETURN 'pong' AS x").single()["x"], f"({time.time()-t:.1f}s)")
        drv.close()
    except Exception as e:  # noqa: BLE001
        ok = False; print("FAIL:", e)

print("\nRESULT:", "ALL LIVE PLATFORMS OK" if ok else "SOMETHING FAILED -> set USE_<x>=0 for it and use mock")
sys.exit(0 if ok else 1)
