"""Build notebooks/hour01_concepts.ipynb — the framing hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    # ------------------------------------------------------------------
    # 1. Opening
    # ------------------------------------------------------------------
    ("md", """\
# Hour 1 — The retrieval problem and why Gen 1 → 3

> *60 minutes of dense material, 2–3 hours to absorb. No vector store, no graph DB — only Claude and the Lotus dataset. The goal of this hour is to see, with your own eyes, what an LLM alone can and cannot do, and to leave with an architecture-level map of the three generations.*

**Reading companion:** [`docs/hour01.md`](../docs/hour01.md)

You are a senior architect. Skip the "what is RAG" recap — it isn't here. Instead we'll build, in this single hour, the conceptual scaffold you'll spend the next 12 hours filling in.
"""),
    # ------------------------------------------------------------------
    # 2. Setup
    # ------------------------------------------------------------------
    ("code", """\
from kg_tutorial import config, llm, display
from kg_tutorial.data import load

config.verify()
bundle = load.load()
"""),
    # ------------------------------------------------------------------
    # 3. Section 1 — The retrieval problem
    # ------------------------------------------------------------------
    ("md", """\
## 1. The retrieval problem in one sentence

> *An LLM trained at time T cannot know facts that exist only at time T+ε or behind your firewall, and even if it could, it has no mechanism to be made to use them.*

That is the entire premise of every "RAG" architecture. The differences between Gen 1, Gen 2, and Gen 3 are not differences of *whether* to retrieve — they are differences of **what shape of data you retrieve over, and who decides how**.

We'll demonstrate the premise immediately. The cell below asks Claude about Gamma Operations GmbH — a private entity it has never seen.
"""),
    ("code", """\
question = (
    "Should a European bank approve the corporate account-opening application "
    "for Gamma Operations GmbH, a Liechtenstein company recently introduced by "
    "an external relationship manager? Cite specific facts."
)

answer = llm.ask(question, max_tokens=400)
display.md(answer)
"""),
    ("md", """\
The model will produce something polite, conditional, and vague — because it has nothing to cite. *This is not a hallucination problem; it's a context problem.* The model is **correctly refusing to invent specifics**. Our job in the next 12 hours is to give it specifics in a useful shape.

### Three classes of failure that retrieval solves

| Failure | What it sounds like | Which generation fixes it |
|---|---|---|
| **Closed-world ignorance** | "I don't have information about this entity." | Gen 1 (any retrieval) |
| **Disconnected facts** | Two relevant facts are retrieved but the model never relates them. | Gen 2 |
| **Wrong question / no verification** | The model answers confidently using stale or partial context. | Gen 3 |

Hold this table — every hour from 2 to 11 is a longer treatment of one row.
"""),
    # ------------------------------------------------------------------
    # 4. Section 2 — Gen 1 in one diagram
    # ------------------------------------------------------------------
    ("md", """\
## 2. Gen 1 — Vector RAG in one diagram

```text
                ┌──────────────────────────────────────┐
   Question ──> │  Embed (sentence model)              │
                └────────────────┬─────────────────────┘
                                 │
                                 ▼
                ┌──────────────────────────────────────┐
                │  Top-k similar chunks (vector store) │
                └────────────────┬─────────────────────┘
                                 │
                                 ▼
                ┌──────────────────────────────────────┐
                │  Stuff into prompt: "Given context X,│
                │  answer the question Y."             │
                └────────────────┬─────────────────────┘
                                 │
                                 ▼
                            Answer + cites
```

**Strengths.** Cheap, fast, and very good when the relationship between the question and the answer is fundamentally one of *semantic similarity over text*.

**Built-in assumptions you may not have noticed.**

