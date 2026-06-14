"""Build notebooks/hour00_setup.ipynb."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    # 1
    ("md", """\
# Hour 0 — Setup & environment

> *15–20 minutes. Verify everything works, get your hands on the synthetic dataset, and meet the **Lotus case** that will follow you for the next 12 hours.*

If any cell below fails, fix the cause and re-run from the top — every subsequent hour assumes the checks in this hour pass.

**Reading companion:** [`docs/hour00.md`](../docs/hour00.md)
"""),
    # 2
    ("md", """\
## What we verify

1. Python 3.11+ and the project is installed.
2. `ANTHROPIC_API_KEY` is set in `.env`.
3. The local embedding model loads and produces a vector.
4. Claude responds to a one-shot call.
5. The synthetic dataset exists (and we regenerate it if not).
6. Neo4j is running (optional — only needed from Hour 4 onwards).

Then we take a first look at the **Lotus case** — the corporate-KYC + UBO scenario the tutorial centres on.
"""),
    # 3
    ("md", "## 1. Python and the project package"),
    ("code", """\
import sys
print("Python:", sys.version.split()[0])
assert sys.version_info >= (3, 11), "Need Python 3.11+"

import kg_tutorial
print("kg_tutorial:", kg_tutorial.__version__)
"""),
    # 4
    ("md", "## 2. Configuration and credentials"),
    ("code", """\
from kg_tutorial import config

config.verify()  # raises if ANTHROPIC_API_KEY is missing

print("Default model:    ", config.MODEL_DEFAULT)
print("Reasoning model:  ", config.MODEL_REASONING)
print("Embedding model:  ", config.EMBED_MODEL)
print("Data directory:   ", config.DATA_DIR)
"""),
    # 5
    ("md", """\
## 3. Local embedding model

First call downloads ~134 MB to `~/.cache/huggingface/`. Subsequent calls are instant on Apple Silicon.
"""),
    ("code", """\
from kg_tutorial import embed

v = embed.embed("Ultimate Beneficial Owner")
print(f"Vector shape: {v.shape}, norm: {(v @ v) ** 0.5:.4f}")
print(f"Embedding dimension: {embed.dimension()}")
"""),
    # 6
    ("md", "## 4. Claude is reachable"),
    ("code", """\
from kg_tutorial import llm

response = llm.ask(
    "In ten words or fewer, what is the FATF?",
    max_tokens=40,
)
print(response)
"""),
    # 7
    ("md", """\
## 5. The synthetic dataset

If you've already run `uv run python -m kg_tutorial.data.generate`, this loads it. Otherwise the next cell generates it (deterministic — same seed every time).
"""),
    ("code", """\
from kg_tutorial.data import generate, load

try:
    bundle = load.load()
except FileNotFoundError:
    print("Generating dataset...")
    generate.write_dataset()
    load.load.cache_clear()
    bundle = load.load()

print("Dataset stats:")
for k, v in bundle.stats().items():
    print(f"  {k:>15}: {v}")
"""),
    # 8
    ("md", """\
## 6. Neo4j (optional now, required from Hour 4)

If Neo4j Desktop is running with the password from `.env.example`, the next cell will print a count of zero nodes. If you don't have Neo4j up yet, the cell will tell you — that's fine for Hours 0–3.

**Install:** download [Neo4j Desktop](https://neo4j.com/download/), create a project, add a *local DBMS* with password `neo4j-tutorial`, and click **Start**.
"""),
    ("code", """\
from kg_tutorial import config

try:
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
    )
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS n")
        n = result.single()["n"]
    driver.close()
    print(f"Neo4j is up. Current node count: {n}")
except Exception as e:
    print(f"Neo4j not reachable yet — that's OK for Hours 0–3.")
    print(f"  Cause: {type(e).__name__}: {e}")
"""),
    # 9
    ("md", """\
## 7. Meet the Lotus case

This is the worked example for every hour. Memorize the shape of the chain — every subsequent lab refers back to it.
"""),
    ("code", """\
from kg_tutorial.data import load

b = load.load()

lotus_people = ["p_john_q_public", "p_alice_public", "p_maria_rossi", "p_tomas_velasco"]
lotus_entities = ["e_gamma_ops", "e_alphabeta_trading", "e_acme_holdings", "e_atlas_wirecorp"]

print("=== Persons ===")
for pid in lotus_people:
    p = load.person(pid)
    flag = " [PEP]" if p.is_pep else ""
    print(f"  {p.full_name}{flag} — {p.nationalities[0]}, resides {p.residence_country}")

print()
print("=== Entities ===")
for eid in lotus_entities:
    e = load.entity(eid)
    print(f"  {e.legal_name} ({e.entity_type.value}, {e.jurisdiction})")

print()
print("=== Control edges ===")
for c in b.controls:
    ctrl = c.controller_id
    ctrld = c.controlled_id
    pct = f" ({c.ownership_pct:.0f}%)" if c.ownership_pct is not None else ""
    print(f"  {ctrl}  --{c.control_type.value}{pct}-->  {ctrld}")
"""),
    # 10
    ("md", """\
## 8. The question we will answer 13 ways

**Should this bank approve the account-opening application for Gamma Operations GmbH?**

Stop here and write down — in 2-3 lines — what you would want a control manager to know before signing off. By Hour 12 you'll have produced answers in:

- Gen 1 (Vector RAG) — and seen it fail.
- Gen 2 (Graph RAG) — and seen where it strains.
- Gen 3 (Hybrid + Agent) — with self-evaluation and full citation chain.

The same case, three architectures. The point of this tutorial is to make the difference *visceral*.
"""),
    # 11
    ("md", """\
---

## Done

If every cell above ran without error, you're ready. Next: [Hour 1 — The retrieval problem](./hour01_concepts.ipynb).

If Neo4j wasn't up, leave it — install it before Hour 4.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour00_setup.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
