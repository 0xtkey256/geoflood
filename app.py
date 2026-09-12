"""FastAPI server: serves the demo UI and streams pipeline events over SSE.  run: uvicorn app:app --reload"""
import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from agent import config, pipeline

app = FastAPI(title="Geo Flood Agent — Daytona × Nosana × Neo4j")
INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX.read_text(encoding="utf-8")


@app.get("/api/flags")
def flags():
    return {"nosana": config.USE_NOSANA, "daytona": config.USE_DAYTONA, "neo4j": config.USE_NEO4J,
            "nosana_model": config.NOSANA_MODEL, "daytona_snapshot": config.DAYTONA_SNAPSHOT}


@app.get("/api/run")
def run(q: str = Query(..., min_length=2)):
    def gen():
        try:
            for ev in pipeline.run_query(q):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'platform': 'agent', 'status': 'error', 'msg': str(e)})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