- Chunks are *independent*. The retrieval algorithm has no notion of "this chunk is connected to that one."
- Ranking is *contextless*. A chunk that's similar to the question by surface meaning beats a chunk that *answers* the question.
- The model receives *unstructured prose*, not entities. The model is left to do all the work of "John = the same John in the other chunk."
"""),
    # ------------------------------------------------------------------
    # 5. Section 3 — Gen 2 in one diagram
    # ------------------------------------------------------------------
    ("md", """\
## 3. Gen 2 — Graph RAG in one diagram

```text
                ┌──────────────────────────────────────┐
   Documents ──>│  Extract entities + relations        │
                └────────────────┬─────────────────────┘
                                 │  (one-time, offline)
                                 ▼
                ┌──────────────────────────────────────┐
                │  Knowledge Graph (nodes + edges)     │
                └────────────────┬─────────────────────┘
                                 │
   Question ──> Entity-link ──>  Subgraph retrieval ───┐
                                                       │
                                                       ▼
                ┌──────────────────────────────────────┐
                │  Subgraph + supporting text → LLM    │
                └────────────────┬─────────────────────┘
                                 │
                                 ▼
                          Connected answer
```

**What's new.** The structure is preserved across documents. "John controls ACME" and "ACME controls AlphaBeta" remain two edges; combined, they answer "who controls AlphaBeta?" — a question no single chunk contains the answer to.

**Built-in assumptions you may not have noticed.**

- Extraction is *brittle*: the KG is only as good as your NER + relation-extraction pipeline.
- The schema is *static*: new relationship types require redesign.
- Cypher/Gremlin queries are *crisp* — they don't naturally handle "the originator's name is approximately this OFAC entry's name."
- Reasoning is still done by the LLM at the end; the KG is *retrieval*, not inference.
"""),
    # ------------------------------------------------------------------
    # 6. Section 4 — Gen 3 in one diagram
    # ------------------------------------------------------------------
    ("md", """\
## 4. Gen 3 — Agentic + Hybrid in one diagram

```text
                ┌──────────────────────────────────────┐
   Question ──> │  Planning agent: decompose the query │
                └────────────────┬─────────────────────┘
                                 │
                                 ▼
                ┌──────────────────────────────────────┐
                │  Adaptive retrieval                  │
                │   - vector search (semantic)         │
                │   - graph traversal (relational)     │
                │   - structured query (SQL/KG)        │
                │   - external tools (sanctions API,   │
                │     adverse media search, fuzzy NER) │
                └────────────────┬─────────────────────┘
                                 │
                                 ▼
                ┌──────────────────────────────────────┐
                │  Reasoning trace + self-critique     │
                │   "Does this answer the question?"   │
                │   "Are my citations sufficient?"     │
                │   "Is there a counter-hypothesis?"   │
                └────────────────┬─────────────────────┘
                                 │
                                 ▼
                      Final answer + audit trail
```

**What's new.** Three things, none of which Gen 2 has:

1. **Orchestration.** The agent decides which retrieval mode each sub-question needs.
2. **Self-verification.** The agent grades its own answer and re-tries when uncertain (Self-RAG, CRAG, Reflexion patterns — Hour 8).
3. **Tool use.** External capabilities — sanctions APIs, fuzzy matchers, code execution — become first-class.

**The cost.** Latency, dollars, and the ever-present risk of agentic loops. We address all three in Hours 8, 11, and 12.
"""),
    # ------------------------------------------------------------------
    # 7. Section 5 — The triangle
    # ------------------------------------------------------------------
    ("md", """\
## 5. The Cost–Capability–Latency triangle

The marketing story is "Gen 3 strictly dominates Gen 2 strictly dominates Gen 1." The architecture story is different.

