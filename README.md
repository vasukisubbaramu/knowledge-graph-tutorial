# Knowledge Graph Tutorial — Gen 1 → Gen 2 → Gen 3 RAG

A 12-hour, hands-on, self-paced tutorial that walks a senior practitioner from classical Vector RAG (Gen 1), through Knowledge-Graph-augmented RAG (Gen 2), to Agentic Hybrid Reasoning (Gen 3). The same realistic problem — Corporate KYC with Ultimate Beneficial Ownership tracing — is re-solved three different ways, so the architectural differences between the generations become visceral rather than abstract.

Each hour is roughly 60 minutes of dense material that takes 2–3 hours to absorb. Every hour ships as both a runnable Jupyter notebook (concept + code + "where this breaks") and a take-anywhere reading companion in Markdown.

**Audience.** Architects and engineers building knowledge-retrieval systems for compliance, risk, fraud, control, or similar high-stakes domains. Some prior familiarity with LLM APIs and Python is assumed; no prior domain knowledge is required (a Corporate KYC + UBO primer is included).

**Scope and disclaimers.**

- All data is synthetic. No real customers, no real sanctions screening, no real regulatory filings.
- The code is tutorial-grade — meant to be read and stepped through, not deployed.
- The repository contains no production credentials. The `.env` file is gitignored; only `.env.example` (with placeholder values) is committed.

---

## Tutorial structure

| Hour | Title | Generation | Status |
|------|-------|------------|--------|
| 0    | Setup and environment | — | ready |
| 1    | The retrieval problem and why Gen 1 → 3 | Framing | ready |
| 2    | Vector RAG, hands-on | Gen 1 | ready |
| 3    | Where Gen 1 breaks | Gen 1 → 2 transition | ready |
| 4    | Knowledge Graph foundations | Gen 2 | ready |
| 5    | Gen 2 — KG construction | Gen 2 | ready |
| 6    | Gen 2 — KG querying | Gen 2 | ready |
| 7    | Gen 2 limits and hybrid retrieval | Gen 2 → 3 transition | ready |
| 8    | Gen 3 — Agentic reasoning | Gen 3 | ready |
| 9    | Gen 3 — Context Graphs | Gen 3 | ready |
| 10   | Gen 3 — Hypergraphs | Gen 3 | ready |
| 11   | End-to-end Control Manager agent | Gen 3 | ready |
| 12   | Production, evaluation, governance | Cross-cutting | ready |

Each hour delivers:

- A runnable notebook at `notebooks/hourNN_*.ipynb` (concepts + executable labs + diagnostic failures).
- A reading companion at `docs/hourNN.md` (the same concepts without the code).

A domain primer for readers new to KYC and UBO is at `docs/kyc_ubo_primer.html` (open in a browser, ~20 minutes).

---

## Repository structure

```
Knowledge-Graph/
├── README.md                       this file
├── pyproject.toml                  package metadata + dependency manifest
├── .env.example                    template for ANTHROPIC_API_KEY and config
├── .gitignore
│
├── kg_tutorial/                    importable Python package (shared utilities)
│   ├── __init__.py
│   ├── config.py                   .env loader, central configuration
│   ├── llm.py                      Claude wrapper
│   ├── embed.py                    local sentence-transformers helper
│   ├── display.py                  Rich-based pretty-print helpers
│   ├── retrieval.py                chunking, ChromaDB, BM25, RRF, LLM rerank
│   ├── graph.py                    NetworkX + Neo4j helpers, visualization
│   ├── extract.py                  spaCy NER + Claude schema-guided extraction
│   ├── tools.py                    agent-callable tools (fuzzy match, sanctions check, KG lookups)
│   ├── agent.py                    LangGraph agent (plan → execute → critique → finalize)
│   ├── hyper.py                    hypergraph data structure and visualization
│   ├── eval.py                     evaluation harness for Hour 12
│   └── data/
│       ├── schema.py               Pydantic models for the KYC domain
│       ├── generate.py             synthetic dataset generator
│       └── load.py                 lookup helpers
│
├── data/
│   ├── synthetic/dataset.json      generated at first run (gitignored)
│   └── chroma_db/                  ChromaDB persistence (gitignored)
│
├── notebooks/                      open these in JupyterLab or VSCode
│   ├── hour00_setup.ipynb
│   ├── hour01_concepts.ipynb
│   ├── hour02_vector_rag.ipynb
│   ├── hour03_gen1_limits.ipynb
│   ├── hour04_kg_foundations.ipynb
│   ├── hour05_kg_construction.ipynb
│   ├── hour06_kg_querying.ipynb
│   ├── hour07_hybrid_retrieval.ipynb
│   ├── hour08_agentic_reasoning.ipynb
│   ├── hour09_context_graphs.ipynb
│   ├── hour10_hypergraphs.ipynb
│   ├── hour11_control_manager_agent.ipynb
│   └── hour12_production_eval.ipynb
│
├── docs/
│   ├── kyc_ubo_primer.html         domain primer for readers new to KYC + UBO
│   ├── hour00.md                   per-hour reading companions
│   ├── hour01.md
│   ├── hour02.md
│   ├── hour03.md
│   ├── hour04.md
│   ├── hour05.md
│   ├── hour06.md
│   ├── hour07.md
│   ├── hour08.md
│   ├── hour09.md
│   ├── hour10.md
│   ├── hour11.md
│   └── hour12.md
│
├── scripts/                        notebook generators (regeneratable)
│   ├── _nb.py                      tiny .ipynb writer
│   ├── build_hour00.py
│   ├── build_hour01.py
│   ├── build_hour02.py
│   ├── build_hour03.py
│   ├── build_hour04.py
│   ├── build_hour05.py
│   ├── build_hour06.py
│   ├── build_hour07.py
│   ├── build_hour08.py
│   ├── build_hour09.py
│   ├── build_hour10.py
│   ├── build_hour11.py
│   └── build_hour12.py
│
└── references/                     research papers cited in the docs (optional)
```

