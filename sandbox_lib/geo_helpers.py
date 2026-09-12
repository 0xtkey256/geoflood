"""
geo_helpers — runs INSIDE the Daytona sandbox.

Fetches real elevation tiles from GSI (国土地理院 標高タイル, open data),
builds a bathtub flood mask for a given water level, samples facility
locations against the mask, and renders a PNG map.

Only needs: numpy, pillow, matplotlib, requests.
Falls back to a synthetic DEM (clearly labelled) if the tiles cannot be fetched.
"""
from __future__ import annotations

import io
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

GSI_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png"  # DEM10B, z<=14
TILE = 256


# ---------------------------------------------------------------- tiles ---
def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lonlat(x: int, y: int, z: int) -> tuple[float, float]:
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def _decode_gsi_png(data: bytes) -> np.ndarray:
    from PIL import Image

    img = np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype(np.int64)
    x = img[..., 0] * 65536 + img[..., 1] * 256 + img[..., 2]
    h = np.where(x < 2 ** 23, x * 0.01, (x - 2 ** 24) * 0.01)
    h = np.where(x == 2 ** 23, np.nan, h)  # (128,0,0) = no data
    return h.astype(np.float32)


def _fetch_tile(z: int, x: int, y: int) -> np.ndarray:
    import requests

    for attempt in range(3):
        try:
            r = requests.get(GSI_URL.format(z=z, x=x, y=y), timeout=10,
                             headers={"User-Agent": "geo-agent-hacksprint/0.1"})
            if r.status_code == 404:  # sea / no tile
                return np.full((TILE, TILE), np.nan, dtype=np.float32)
            r.raise_for_status()
            return _decode_gsi_png(r.content)
        except Exception:  # noqa: BLE001
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"tile fetch failed z{z}/{x}/{y}")


def fetch_dem(bbox: dict, z: int = 13) -> tuple[np.ndarray, dict, str]:
    """bbox = {west, south, east, north}. Returns (dem[m], bounds, source)."""
    x0, y0 = lonlat_to_tile(bbox["west"], bbox["north"], z)
    x1, y1 = lonlat_to_tile(bbox["east"], bbox["south"], z)
    xs, ys = range(x0, x1 + 1), range(y0, y1 + 1)
    coords = [(x, y) for y in ys for x in xs]
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            tiles = list(ex.map(lambda c: _fetch_tile(z, c[0], c[1]), coords))
        source = f"GSI DEM10B tiles z{z} ({len(coords)} tiles)"
    except Exception as e:  # noqa: BLE001
        print(f"[geo_helpers] tile fetch failed ({e}); using synthetic DEM")
        return _synthetic_dem(bbox)
    rows = []
    i = 0
    for _ in ys:
        rows.append(np.hstack(tiles[i:i + len(xs)]))
        i += len(xs)
    dem = np.vstack(rows)
    west, north = tile_to_lonlat(x0, y0, z)
    east, south = tile_to_lonlat(x1 + 1, y1 + 1, z)
    return dem, {"west": west, "south": south, "east": east, "north": north}, source


def _synthetic_dem(bbox: dict, size: int = 512):
    """Plausible lowland/upland terrain so the pipeline still demos offline."""
    lon = np.linspace(bbox["west"], bbox["east"], size)
    lat = np.linspace(bbox["north"], bbox["south"], size)
    LON, LAT = np.meshgrid(lon, lat)
    t = (LON - bbox["west"]) / (bbox["east"] - bbox["west"])
    u = (LAT - bbox["south"]) / (bbox["north"] - bbox["south"])
    dem = 22 * (1 - t) ** 2 + 2.5 * np.sin(6 * t + 2 * u) + 1.5 * u - 1.0
    river = np.exp(-((t - (0.55 + 0.15 * (1 - u))) ** 2) / 0.0015) * 4
    dem = dem - river
    return dem.astype(np.float32), dict(bbox), "SYNTHETIC DEM (offline fallback)"


# ---------------------------------------------------------------- flood ---
def flood_mask(dem: np.ndarray, water_level_m: float) -> np.ndarray:
    valid = ~np.isnan(dem)
    return valid & (dem <= water_level_m)


