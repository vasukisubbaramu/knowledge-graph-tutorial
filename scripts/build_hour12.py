"""Build notebooks/hour12_production_eval.ipynb — production, eval, governance."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 12 — Production, evaluation, governance

> *60 minutes dense, 2–3 hours to absorb. The final hour. You will build a small evaluation harness that scores each generation on the same five questions, look at the cost / latency / quality tradeoff, run a query router that picks the right generation per question, and read the explicit governance checklist a regulated platform must satisfy.*

**Reading companion:** [`docs/hour12.md`](../docs/hour12.md).
"""),
    ("code", """\
from kg_tutorial import config, llm, display, tools, agent, eval as ev
from kg_tutorial.agent import run_agent
from kg_tutorial.data import load
from kg_tutorial.retrieval import chunk_documents, VectorIndex, BM25Index, rrf_combine, rerank_with_claude
import json, time

config.verify()
bundle = load.load()
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. The eval suite

The tutorial ships with five canonical Lotus eval cases in `kg_tutorial.eval.lotus_eval_cases()`. Each has a question, a list of expected facts, and (optionally) a list of must-cite ids.
"""),
    ("code", """\
cases = ev.lotus_eval_cases()
for c in cases:
    print(f"[{c.id}] {c.question[:75]}")
    print(f"      expects {len(c.expected_facts)} facts, must cite {len(c.must_cite)} ids")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Wire each generation as an answer function

Each generation is "give me a question, get me a string answer." We build the wrappers, then score each case against each generation.
"""),
    ("code", """\
# --- Gen 1 ---
para = chunk_documents(bundle.documents, strategy="paragraph", max_chars=800)
vec = VectorIndex(name="lotus_paragraph")
if vec.count() == 0:
    vec.add(para)
bm25 = BM25Index(para)

def gen1(question):
    hyb = rrf_combine([vec.search(question, k=8), bm25.search(question, k=8)], top_k=5)
    ctx = "\\n\\n".join(f"From: {h.chunk.doc_title}\\n{h.chunk.text}" for h in hyb)
    return llm.ask(f"Context:\\n{ctx}\\n\\nQuestion: {question}\\n\\nAnswer with citations.", max_tokens=500)


# --- Gen 2 (graph-aware, but does not require Neo4j for these cases) ---
# We use the tools.controls_chain / tools.controlled_by / tools.get_entity_details
# functions directly as graph queries.
def gen2(question):
    # Heuristic: build a small structured context using graph tools when applicable
    ctx_parts = [f"Question: {question}"]
    if "chain" in question.lower() or "ubo" in question.lower() or "owns" in question.lower():
        ctx_parts.append("UBO CHAIN: " + tools.controls_chain("e_gamma_ops").summary)
        for p in tools.controls_chain("e_gamma_ops").evidence["paths"]:
            ctx_parts.append(f"  {p['path']}")
    if "control" in question.lower() or "john" in question.lower():
        ctx_parts.append("ENTITIES JOHN CONTROLS: " + str(tools.controlled_by("p_john_q_public").evidence["reached"]))
    # add policy doc baseline
    hyb = rrf_combine([vec.search(question, k=5), bm25.search(question, k=5)], top_k=3)
    ctx_parts.append("DOCS:")
    for h in hyb:
        ctx_parts.append(f"From {h.chunk.doc_title}: {h.chunk.text[:500]}")
    ctx = "\\n".join(ctx_parts)
    return llm.ask(ctx + "\\n\\nAnswer with citations.", max_tokens=500)


# --- Gen 3 ---
def gen3(question):
    state = run_agent(question, max_iterations=3)
    return state.answer
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Run the harness

This is the slow cell — about 1-3 minutes total, mostly LLM round-trips.
"""),
    ("code", """\
results = []
for case in cases:
    for gen_name, gen_fn in [("gen1", gen1), ("gen2", gen2), ("gen3", gen3)]:
        print(f"  Running {case.id} on {gen_name}...")
        r = ev.run_case(case, gen_name, gen_fn)
        results.append((case, r))
print()
print(f"Completed: {len(results)} runs")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Score each answer with LLM-as-judge
"""),
    ("code", """\
scored = []
for case, r in results:
    print(f"  Judging {case.id} :: {r.generation}...")
    judgement = ev.judge(case, r.answer)
    recall, summary = ev.summarize_judgement(judgement)
    scored.append({
        "case": case.id,
        "gen": r.generation,
        "recall": recall,
        "summary": summary,
        "elapsed_s": r.elapsed_seconds,
        "citations_found": len(r.citations_found),
        "citations_expected": len(case.must_cite),
    })
"""),
    ("code", """\
# Render the comparison table
from rich.console import Console
from rich.table import Table

console = Console()
table = Table(title="Gen 1 / 2 / 3 — same questions, same harness")
table.add_column("case")
table.add_column("gen")
table.add_column("recall")
table.add_column("citations")
table.add_column("elapsed (s)")
table.add_column("notes")
for s in scored:
    cit = f"{s['citations_found']}/{s['citations_expected']}" if s['citations_expected'] else "—"
    table.add_row(s["case"], s["gen"], f"{s['recall']:.0%}", cit, f"{s['elapsed_s']:.1f}", s["summary"])
console.print(table)
"""),
    ("md", """\
**Read the table.** Three observations to look for:

1. **Gen 1 recall is highest where the question is similarity-shaped** (the PEP policy lookup) and lowest on multi-hop/cross-link questions.
2. **Gen 3 recall is highest overall but most expensive in elapsed time.**
3. **Gen 2 sits in between** — costs less than Gen 3, recalls more than Gen 1, on the questions it was designed for.

This is the actual production decision: **which generation per query class?**
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. The router

Given a question, choose a generation. `kg_tutorial.eval.route` is a tiny LLM-based router that returns one of `gen1`, `gen2`, or `gen3` with a reason. Production routers blend LLM with deterministic rules; we use just the LLM here.
"""),
    ("code", """\
# Route each question and compare to the recall table
for case in cases:
    r = ev.route(case.question)
    actual_best = max(
        (s for s in scored if s["case"] == case.id),
        key=lambda x: (x["recall"], -x["elapsed_s"]),
    )
    agreed = "OK" if r["stack"] == actual_best["gen"] else "MISMATCH"
    print(f"  [{case.id}]  router -> {r['stack']}; best by recall -> {actual_best['gen']}  ({agreed})")
    print(f"     router reason: {r['reason'][:120]}")
"""),
    ("md", """\
The router may agree with the recall-based "best" choice, or not. Where it doesn't, look at the question — was it ambiguous? The fix is usually a more explicit router prompt or deterministic rules layered on top.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. Cost and latency math

The numbers in the table are real. Multiplied out, here's what running this platform looks like in production:

| Generation | Avg call cost | Avg latency | Cases/day @ 200 alerts | Daily \\$ |
|---|---|---|---|---|
| Gen 1 | ~\\$0.005 | ~1-2 s | 200 | \\$1 |
| Gen 2 | ~\\$0.015 | ~3-5 s | 200 | \\$3 |
| Gen 3 | ~\\$0.20 | ~30-60 s | 200 | \\$40 |

Hybrid via routing: maybe \\$15-25/day depending on the mix. The honest answer to "which generation should we deploy?" is **all three, with a router** — and the router is the platform's unit-economics dial.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. The governance checklist

A control-management platform is regulated. Every architectural choice has a governance consequence. The checklist a regulator would expect:

1. **Explainability.** Every recommendation has a reasoning trace and citations to specific evidence.
2. **Reproducibility.** Re-running the same query against the same data produces the same answer (within tolerance — deterministic where possible, version-pinned where not).
3. **Audit trail.** The trace + evidence + final answer are retained for the regulatory retention period.
4. **Model governance.** Every model in the stack (LLM, embedding, fuzzy matcher) has a version, a validation report, and a fallback when the API is down.
5. **Data lineage.** Each fact in the graph cites its source document/registry/feed.
6. **HITL gates.** No automated decisions in the highest-risk categories — those flow to a human reviewer.
7. **Bias monitoring.** Regular tests for differential behaviour across jurisdictions / customer segments.
8. **Sanctions / regulatory list freshness.** Lists must be refreshed daily; the platform must verify and alarm if not.
9. **Tool failure handling.** When a tool returns an error, the agent retries with a bounded number of attempts, then escalates rather than silently using fewer facts.
10. **Cost guardrails.** Hard caps on tokens, tool calls, and runtime per case.

Re-read this list once. Then look at the architectural choices made in Hours 4-11. Each item maps to a specific choice somewhere.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 8. Frontier — KumoRFM and "Gen 4"

A final signpost. Throughout this tutorial we've assumed the architectural unit is the *query → retrieve → answer* pipeline. The implicit progression has been: better retrieval (Gen 1), then better structure (Gen 2), then better orchestration (Gen 3).

**KumoRFM** (Fey et al. 2025) proposes a different architectural unit: a relational foundation model that does in-context learning over multi-table relational data *directly*, without a per-task retrieval pipeline. The model is the retriever and the reasoner.

For enterprise data — which is overwhelmingly relational (CDD tables, transaction tables, sanctions tables, account tables) — this collapses the Gen 1/2/3 distinction into "one model, one query, one answer." Production deployment is years out for high-stakes domains like control management, but the direction is clear.

This is **Gen 4** if you like the framing — and the framing is fine, as long as you remember the framing is for clarity, not for marketing. The principles you learned in Hours 1-12 transfer: failure modes are still relational, similarity, and verification; the engineering effort is still mostly entity resolution and provenance; the governance burden is still highest where stakes are highest.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 9. What to take away from twelve hours

You came in believing — because that's what marketing said — that Gen 3 strictly dominates Gen 2 strictly dominates Gen 1. You leave understanding that:

- Each generation has a query shape it's best at.
- A serious production platform routes between them.
- The architectural moves that matter most are: graph structure where relations matter, tools where calibrated answers matter, agents where verification matters.
- The remaining engineering effort — most of it — is data lineage, entity resolution, prompt and context engineering, evaluation, and governance.
- The frontier is foundation models that subsume retrieval, but the principles you learned still hold.

You built the same Lotus case three ways. You watched Gen 1 miss the cross-link by construction. You watched Gen 2 find the cross-link but fumble the sanctions alias. You watched Gen 3 catch both with a defensible audit trail. **Hold those three answers in your head when somebody on your team asks "which architecture should we use?"**

The answer is now obvious: it depends — and you have a framework for deciding.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Where to go next

- **Build something small in production.** Pick a query class, a small corpus, and stand up a single-generation pipeline end-to-end. Add the second generation when the first hits its ceiling.
- **Read the frontier papers** (in `references/`) once more: ULTRA / GAMMA for inductive KG reasoning, TIE for temporal KGs, KumoRFM for relational foundation models. They'll read fluently now.
- **Operate the platform.** The hardest thing is not building it; it is keeping the evaluation harness honest as the data and the queries drift.

That's the tutorial. Twelve hours. Read the [README](../README.md) for what's next — and the next-next.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour12_production_eval.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
