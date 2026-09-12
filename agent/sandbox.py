"""
Code execution step. Primary: Daytona sandbox (isolated, disposable, pip-able).
Fallback: local subprocess (mock) so the demo still renders offline.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from . import config

HELPERS_PATH = Path(__file__).resolve().parent.parent / "sandbox_lib" / "geo_helpers.py"
Log = Callable[[str], None]


class SandboxResult(dict):
    """keys: provider, stdout, exit_code, result (dict), map_png (bytes|None), sandbox_id"""


# ------------------------------------------------------------------ Daytona ---
def run_in_daytona(script: str, facilities: list[dict], log: Log) -> SandboxResult:
    from daytona import (CreateSandboxFromImageParams, CreateSandboxFromSnapshotParams,
                         Daytona, DaytonaConfig, FileUpload, Image)

    daytona = Daytona(DaytonaConfig(api_key=config.DAYTONA_API_KEY))
    if config.DAYTONA_SNAPSHOT:
        params = CreateSandboxFromSnapshotParams(snapshot=config.DAYTONA_SNAPSHOT, ephemeral=True)
        log(f"creating sandbox from snapshot '{config.DAYTONA_SNAPSHOT}'")
    else:
        image = Image.debian_slim("3.12").pip_install(config.SANDBOX_PIP)
        params = CreateSandboxFromImageParams(image=image, ephemeral=True)
        log("creating sandbox from declarative image (debian_slim + numpy/matplotlib) — first build is cached")

    sandbox = daytona.create(params, timeout=300,
                             on_snapshot_create_logs=lambda l: log(f"[image build] {l.strip()}"))
    log(f"sandbox {sandbox.id} is running")
    try:
        sandbox.fs.upload_files([
            FileUpload(HELPERS_PATH.read_bytes(), "geo_helpers.py"),
            FileUpload(script.encode(), "run.py"),
            FileUpload(json.dumps(facilities, ensure_ascii=False).encode(), "facilities.json"),
        ])
        log("uploaded geo_helpers.py, run.py, facilities.json")
        resp = sandbox.process.exec("python3 run.py", timeout=240)
        stdout = resp.result or ""
        log(f"exec finished exit={resp.exit_code}")
        if resp.exit_code != 0:
            raise RuntimeError(f"sandbox script failed: {stdout[-800:]}")
        result = json.loads(sandbox.fs.download_file("out/result.json"))
        map_png = sandbox.fs.download_file("out/map.png")
        return SandboxResult(provider="daytona", stdout=stdout, exit_code=resp.exit_code,
                             result=result, map_png=map_png, sandbox_id=sandbox.id)
    finally:
        try:
            sandbox.delete()
            log(f"sandbox {sandbox.id} deleted (ephemeral)")
        except Exception as e:  # noqa: BLE001
            log(f"sandbox delete skipped: {e}")


# --------------------------------------------------------------- local mock ---
def run_locally(script: str, facilities: list[dict], log: Log) -> SandboxResult:
    with tempfile.TemporaryDirectory(prefix="geo-agent-") as d:
        d = Path(d)
        (d / "geo_helpers.py").write_bytes(HELPERS_PATH.read_bytes())
        (d / "run.py").write_text(script, encoding="utf-8")
        (d / "facilities.json").write_text(json.dumps(facilities, ensure_ascii=False), encoding="utf-8")
        log("MOCK: running script in a local subprocess (no isolation!)")
        env = {**os.environ, "MPLCONFIGDIR": os.environ.get("MPLCONFIGDIR", str(d / "mpl"))}
        p = subprocess.run([sys.executable, "run.py"], cwd=d, capture_output=True, text=True, timeout=240, env=env)
        if p.returncode != 0:
            raise RuntimeError(f"local script failed: {p.stderr[-800:]}")
        result = json.loads((d / "out" / "result.json").read_text(encoding="utf-8"))
        map_png = (d / "out" / "map.png").read_bytes()
        return SandboxResult(provider="local-mock", stdout=p.stdout, exit_code=0,
                             result=result, map_png=map_png, sandbox_id="local")


def run(script: str, facilities: list[dict], log: Log) -> SandboxResult:
    if config.USE_DAYTONA:
        try:
            return run_in_daytona(script, facilities, log)
        except Exception as e:  # noqa: BLE001
            log(f"Daytona failed ({type(e).__name__}: {e}) -> falling back to local mock")
    return run_locally(script, facilities, log)


# ----------------------------------------------------- optional snapshot build ---
def build_snapshot(name: str = "geo-agent-py312") -> None:
    """One-off: pre-build a snapshot with deps so sandboxes start in ~1s. Then set DAYTONA_SNAPSHOT=name."""
    from daytona import CreateSnapshotParams, Daytona, DaytonaConfig, Image

    daytona = Daytona(DaytonaConfig(api_key=config.DAYTONA_API_KEY))
    daytona.snapshot.create(
        CreateSnapshotParams(name=name, image=Image.debian_slim("3.12").pip_install(config.SANDBOX_PIP)),
        on_logs=print,
    )
    print(f"snapshot '{name}' ready — add DAYTONA_SNAPSHOT={name} to .env")


if __name__ == "__main__":
    build_snapshot(sys.argv[1] if len(sys.argv) > 1 else "geo-agent-py312")
