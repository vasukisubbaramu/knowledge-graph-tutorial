"""Central configuration loaded from .env.

Why a module instead of inlining os.getenv calls in every notebook:
- Single source of truth for defaults
- One place to change if Anthropic releases a new model
- Notebooks read like prose: `config.MODEL_DEFAULT` not `os.getenv("KG_MODEL_DEFAULT", "claude-sonnet-4-6")`
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


# Claude
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_DEFAULT: str = os.getenv("KG_MODEL_DEFAULT", "claude-sonnet-4-6")
MODEL_REASONING: str = os.getenv("KG_MODEL_REASONING", "claude-opus-4-7")

# Embeddings (local)
EMBED_MODEL: str = os.getenv("KG_EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# Neo4j
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4j-tutorial")

# Paths
DATA_DIR: Path = Path(os.getenv("KG_DATA_DIR", ROOT / "data" / "synthetic"))
CHROMA_DIR: Path = Path(os.getenv("KG_CHROMA_DIR", ROOT / "data" / "chroma_db"))

# Behavior
VERBOSE_LLM: bool = os.getenv("KG_VERBOSE_LLM", "0") == "1"


def verify() -> None:
    """Raise if essential config is missing. Run at the top of every notebook."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