def pixel_area_km2(bounds: dict, shape: tuple[int, int]) -> float:
    h, w = shape
    mid_lat = math.radians((bounds["north"] + bounds["south"]) / 2)
    dx_km = (bounds["east"] - bounds["west"]) * 111.32 * math.cos(mid_lat) / w
    dy_km = (bounds["north"] - bounds["south"]) * 110.57 / h
    return dx_km * dy_km


def sample_facilities(mask, dem, bounds, water_level_m, facilities):
    h, w = mask.shape
    out = []
    for f in facilities:
        col = int((f["lon"] - bounds["west"]) / (bounds["east"] - bounds["west"]) * w)
        row = int((bounds["north"] - f["lat"]) / (bounds["north"] - bounds["south"]) * h)
        inside = 0 <= row < h and 0 <= col < w
        elev = float(dem[row, col]) if inside and not np.isnan(dem[row, col]) else None
        flooded = bool(inside and mask[row, col])
        depth = round(max(0.0, water_level_m - elev), 2) if (flooded and elev is not None) else 0.0
        out.append({**f, "elevation_m": None if elev is None else round(elev, 2),
                    "flooded": flooded, "depth_m": depth})
    return out


# ---------------------------------------------------------------- render ---
def render_map(dem, mask, bounds, facilities, out_path, title, water_level_m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource

    ext = [bounds["west"], bounds["east"], bounds["south"], bounds["north"]]
    fig, ax = plt.subplots(figsize=(10, 8), dpi=110)
    d = np.nan_to_num(dem, nan=0.0)
    ls = LightSource(azdeg=315, altdeg=45)
    shaded = ls.shade(np.clip(d, -5, 60), cmap=plt.cm.terrain, vert_exag=8,
                      blend_mode="soft", vmin=-5, vmax=60)
    ax.imshow(shaded, extent=ext, aspect="auto")
    overlay = np.zeros((*mask.shape, 4))
    overlay[mask] = [0.05, 0.35, 0.95, 0.55]
    ax.imshow(overlay, extent=ext, aspect="auto")
    for f in facilities:
        c = "#d62728" if f["flooded"] else "#111111"
        m = {"substation": "s", "hospital": "P", "shelter": "^"}.get(f["type"], "o")
        ax.scatter(f["lon"], f["lat"], s=120 if f["flooded"] else 70, c=c, marker=m,
                   edgecolors="white", linewidths=1.2, zorder=5)
        ax.annotate(f["id"], (f["lon"], f["lat"]), xytext=(4, 4), textcoords="offset points",
                    fontsize=7, color=c, zorder=6)
    latin = {"荒川下流": "Lower Arakawa (E. Tokyo lowlands)", "江東・墨田": "Koto / Sumida",
             "多摩川下流": "Lower Tamagawa"}.get(title, title.encode("ascii", "ignore").decode() or "AOI")
    ax.set_title(f"{latin}\nbathtub flood @ +{water_level_m:.1f} m  |  red = inundated facility",
                 fontsize=11)
    ax.set_xlim(bounds["west"], bounds["east"]); ax.set_ylim(bounds["south"], bounds["north"])
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


# ---------------------------------------------------------------- driver ---
def run_flood(area_name: str, bbox: dict, water_level_m: float,
              facilities_path: str = "facilities.json", out_dir: str = "out", zoom: int = 13) -> dict:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    with open(facilities_path, encoding="utf-8") as fh:
        facilities = json.load(fh)
    dem, bounds, source = fetch_dem(bbox, z=zoom)
    mask = flood_mask(dem, water_level_m)
    fac = sample_facilities(mask, dem, bounds, water_level_m, facilities)
    area = float(mask.sum() * pixel_area_km2(bounds, mask.shape))
    map_path = os.path.join(out_dir, "map.png")
    render_map(dem, mask, bounds, fac, map_path, area_name, water_level_m)
    result = {
        "area_name": area_name, "water_level_m": water_level_m, "bbox": bounds,
        "dem_source": source, "dem_shape": list(mask.shape),
        "flooded_area_km2": round(area, 2),
        "flooded_fraction": round(float(mask.mean()), 4),
        "min_elev_m": None if np.isnan(dem).all() else round(float(np.nanmin(dem)), 2),
        "facilities": fac,
        "flooded_facility_ids": [f["id"] for f in fac if f["flooded"]],
        "elapsed_s": round(time.time() - t0, 2),
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "facilities"}, ensure_ascii=False))
    return result