|                | Gen 1 (Vector) | Gen 2 (Graph) | Gen 3 (Agentic) |
|----------------|----------------|---------------|-----------------|
| **Setup cost** | Low — embed your corpus once. | High — extraction + schema design. | Very high — agent design, tools, eval harness. |
| **Per-query cost** | Cheap (one embed + one LLM call). | Modest (one LLM call + KG query). | Expensive (N LLM calls + N tool calls + critique). |
| **Per-query latency** | <1 s | 1–3 s | 5–60 s |
| **Capability ceiling** | Semantic similarity. | Multi-hop relational reasoning. | Open-ended reasoning with verification. |
| **Failure mode** | Misses connections. | Brittle to extraction errors and schema drift. | Loops, hallucinations under tool stress. |
| **Audit story** | Cited chunks. | Cited subgraph. | Full reasoning trace. |

A control manager reviewing 200 CDD cases a day cannot afford to spend 60 seconds and \\$0.40 on each one through a Gen 3 agent. They also cannot afford to *miss* a sanctions match by spending 1 second on Gen 1.

> *The interesting design question is **not** "which generation do we use?" — it's "which retrieval mode does each kind of query deserve?"*

Hour 11 builds an agent that **routes** the question. Hour 12 builds the **eval harness** that proves the routing is correct.
"""),
    # ------------------------------------------------------------------
    # 8. Section 6 — Is Gen 1 stale?
    # ------------------------------------------------------------------
    ("md", """\
## 6. "Is Gen 1 stale?"

You may have heard that Gen 1 is stale. It is not. Three quick observations.

1. **Pure semantic similarity remains the right hammer for many nails.** "Find me policy text about EDD for PEPs" is a Gen 1 question. A graph would slow you down.
2. **Every Gen 2 system has Gen 1 inside it.** Microsoft GraphRAG retrieves community summaries via vector similarity. LlamaIndex's KG retrievers re-rank with embeddings.
3. **Every Gen 3 system has Gen 1 and Gen 2 as tools.** The agent calls them.

The honest framing is layered:

```text
Gen 3 (orchestrate + verify)
  ├── Gen 2 (structure + multi-hop)
  ├── Gen 1 (similarity over unstructured text)
  └── Tools (sanctions, code, calculators, fuzzy match, ...)
```

Gen 1 is the floor. Gen 2 is the walls. Gen 3 is the project manager. They build the same house.
"""),
    # ------------------------------------------------------------------
    # 9. Section 7 — The Lotus case briefing
    # ------------------------------------------------------------------
    ("md", """\
## 7. The Lotus case — what answer must we produce?

Print the case briefing. Read it once. Then read it again and write down what *you* think the answer should be — you'll compare against Gen 1's answer in Hour 2, Gen 2's in Hour 6, and Gen 3's in Hour 11.
"""),
    ("code", """\
from kg_tutorial.data import load
b = load.load()

print("APPLICANT")
g = load.entity("e_gamma_ops")
print(f"  {g.legal_name} ({g.entity_type.value}, {g.jurisdiction})")
print(f"  Address: {g.registered_address}")
print(f"  Activity: {g.notes}")

print()
print("OWNERSHIP CHAIN (declared)")
print("  Gamma Operations GmbH  <-- 75% -- AlphaBeta Trading SA  <-- 100% --  ACME Holdings Ltd  <-- 50% --  John Q. Public")

print()
print("KEY FACTS (scattered across documents and reference data)")
print("  - John Q. Public is a PEP-relative (nephew of MP Alice Public).")
print("  - John Q. Public is *also* a director of Atlas Wirecorp (UAE).")
print("  - The first incoming deposit (EUR 500,000) is from 'ATLAS WIRECORP'.")
print("  - OFAC lists 'ATLAS WIRE CORPORATION' (UAE, ER 13224) — near-match.")
print("  - Adverse media (2024) names John Q. Public in connection with ACME.")
print("  - Bank policy treats nephews of sitting MPs as PEP-relatives requiring EDD.")
print("  - Bank policy: fuzzy sanctions score >= 85 must escalate, regardless of business comfort.")
"""),
    # ------------------------------------------------------------------
    # 10. Demo — Claude with all docs in context
    # ------------------------------------------------------------------
    ("md", """\
