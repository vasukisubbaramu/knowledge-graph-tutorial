"""Build notebooks/hour07_hybrid_retrieval.ipynb — Gen 2 → Gen 3 transition."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 7 — Hybrid retrieval and the Gen 2 → 3 seam

> *60 minutes dense, 2–3 hours to absorb. The transition hour. By the end you will have built a hybrid retriever that combines vector search, graph traversal, and tool calls — and you will see, in code, why the *next* architectural move is an agent that decides which to call.*

**Reading companion:** [`docs/hour07.md`](../docs/hour07.md).

This hour is short on theory and long on demonstration. The three retrieval modes are already familiar; what's new is *combining* them.
"""),
    ("code", """\
from kg_tutorial import config, llm, display, tools
from kg_tutorial.data import load
from kg_tutorial.graph import GraphDB
from kg_tutorial.retrieval import chunk_documents, VectorIndex, BM25Index, rrf_combine

config.verify()
bundle = load.load()
print(f"Tools available: {list(tools.REGISTRY)}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. The three retrieval modes

So far you have three ways to retrieve evidence for a question:

| Mode | What it returns | When it's the right tool |
|---|---|---|
| **Vector + BM25 + rerank** | Text chunks ranked by hybrid relevance | Similarity-shaped questions over prose |
| **Graph traversal (Cypher)** | Structured subgraphs | Multi-hop relational queries |
| **Direct tools** | Computed answers with calibrated confidence | Fuzzy match, sanctions check, lookups |

Each mode has a question shape it serves best. **The seam between Gen 2 and Gen 3 is exactly the moment when you stop asking "which retriever do I use?" and start asking "which sub-question deserves which retriever?"**

The hour's working observation is this: **even without an LLM agent, a hand-coded hybrid retriever outperforms any single mode** — because it asks each mode the shape of question it is good at and combines the results.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. The Lotus question, decomposed by hand

The Lotus question — *"Should we approve Gamma Operations GmbH?"* — decomposes into roughly five sub-questions:

| Sub-question | Best retrieval mode |
|---|---|
| Q1: Who is the UBO of the applicant? | Graph traversal |
| Q2: Is the UBO a PEP or PEP-relative? | Document search (policy) + graph (`is_pep` flag) |
| Q3: What entities does the UBO control? | Graph traversal |
| Q4: Is the deposit's originator sanctioned? | Fuzzy-match tool |
| Q5: Is the source of funds adequately supported? | Document search (SoF questionnaire) |

We will answer each by hand with the right tool, then synthesize. This is *what an agent would do*, just without the LLM driving.
"""),
    ("code", """\
# Q1 — UBO chain via the controls_chain tool
print("Q1 — UBO chain:")
r = tools.controls_chain("e_gamma_ops")
for p in r.evidence["paths"]:
    print(f"   {p['path']}")
print()

# Q2 — PEP status via entity details
print("Q2 — PEP classification of John:")
r = tools.get_entity_details("p_john_q_public")
print(f"   is_pep={r.evidence['is_pep']}, reason: {r.evidence['pep_reason']}")
print()

# Q3 — entities John controls (the cross-link test)
print("Q3 — Entities controlled by John:")
r = tools.controlled_by("p_john_q_public")
for eid in r.evidence["reached"]:
    print(f"   {eid}")
print()

# Q4 — fuzzy sanctions match (the Hour 3 Diagnostic 3 fix)
print("Q4 — Sanctions check on the deposit originator:")
r = tools.sanctions_check("ATLAS WIRECORP")
print(f"   {r.summary}")
for hit in r.evidence["hits"]:
    print(f"     - {hit['name']:>30}  score={hit['score']}")
print()

# Q5 — Source of funds via document search
print("Q5 — Source of funds evidence:")
r = tools.document_search("source of funds questionnaire for Gamma Operations deposit", k=3)
for h in r.evidence["hits"][:2]:
    print(f"   from {h['doc_title']}")
    print(f"     {h['text'][:200]}...")
"""),
    ("md", """\
**Stop and look at Q4 specifically.** Hour 3's Diagnostic 3 failed exactly here — Gen 1's similarity search couldn't surface the OFAC entry. The fuzzy-match tool returns:

- `ESCALATE: 'ATLAS WIRECORP' — best match 'ATLAS WIRE CORPORATION' (93.3%)`

A score. A threshold. A decision. **This is the answer Gen 1 couldn't produce — because Gen 1's hammer is similarity, and similarity is the wrong instrument here.**
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Hand-coded hybrid retrieval

Now let's compose the five sub-answers into one prompt and ask Claude to synthesize. The point: even without an agent, *routing each sub-question to its right retriever and concatenating the results gives a vastly better context than any single mode.*
"""),
    ("code", """\
# Gather evidence from each sub-question's right tool
q1 = tools.controls_chain("e_gamma_ops")
q2 = tools.get_entity_details("p_john_q_public")
q3 = tools.controlled_by("p_john_q_public")
q4 = tools.sanctions_check("ATLAS WIRECORP")
q5 = tools.document_search("source of funds and source of wealth requirements for PEP-relatives", k=3)

context = f\"\"\"
UBO CHAIN (controls_chain tool):
{q1.summary}
{chr(10).join('  - ' + p['path'] for p in q1.evidence['paths'])}

UBO PEP STATUS (get_entity_details tool):
{q2.summary}
  reason: {q2.evidence['pep_reason']}

UBO'S OTHER CONTROLLED ENTITIES (controlled_by tool):
{q3.summary}
  entities: {q3.evidence['reached']}

SANCTIONS CHECK (sanctions_check tool):
{q4.summary}

POLICY EVIDENCE (document_search tool):
{chr(10).join('From ' + h['doc_title'] + ':' + chr(10) + h['text'][:400] for h in q5.evidence['hits'][:2])}
\"\"\"

prompt = f\"\"\"You are a senior bank control manager.

EVIDENCE COLLECTED FROM HYBRID RETRIEVAL:
{context}

Question: Should this bank approve the account-opening application for Gamma Operations GmbH?

Write a structured recommendation. Cite tool outputs (e.g. "sanctions_check returned ESCALATE at 93%").
End with APPROVE, DECLINE, or ESCALATE.
\"\"\"
answer = llm.ask(prompt, max_tokens=800, model=config.MODEL_DEFAULT)
display.md(answer)
"""),
    ("md", """\
**Compare this answer to Gen 1's (Hour 2) and Gen 2's (Hour 6).** The differences should be sharp:

- **The sanctions match is no longer fuzzy in the answer.** It's a calibrated score with a threshold and a decision.
- **The cross-link to Atlas Wirecorp is there** (Gen 2 found it; Gen 1 missed it).
- **The PEP-relative classification is explicit** (both Gen 2 and Hybrid found it).
- **The source-of-funds gap is articulated** (all three find this).

The recommendation should be ESCALATE or DECLINE — APPROVE is wrong on multiple grounds and any answer that says APPROVE is wrong.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Why this is *not yet* Gen 3

What you just did is a hand-coded hybrid retriever. It is not yet an agent. Two things distinguish them:

1. **You chose which tool to call for which sub-question.** An agent would decide.
2. **You did not verify the result.** An agent would critique it.

Look at the hybrid answer above. There may be claims in it that are not directly supported by the evidence. There may be evidence in the context that the model did not use. **A control manager auditing the answer would want both questions answered automatically:** "are all claims grounded?" and "is all evidence considered?"

That's the role of the **critic** in an agent loop. Hour 8 introduces it.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. Temporal — the strain we are deliberately not addressing

Brief note. The Lotus case has no time element exercised in this hour. In production:

- Ownership changes (someone exits, a new UBO emerges).
- Sanctions lists update daily.
- Adverse media accrues.
- Customer behaviour shifts.

Our schema has `effective_from` and `effective_to` on control edges; Cypher does not have first-class temporal semantics for traversal "as of" a date. Real production KGs model bi-temporal facts (valid time + transaction time) and write queries that filter on both.

The research frontier is **TIE** and similar approaches: incremental updates to KG embeddings without catastrophic forgetting, so that a model trained on yesterday's KG can incorporate today's changes without re-training. We do not implement these. **Treat temporal as the one Gen 2 strain we acknowledge and defer.**
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. Tool taxonomy

The catalogue you'll see again in Hour 8 (when the LLM picks tools) and Hour 11 (when the full agent runs). Look at the descriptions; each is one sentence — the LLM picks based on these descriptions, so writing them well is part of the agent design.
"""),
    ("code", """\
print(tools.describe_tools())
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 8

Three questions:

1. **For each of the five sub-questions, was a tool the right choice — or would document search have been sufficient?** Where would Gen 1 have sufficed? Where was Gen 2 needed? Where was a calibrated tool strictly required?
2. **The hand-coded hybrid worked because you knew the decomposition.** What happens when the question is "Is there anything else we should be worried about?" — an open-ended question? That's the prompt for Hour 8.
3. **Notice the *cost* shape.** Each tool call is cheap or free (deterministic Python). The LLM call at the end is the major cost. An agent that calls tools and *only* uses the LLM for synthesis is much cheaper than an agent that uses the LLM for every step. Hour 8 weighs the tradeoff.

Next: [Hour 8 — Agentic reasoning](./hour08_agentic_reasoning.ipynb). The LLM drives the loop; you watch it decide.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour07_hybrid_retrieval.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
