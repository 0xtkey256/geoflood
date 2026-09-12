import os
from dotenv import load_dotenv

load_dotenv()

# --- Nosana (OpenAI-compatible LLM endpoint on decentralized GPU) ---
NOSANA_BASE_URL = os.getenv("NOSANA_BASE_URL", "").rstrip("/")  # e.g. https://<job-id>.node.k8s.prd.nos.ci/v1
NOSANA_MODEL = os.getenv("NOSANA_MODEL", "")
NOSANA_API_KEY = os.getenv("NOSANA_API_KEY", "nosana")

# optional fallbacks for the LLM step
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# --- Daytona ---
DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_SNAPSHOT = os.getenv("DAYTONA_SNAPSHOT", "")  # optional pre-built snapshot name

# --- Neo4j ---
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# --- kill switches (set to 0 to force mock even when creds exist) ---
def _flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default) not in ("0", "false", "False", "")

USE_NOSANA = _flag("USE_NOSANA") and bool(NOSANA_BASE_URL)
USE_DAYTONA = _flag("USE_DAYTONA") and bool(DAYTONA_API_KEY)
USE_NEO4J = _flag("USE_NEO4J") and bool(NEO4J_URI and NEO4J_PASSWORD)

SANDBOX_PIP = ["numpy", "pillow", "matplotlib", "requests"]