## 8. Demo — give Claude *everything* and ask

Before we build any retrieval system, let's see what happens if we just paste all 7 documents into the prompt and ask the question. This is the "naive baseline." It will be surprisingly competent — and surprisingly fragile. Watch *which* facts the model connects and which it misses.
"""),
    ("code", """\
all_docs = "\\n\\n---\\n\\n".join(
    f"### {d.title}\\n\\n{d.body}" for d in bundle.documents
)

prompt = f\"\"\"You are a senior bank control manager. Given the seven documents below,
write a one-paragraph recommendation on whether to approve the account opening
for Gamma Operations GmbH. Cite specific document titles for each claim. End with
APPROVE, DECLINE, or ESCALATE.

DOCUMENTS:
{all_docs}
\"\"\"

answer = llm.ask(prompt, max_tokens=600, model=config.MODEL_DEFAULT)
display.md(answer)
"""),
    ("md", """\
**Stop and think before you scroll.**

- Did Claude notice the cross-link between John Q. Public being UBO of ACME *and* a director of Atlas Wirecorp?
- Did Claude recognise the alias-mismatch between "ATLAS WIRECORP" (deposit narrative) and "ATLAS WIRE CORPORATION" (OFAC list)?
- Did Claude trigger the PEP-relative policy paragraph (Sec. 3.2(e) of the PEP policy)?
- How did the answer cite — by document title? By section? By line?
- Is the answer *defensible* in front of a regulator?

This single prompt is the asymptotic ceiling of "stuff everything into context." We will outperform it from Hour 2 on — not by adding cleverness to the prompt, but by giving Claude the **shape** of the data, not just its bytes.
"""),
    # ------------------------------------------------------------------
    # 11. Roadmap + "where we are heading"
    # ------------------------------------------------------------------
    ("md", """\
## 9. Where this is heading

| Hour | What you'll build | The hard truth you'll learn |
|------|------------------|-----------------------------|
| 2    | Vector RAG over the 7 docs | Surface similarity isn't the same as *answering* |
| 3    | A query that breaks Gen 1 | The Lotus chain is invisible to similarity |
| 4    | A KG ontology for KYC + UBO | FIBO, schema vs schema-free, the cost of design |
| 5    | Build the KG by extraction | LLM-extracted graphs are useful and lossy |
| 6    | Cypher + text-to-Cypher | Crisp queries, brittle when reality isn't crisp |
| 7    | Hybrid retrieval (vector + graph) | Production reality starts here |
| 8    | An agent with self-critique | ReAct, Self-RAG, CRAG — and how loops happen |
| 9    | Context Graphs | Why "prompt engineering" was misnamed |
| 10   | Hypergraphs for transactions | When binary edges aren't enough |
| 11   | End-to-end Control Manager agent | Multi-agent, HITL, full citation chain |
| 12   | Eval, cost, governance | The right answer to "which generation?" is "depends" |

And, as signposts to the research frontier sitting on your bookshelf:

- ULTRA / GAMMA — universal inductive reasoning over arbitrary KGs (Hour 4, 7).
- TIE — temporal KG completion when the graph changes (Hour 7).
- KumoRFM — relational foundation models for enterprise data (Hour 12).

These are *post*-this-tutorial. The whole point of the next 11 hours is to make those papers read as natural next steps, not as inscrutable jargon.
"""),
    # ------------------------------------------------------------------
    # 12. Closing prompt
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think

Before Hour 2, write down (on paper) your answers to three questions. We'll come back to them in Hour 12.

1. **What query, in your current platform, deserves Gen 1?** Why is similarity sufficient there?
2. **What query deserves Gen 2?** What is the *connection* that similarity cannot find?
3. **What query deserves Gen 3?** What *verification* would you want before showing the answer to a control manager?

If you can answer these three after Hour 12 with a structurally different answer than today, the tutorial worked.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour01_concepts.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
