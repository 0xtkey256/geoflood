"""Vercel entry point — re-exports the FastAPI app from the repo root."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")  # matplotlib needs a writable config dir on Vercel

from app import app  # noqa: E402,F401
