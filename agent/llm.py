"""
LLM step. Primary: Nosana (OpenAI-compatible endpoint on decentralized GPU).
Fallbacks: OpenAI -> Anthropic -> deterministic canned plan (demo never dies).
"""
from __future__ import annotations

import json
import re

from . import config
from .seed_data import AREAS, DEFAULT_AREA

SYSTEM_PROMPT = """You are a GIS coding agent. You write short Python scripts that run inside an isolated sandbox.
A helper module `geo_helpers` is on the path with:
  run_flood(area_name: str, bbox: dict(west,south,east,north), water_level_m: float,
            facilities_path="facilities.json", out_dir="out", zoom=13) -> dict
It fetches real GSI elevation tiles for bbox, computes a bathtub flood mask for water_level_m,
tests every facility in facilities.json, renders out/map.png and writes out/result.json.

Known areas (name -> bbox): %s

Reply with ONLY one fenced python code block that:
1. imports geo_helpers
2. picks the area bbox and water level implied by the user's request (default area "%s", default 3.0 m)
3. calls geo_helpers.run_flood(...) once and prints nothing else.
""" % (json.dumps(AREAS, ensure_ascii=False), DEFAULT_AREA)

SUMMARY_PROMPT = """You are a disaster-response analyst. Given JSON results of a flood scenario over Tokyo
(GSI elevation data, bathtub model) and a knowledge-graph cascade query, write a 3-4 sentence Japanese
briefing for a municipal EOC: inundated area, which facilities are inundated, and which facilities
outside the water lose power via a flooded substation (cascade). Be concrete, cite numbers. No markdown."""


def _extract_params(query: str) -> tuple[str, float]:
    area = DEFAULT_AREA
    for name in AREAS:
        if name in query or name.replace("下流", "") in query:
            area = name
            break
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|ｍ|メートル)", query)
    level = float(m.group(1)) if m else 3.0
    return area, level


def canned_script(query: str) -> str:
    area, level = _extract_params(query)
    bbox = AREAS[area]
    return f'''import geo_helpers
# canned plan (LLM unavailable) — parsed from: {query!r}
bbox = {{"west": {bbox["west"]}, "south": {bbox["south"]}, "east": {bbox["east"]}, "north": {bbox["north"]}}}
geo_helpers.run_flood("{area}", bbox, {level})
'''


def _client_chain():
    """Yield (label, openai_client, model) in priority order."""
    from openai import OpenAI

    if config.USE_NOSANA:
        yield "nosana", OpenAI(base_url=config.NOSANA_BASE_URL, api_key=config.NOSANA_API_KEY,
                               timeout=60), config.NOSANA_MODEL or _discover_model()
    if config.OPENAI_API_KEY:
        yield "openai", OpenAI(api_key=config.OPENAI_API_KEY, timeout=60), config.OPENAI_MODEL
    if config.ANTHROPIC_API_KEY:
        yield "anthropic", OpenAI(base_url="https://api.anthropic.com/v1/",
                                  api_key=config.ANTHROPIC_API_KEY, timeout=60), config.ANTHROPIC_MODEL


def _discover_model() -> str:
    """vLLM/Ollama on Nosana expose /v1/models — pick the first served model."""
    try:
        import httpx
        r = httpx.get(f"{config.NOSANA_BASE_URL}/models", timeout=10,
                      headers={"Authorization": f"Bearer {config.NOSANA_API_KEY}"})
        return r.json()["data"][0]["id"]
    except Exception:  # noqa: BLE001
        return "default"


def chat(messages: list[dict], max_tokens: int = 800) -> tuple[str, str]:
    """Returns (provider_label, text). Raises if every provider fails."""
    last_err = None
    for label, client, model in _client_chain():
        try:
            r = client.chat.completions.create(model=model, messages=messages,
                                               temperature=0.1, max_tokens=max_tokens)
            text = r.choices[0].message.content or ""
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()  # reasoning models
            if text:
                return label, text
        except Exception as e:  # noqa: BLE001
            last_err = f"{label}: {e}"
    raise RuntimeError(last_err or "no LLM provider configured")


def plan_script(query: str) -> tuple[str, str, bool]:
    """Returns (provider, python_script, used_fallback)."""
    try:
        provider, text = chat([{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": query}])
        m = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.S)
        code = (m.group(1) if m else text).strip()
        if "geo_helpers" in code and "run_flood" in code and "import os" not in code \
                and "subprocess" not in code:
            return provider, code + "\n", False
        raise ValueError("LLM output did not use geo_helpers.run_flood")
    except Exception as e:  # noqa: BLE001
        return f"canned ({e})", canned_script(query), True


def summarize(result: dict, cascade: list[dict]) -> tuple[str, str]:
    slim = {k: v for k, v in result.items() if k not in ("facilities", "bbox")}
    slim["flooded_facilities"] = [f"{f['name']}({f['type']}, depth {f['depth_m']}m)"
                                  for f in result["facilities"] if f["flooded"]]
    slim["cascade_power_loss"] = cascade
    try:
        return chat([{"role": "system", "content": SUMMARY_PROMPT},
                     {"role": "user", "content": json.dumps(slim, ensure_ascii=False)}], max_tokens=400)
    except Exception:  # noqa: BLE001
        flooded = ", ".join(slim["flooded_facilities"]) or "なし"
        casc = ", ".join(f"{c['facility']}（{c['via']}経由）" for c in cascade) or "なし"
        return "canned", (f"{result['area_name']}で水位+{result['water_level_m']}mの場合、"
                          f"浸水面積は約{result['flooded_area_km2']}km²。浸水する施設: {flooded}。"
                          f"浸水域外でも変電所経由で停電が波及する施設: {casc}。")