---

## Prerequisites

- **Python 3.11 or newer.** The package targets `>=3.11`. Earlier versions will fail at import.
- **An Anthropic API key.** Sign up at [https://console.anthropic.com](https://console.anthropic.com). The full tutorial costs on the order of \$2–6 in API calls if you run every cell.
- **Neo4j Desktop.** Only required from Hour 4 onwards. Free download at [https://neo4j.com/download/](https://neo4j.com/download/). Community Edition is fine.
- **Roughly 3–4 GB of disk** (most of it for the local embedding model and the BGE weights, downloaded on first use).
- **macOS, Linux, or WSL.** Designed to run on a single MacBook; everything works equivalently on Linux. Windows-native is not tested.

---

## Installation

### 1. Clone the repository

```bash
git clone <your-fork-or-this-repo>.git
cd Knowledge-Graph
```

### 2. Create a virtual environment

Use whatever you prefer. Two common choices:

**Option A — standard `venv` + `pip`:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**Option B — `uv` (faster, recommended if you have it):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # one-time install
uv venv --python 3.11
source .venv/bin/activate
```

### 3. Install dependencies

The full dependency set covers all 12 hours. Install it in one shot so you don't hit `ModuleNotFoundError` partway through:

```bash
pip install \
  anthropic \
  sentence-transformers \
  chromadb \
  neo4j \
  langgraph langchain-anthropic langchain-core \
  pandas pydantic faker spacy \
  rank-bm25 \
  jupyter ipywidgets \
  rich \
  python-dotenv \
  matplotlib networkx pyvis \
  scikit-learn
```

Or, equivalently, install the project in editable mode (uses `pyproject.toml`):

```bash
pip install -e .
```

### 4. Pin NumPy (defensive — recommended on miniconda / mixed envs)

Some packages still ship wheels compiled against NumPy 1.x. Mixing them with NumPy 2.x can crash silently. Pin to be safe:

```bash
pip install "numpy<2"
```

### 5. Download the spaCy English model

Required from Hour 5 onwards (NER baseline):

```bash
python -m spacy download en_core_web_sm
```

### 6. Configure your API key

```bash
cp .env.example .env
# open .env in your editor and set:
#   ANTHROPIC_API_KEY=sk-ant-...
```

### 7. Generate the synthetic dataset

```bash
python -m kg_tutorial.data.generate
```

This writes `data/synthetic/dataset.json` (deterministic, regeneratable).

### 8. (From Hour 4 onwards) Set up Neo4j Desktop

1. Install Neo4j Desktop.
2. Create a new project, add a Local DBMS.
3. Set the password to `neo4j-tutorial` (matches `.env.example`).
4. Click **Start** and wait for the "Active" indicator.

You do not need Neo4j for Hours 0–3. Hour 0 has a connection check that fails gracefully when Neo4j is absent.

### 9. Launch Jupyter

```bash
jupyter lab
```

Open `notebooks/hour00_setup.ipynb` and run from the top.

---

## Running the tutorial

The notebooks are designed to be run in order. Each hour assumes the artifacts (vector index, KG, agent definitions) created by previous hours, but every hour also re-initializes its dependencies so any single notebook can be re-run from scratch.

**A note on `kg_tutorial` imports.** Every notebook starts with a tiny bootstrap cell that adds the project root to `sys.path`. This means the notebooks work whether you launched Jupyter from the project root or from `notebooks/`, with or without `pip install -e .`. You should not have to touch it.

**Regenerating a notebook.** If you edit a `scripts/build_hourNN.py`, regenerate the corresponding notebook:

```bash
python scripts/build_hour02.py    # rewrites notebooks/hour02_vector_rag.ipynb
```

---

## Stack choices

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Claude (Sonnet for routine, Opus for heavy reasoning) | Quality with cost awareness; the agent hour uses Opus deliberately |
| Embeddings | `sentence-transformers` (BGE-small) | Local, no extra API key, fast on Apple Silicon, ~134 MB |
| Vector store | ChromaDB (embedded) | No server; persists to a directory; replaces pgvector with zero ops |
| Graph database | Neo4j Desktop (Community Edition) | Single download; the Neo4j Browser visualization is invaluable for teaching |
| Agent framework | LangGraph | Explicit state graphs, easy to inspect agent decisions |
| Env / packaging | `pip` + `venv` or `uv` | Either works; the project is a standard `pyproject.toml` |

The choices are deliberately MacBook-scale. Nothing in the tutorial requires a GPU, Kubernetes, a managed database, or a separate vector-store service.

---

## A note on the Gen 1 / 2 / 3 framing

You may have heard "Gen 1 is stale, Gen 2 is yesterday, Gen 3 is the future." That's vendor framing — useful as a story, misleading as architecture. The honest framing this tutorial argues for:

- **Vector RAG (Gen 1)** is the right tool for *semantic similarity over unstructured text*. It is not deprecated.
- **Graph RAG (Gen 2)** adds what Vector RAG fundamentally cannot do — *multi-hop relational reasoning*. It is complementary, not a replacement.
- **Agentic / Hybrid (Gen 3)** is about *orchestration and verification* — an agent decides when to use vector vs graph vs structured queries vs tools, and critiques its own output.

The production architecture is hybrid. The interesting question is not "which generation wins" but "which retrieval mode does this *query* deserve, and how do I know the answer is right?" That question is what Hours 11 and 12 are about.

---

## Frontier signposts

Hours 4, 7, and 12 reference (without implementing) research that sits past the scope of this tutorial:

- **ULTRA / GAMMA** — Knowledge-graph foundation models. Universal inductive reasoning over arbitrary KGs.
- **TIE** — Temporal KG completion. KGs in finance are temporal; ownership changes, listings expire, sanctions are added.
- **KumoRFM** — Relational foundation models. Enterprise data is overwhelmingly relational; KumoRFM extends in-context learning to multi-table relational settings.

These are the "Gen 4 onward" frontier. The point of the tutorial is to make those papers read fluently as natural next steps after Hour 12.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'kg_tutorial'`**
The package isn't on the import path. Either install it (`pip install -e .` from the project root, then restart the Jupyter kernel), or rely on the bootstrap cell at the top of every notebook (it adds the project root to `sys.path` automatically — make sure you run it first).

**`ModuleNotFoundError: No module named 'neo4j'` in Hour 0**
Expected if you haven't installed Neo4j yet. Hour 0's Neo4j check is wrapped in `try/except` and prints `"Neo4j not reachable yet — that's OK for Hours 0–3."` followed by the cause. Continue to Hour 1. Install Neo4j Desktop before Hour 4.

**`tqdm IProgress not found. Please update jupyter and ipywidgets.`**
Cosmetic. Update with:

```bash
pip install -U ipywidgets
```

Restart the kernel.

**`A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x`**
Some package's wheel hasn't caught up. Pin NumPy:

```bash
pip install "numpy<2"
```

Restart the kernel.

**ChromaDB telemetry messages**
Disabled in code by setting `anonymized_telemetry=False`. If you still see them, you have an older ChromaDB; upgrade.

**Anthropic 401 / authentication error**
Re-check `.env` — `ANTHROPIC_API_KEY` must be present and valid. After editing `.env`, restart the kernel so the new value is picked up.

**Neo4j connection refused (from Hour 4)**
Neo4j Desktop is not running, or the password doesn't match `.env`. The default in `.env.example` is `neo4j-tutorial`. Verify the DBMS is started and the password matches.

---

## Cost notes

The tutorial uses Claude Sonnet for most calls and Claude Opus for the heavy-reasoning hour. Approximate cost for running every cell of every hour end-to-end is **\$2–6**. Set a billing alert. The local embedding model (BGE-small via `sentence-transformers`) is free.

---

## Contributing

This is an educational repository. PRs welcome for:

- Bug fixes in the helper code (`kg_tutorial/`).
- Clarifications or typo fixes in the notebooks and reading docs.
- Additional troubleshooting entries for issues other readers may hit.

Not in scope: production-grade implementations, additional vendors, or significant scope changes to the hours. The tutorial is intentionally bounded.

---

## License

No license has been set. If you intend to fork, reuse, or republish, please add a license file appropriate to your needs. The synthetic data and code are released for educational use without warranty.
