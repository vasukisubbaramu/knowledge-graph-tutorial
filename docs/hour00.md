# Hour 0 — Setup notes

The notebook `hour00_setup.ipynb` is mostly verification, not concepts. This document captures the few facts about the *environment* that matter beyond simply getting cells to run.

## Why these specific choices

**Claude as the LLM.** We use Claude end-to-end because the tutorial assumes one capable LLM you can call repeatedly. Tutorial-grade is *not* a stand-in for production: in production you'll likely route easy calls to Sonnet or Haiku and reserve Opus for high-stakes reasoning. Hours 11–12 demonstrate that routing pattern explicitly.

**`sentence-transformers` for embeddings (BGE-small).** We avoid an embedding API for three reasons. One: it removes a key from your tutorial. Two: BGE-small is genuinely strong for this scale (~134 MB, 384-dim, runs in milliseconds on Apple Silicon). Three: it lets us *see* the embeddings — you can inspect, perturb, and compare without an API trace. In production you'll often choose a hosted embedding model (Voyage, OpenAI, Cohere) for the quality bump, but the *architecture* is identical.

**ChromaDB for the vector store.** Embedded, no server, persists to a local directory. We don't use FAISS because we want metadata filters out of the box; we don't use pgvector because it requires Postgres infrastructure that is overkill for a MacBook tutorial. The cost is that Chroma is *not* a production-grade vector store at scale — but at this scale, that doesn't matter.

**Neo4j Desktop for the graph database.** Neo4j Desktop is a single download, ships with the Neo4j Browser (which is your best teaching tool: you can *see* the graph), runs on ~500 MB at idle, and uses Cypher — the de-facto query language for property graphs.  The Community Edition is fine; no Enterprise features are used in this tutorial.

**LangGraph for the agent framework.** Hour 8 onward. LangGraph is currently the most popular framework for explicit-state agents in 2026; the conceptual ideas (planner, executor, critic) transfer cleanly to any other framework.

**`uv` instead of pip/venv.** No technical requirement, just speed. If you prefer pip + venv, the `pyproject.toml` works with both.

## Why the dataset is what it is

The synthetic dataset is built around **one pathological case** — "Project Lotus" — plus noise. The case has six features that surface different limits of each generation:

| # | Feature | Surfaces in |
|---|---------|-------------|
| 1 | Multi-hop ownership: Person → Cayman SPV → Panama SA → Liechtenstein GmbH | Gen 1 fails (Hour 3); Gen 2 succeeds (Hour 6) |
| 2 | Cross-link: the UBO also directs the deposit's originator | Why graphs find what similarity misses |
| 3 | Alias mismatch: deposit says "ATLAS WIRECORP", OFAC says "ATLAS WIRE CORPORATION" | Why crisp Cypher needs help from fuzzy matching (Hour 7) |
| 4 | PEP-relative: nephew of MP, only flagged if you read the policy footnote | Why retrieval ≠ reasoning (Hour 8) |
| 5 | Adverse media: secondary corroboration scattered across sources | Where Gen 3 tools earn their keep |
| 6 | Temporal: ownership has been stable for 5 years, but listings can land tomorrow | Why temporal KGs are the frontier (Hour 7's signpost to TIE) |

Memorize the chain *before* Hour 2:

```
John Q. Public  --50%-->  ACME Holdings Ltd (KY)
                                 │
                                 ▼
                                100%
                                 │
                                 ▼
                          AlphaBeta Trading SA (PA)
                                 │
                                 ▼
                                 75%
                                 │
                                 ▼
                          Gamma Operations GmbH (LI)  <-- the applicant
                                 │
                                 ▼
                          Account a_gamma_001 (pending)
                                 ↑
                                 │
                        EUR 500,000 inbound wire
                                 │
                                 │  counterparty:
                                 │  "ATLAS WIRECORP" (AE)
                                 │       │
                                 │       │  also directed by:
                                 │       ▼
                          John Q. Public  ←──── PEP-relative
                                         (nephew of MP Alice Public)

                          OFAC has:
                          "ATLAS WIRE CORPORATION" (AE)
                          Aliases: "Atlas Wire Co.", "Atlas Wire Corp.", "Атлас Уайр"
```

Everything in Hours 2–12 is a different way of asking *"is this safe to onboard?"*

## When you should *not* trust the tutorial setup

- **Costs.** If you run the full tutorial including all the agent loops in Hour 11, you'll spend on the order of \\$2–6 in Claude API calls. Set a billing alert. Use Sonnet for everything except the explicit Opus calls in Hours 8 and 11.
- **Embedding determinism.** sentence-transformers are deterministic given a fixed seed, but BGE outputs change slightly across model versions. Pin the model name if you build anything beyond the tutorial.
- **Neo4j password.** The default `neo4j-tutorial` is fine for a local install. *Never* reuse it.

## Done

Move on to `hour01_concepts.ipynb`. Hour 1 is dense — block 60 uninterrupted minutes for it.
