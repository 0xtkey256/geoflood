"""
Knowledge-graph step. Primary: Neo4j (Aura or local). Fallback: in-memory mock with identical API.

Why a graph: the interesting question is not "what is under water" but
"what OUTSIDE the water stops working because of what is under water" — a multi-hop query.
"""
from __future__ import annotations

import uuid
from typing import Callable

from . import config
from .seed_data import FACILITIES, RELATIONS

Log = Callable[[str], None]

CASCADE_CYPHER = """
MATCH (f:Facility)-[:POWERED_BY]->(sub:Facility)-[fl:FLOODED_IN]->(s:Scenario {id: $sid})
WHERE NOT (f)-[:FLOODED_IN]->(s)
OPTIONAL MATCH (bk:Facility)-[:BACKUP_OF]->(sub)
WITH f, sub, fl, bk, EXISTS { (bk)-[:FLOODED_IN]->(s) } AS backup_down
RETURN f.id AS id, f.name AS facility, f.type AS type, sub.name AS via,
       fl.depth_m AS via_depth_m,
       CASE WHEN bk IS NULL THEN 'none' WHEN backup_down THEN 'backup also flooded' ELSE bk.name END AS backup
ORDER BY f.type, f.id
"""


class Neo4jGraph:
    provider = "neo4j"

    def __init__(self):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.driver.verify_connectivity()

    def seed(self, log: Log) -> None:
        with self.driver.session() as s:
            s.run("CREATE CONSTRAINT facility_id IF NOT EXISTS FOR (f:Facility) REQUIRE f.id IS UNIQUE")
            s.run("UNWIND $rows AS r MERGE (f:Facility {id: r.id}) "
                  "SET f.name = r.name, f.type = r.type, f.lat = r.lat, f.lon = r.lon", rows=FACILITIES)
            for a, rel, b in RELATIONS:
                s.run(f"MATCH (a:Facility {{id:$a}}), (b:Facility {{id:$b}}) MERGE (a)-[:{rel}]->(b)", a=a, b=b)
            n = s.run("MATCH (f:Facility) RETURN count(f) AS n").single()["n"]
        log(f"seeded graph: {n} facilities, {len(RELATIONS)} relations")

    def facilities(self) -> list[dict]:
        with self.driver.session() as s:
            return [dict(r) for r in s.run("MATCH (f:Facility) RETURN f.id AS id, f.name AS name, "
                                           "f.type AS type, f.lat AS lat, f.lon AS lon ORDER BY f.id")]

    def write_scenario(self, result: dict, log: Log) -> str:
        sid = f"scn-{uuid.uuid4().hex[:8]}"
        flooded = [{"id": f["id"], "depth_m": f["depth_m"]} for f in result["facilities"] if f["flooded"]]
        with self.driver.session() as s:
            s.run("CREATE (s:Scenario {id:$sid, area:$area, water_level_m:$wl, flooded_area_km2:$km2, "
                  "dem_source:$src, created_at: datetime()})",
                  sid=sid, area=result["area_name"], wl=result["water_level_m"],
                  km2=result["flooded_area_km2"], src=result["dem_source"])
            s.run("UNWIND $rows AS r MATCH (f:Facility {id:r.id}), (s:Scenario {id:$sid}) "
                  "MERGE (f)-[fl:FLOODED_IN]->(s) SET fl.depth_m = r.depth_m", rows=flooded, sid=sid)
        log(f"wrote Scenario {sid} with {len(flooded)} FLOODED_IN edges")
        return sid

    def cascade(self, sid: str) -> list[dict]:
        with self.driver.session() as s:
            return [dict(r) for r in s.run(CASCADE_CYPHER, sid=sid)]

    def close(self):
        self.driver.close()


class MockGraph:
    provider = "mock-graph"

    def __init__(self):
        self.fac = {f["id"]: dict(f) for f in FACILITIES}
        self.rels = list(RELATIONS)
        self.scenarios: dict[str, dict] = {}

    def seed(self, log: Log) -> None:
        log(f"MOCK graph: {len(self.fac)} facilities, {len(self.rels)} relations (in-memory)")

    def facilities(self) -> list[dict]:
        return [dict(f) for f in self.fac.values()]

    def write_scenario(self, result: dict, log: Log) -> str:
        sid = f"scn-{uuid.uuid4().hex[:8]}"
        self.scenarios[sid] = {f["id"]: f["depth_m"] for f in result["facilities"] if f["flooded"]}
        log(f"MOCK: scenario {sid} with {len(self.scenarios[sid])} flooded facilities")
        return sid

    def cascade(self, sid: str) -> list[dict]:
        flooded = self.scenarios[sid]
        backups = {b: a for a, rel, b in self.rels if rel == "BACKUP_OF"}  # sub -> backup sub
        out = []
        for a, rel, b in self.rels:
            if rel == "POWERED_BY" and b in flooded and a not in flooded:
                bk = backups.get(b)
                backup = "none" if bk is None else ("backup also flooded" if bk in flooded else self.fac[bk]["name"])
                out.append({"id": a, "facility": self.fac[a]["name"], "type": self.fac[a]["type"],
                            "via": self.fac[b]["name"], "via_depth_m": flooded[b], "backup": backup})
        return sorted(out, key=lambda r: (r["type"], r["id"]))

    def close(self):
        pass


def connect(log: Log):
    if config.USE_NEO4J:
        try:
            g = Neo4jGraph()
            log(f"connected to Neo4j at {config.NEO4J_URI}")
            return g
        except Exception as e:  # noqa: BLE001
            log(f"Neo4j failed ({type(e).__name__}: {e}) -> falling back to in-memory graph")
    return MockGraph()
