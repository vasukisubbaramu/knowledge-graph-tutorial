"""Build notebooks/hour09_context_graphs.ipynb — Gen 3 context engineering hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 9 — Gen 3: Context Graphs

> *60 minutes dense, 2–3 hours to absorb. The complement to Hour 8. You will build query-specific context graphs that combine document chunks, KG subgraphs, and prior tool outputs into a structured input the agent reasons over. The term to learn is **context engineering** — the discipline that replaces "prompt engineering" once prompts get serious.*

**Reading companion:** [`docs/hour09.md`](../docs/hour09.md).
"""),
    ("code", """\
from kg_tutorial import config, llm, display, tools
from kg_tutorial.data import load
from kg_tutorial.graph import bundle_to_networkx, networkx_to_text
from kg_tutorial.retrieval import chunk_documents, VectorIndex, BM25Index, rrf_combine

config.verify()
bundle = load.load()
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. Knowledge graph vs Context graph

A **knowledge graph** is the long-lived store: persisted, schema-bound, queryable, large.

A **context graph** is something subtler. It is the *transient, query-specific structured input* you build for the LLM at inference time. It typically contains:

- A slice of the KG (relevant entities, edges, properties).
- A handful of unstructured chunks the retrievers brought back.
- Outputs of tool calls (sanctions scores, adverse-media hits, fuzzy matches).
- Prior dialog turns (for conversational agents).
- Constraint reminders ("the response must include citations; the response must end with one of APPROVE / DECLINE / ESCALATE").

A context graph is *not* a graph database. It is a structured assembly — usually serialised as text — that gives the LLM exactly the right shape and content for the question it needs to answer.

> **The shift from prompt engineering to context engineering.** Prompt engineering was about phrasing the *instruction*. Context engineering is about *assembling the input* — what evidence to include, in what order, with what structure, from which sources, with which citations. This is the dominant discipline of 2026 LLM systems.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Three memory types

When the agent runs for a session — answering several questions about the same customer, say — it has three forms of memory at play:

| Memory | What it holds | Lifetime |
|---|---|---|
| **Working** | The current question, the evidence collected this turn, the critic's last feedback | One turn |
| **Episodic** | What happened in prior turns of this session — what the user asked, what was concluded | One session |
| **Semantic** | What was learned that's worth keeping for future sessions — domain facts, user preferences | Indefinite |

Hour 9 focuses on the *working* memory — the context the LLM sees this turn. Hour 11 adds episodic and (lightly) semantic via the agent state and external memory stores.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Build a context graph for one Lotus sub-question

The sub-question: *"Should the deposit be escalated under our sanctions policy?"*

A naive context would be "give Claude everything." A good context is curated:

1. **Anchor.** What entity is this question about? (`dep_001`)
2. **Local structure.** Pull the subgraph around `dep_001` (1-2 hops).
3. **Relevant tool outputs.** Sanctions check, fuzzy name match.
4. **Relevant unstructured chunks.** The sanctions policy doc only.
5. **Constraints.** Bank's policy thresholds, the expected response shape.

Building this is the hour's exercise.
"""),
    ("code", """\
# Step 1 - anchor identification
anchor_id = "dep_001"
deposit = bundle.deposits[0]
print(f"Anchor: deposit {anchor_id}, EUR {deposit.amount_eur:,.0f} from '{deposit.counterparty_name}'")

# Step 2 - local KG structure around the anchor
G = bundle_to_networkx(bundle)
local_nodes = set()
local_nodes.add(anchor_id)
local_nodes.add(deposit.account_id)
# Add the chain reaching the account
for u, v, d in G.edges(data=True):
    if u in local_nodes or v in local_nodes:
        local_nodes.add(u); local_nodes.add(v)
# One more hop
for u, v, d in G.edges(data=True):
    if u in local_nodes or v in local_nodes:
        local_nodes.add(u); local_nodes.add(v)
local_subgraph = G.subgraph(local_nodes).copy()
print(f"Local subgraph: {local_subgraph.number_of_nodes()} nodes")
"""),
    ("code", """\
# Step 3 - relevant tool outputs
sanc = tools.sanctions_check(deposit.counterparty_name)
fuzzy = tools.fuzzy_name_match(deposit.counterparty_name, list_kind="sanctions")

# Step 4 - just the sanctions policy chunk
docs_chunks = chunk_documents([d for d in bundle.documents if d.id == "d_policy_sanctions"], strategy="paragraph", max_chars=800)
policy_chunk_text = "\\n\\n".join(c.text for c in docs_chunks)

# Step 5 - explicit constraints (these will be in the prompt header)
constraints = (
    "The bank's policy on sanctions screening: escalate at fuzzy match >= 85; review at >= 70."
)
"""),
    ("code", """\
# Compose the context graph as structured text
context_graph_text = f\"\"\"
=== CONTEXT GRAPH for question: should deposit {anchor_id} be escalated? ===

[STRUCTURE]
{networkx_to_text(local_subgraph)}

[TOOL OUTPUTS]
- sanctions_check(name='{deposit.counterparty_name}') -> {sanc.summary}
    Top hits: {[h for h in sanc.evidence['hits'][:3]]}
- fuzzy_name_match(query='{deposit.counterparty_name}', list_kind='sanctions') -> {fuzzy.summary}

[POLICY EVIDENCE]
{policy_chunk_text}

[CONSTRAINTS]
{constraints}
\"\"\"
print(context_graph_text[:3000])
print("..." if len(context_graph_text) > 3000 else "")
"""),
    ("md", """\
**Look at the assembled context.** It has three loadbearing properties that a naive "stuff everything in the prompt" approach does not:

1. **It is small.** Maybe 1500 tokens. A naive context would be 10x larger.
2. **It is structured.** Sections are labelled; sources are named; tool outputs are distinguishable from prose.
3. **It is sufficient.** Every fact the answer needs is present; nothing irrelevant is present.

That's context engineering. Now ask the question:
"""),
    ("code", """\
prompt = (
    context_graph_text
    + "\\n\\nQUESTION: Should this deposit be escalated? Cite the specific tool outputs and policy paragraph supporting your decision."
)
answer = llm.ask(prompt, max_tokens=400, model=config.MODEL_DEFAULT)
display.md(answer)
"""),
    ("md", """\
The answer should be ESCALATE, citing the 93.3% fuzzy match, the policy's 85% threshold, and (if the policy chunk is visible) the specific sentence in the policy about not dismissing fuzzy matches on business comfort.

**Compare to the same question answered with a naive "all 7 docs in prompt" context.** The naive answer is more verbose, less precise, harder to audit. The context-engineered answer is short, structured, defensible.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Context engineering vs prompt engineering

The two activities and where each matters:

| Activity | What it tunes | When you reach its ceiling |
|---|---|---|
| **Prompt engineering** | The instruction, the format, the persona | When you've nailed the wording and the answer still misses facts the model never saw |
| **Context engineering** | What facts the model sees, in what shape, with what provenance | When the input is right but the model still chooses wrong from among facts |

Prompt engineering hit a wall around 2024. Once instruction-tuned models became capable, the marginal gain from "better wording" plateaued. The marginal gain from **better-curated input** did not plateau. That is why every serious 2026 LLM platform has more engineering investment in context assembly than in prompt phrasing.

This shift has names — *"context engineering,"* *"retrieval-augmented context,"* *"prompt compression"* — none of which are settled. The phenomenon is the same: the discipline of choosing, structuring, and provenance-tagging the input.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. The reasoning trace as memory

Look back at the Hour 8 agent's `state.trace`. It is a record of what the agent did:

- PLAN: 2 sub-tasks
- EXEC: sanctions_check(...) -> ESCALATE...
- CRITIQUE: sufficient=False :: missing the chain
- PLAN: 1 sub-task
- EXEC: controls_chain(...) -> 3 paths
- CRITIQUE: sufficient=True
- FINAL: ESCALATE

This trace is **the audit log** the control-management platform needs. A control manager reading it can:

- Verify the agent considered the right evidence.
- Spot if a tool was called with wrong arguments.
- See where the agent decided "enough" — and disagree.
- Show a regulator how the decision was made.

**Without the trace, you have an answer. With the trace, you have a defensible decision.** Hour 11 builds the trace as a first-class output. Hour 12 turns it into an evaluation artefact.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. Token economy

A practical observation. The context above is ~1500 tokens. The model's reply is ~300 tokens. That's the cost.

If you naively assembled context (stuff everything), you'd be at ~10000 tokens — 7x more expensive per call, and slower. Across an agent loop with 3-4 LLM calls, the difference adds up.

The Gen 3 platform's token economy is the platform's *unit economics*. Context engineering directly determines them. Three practical heuristics:

1. **Anchor first, then expand.** Identify the anchor node, pull only the minimum context around it.
2. **Tool outputs over raw documents.** A `sanctions_check` result is 1 line; the equivalent OFAC list chunk is 100 lines.
3. **Reuse, don't recompute.** Cache tool outputs by (tool, args) within a session.

Hour 12 measures this directly.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 10

Three questions:

1. **In the context graph above, what is the smallest fact that, if removed, would change the answer?** Identify it. That's the *load-bearing* fact; the rest could be cut.
2. **What is the largest fact that, if removed, would not change the answer?** Identify it. That's the *fat* in the context; in production you'd remove it.
3. **What would you store in episodic memory across a session about Gamma Operations?** ("the UBO is John Q. Public, classified PEP-relative, sanctions concern on Atlas Wirecorp originator at 93.3%") — that's what next turn's context graph would start from for free.

Next: [Hour 10 — Hypergraphs](./hour10_hypergraphs.ipynb). The Lotus deposit, revisited as a single n-ary relation rather than a sprawl of binary edges.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour09_context_graphs.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
