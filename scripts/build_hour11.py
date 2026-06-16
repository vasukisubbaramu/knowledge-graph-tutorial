"""Build notebooks/hour11_control_manager_agent.ipynb — Gen 3 capstone."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 11 — End-to-end Control Manager agent

> *60 minutes dense, 2–3 hours to absorb. The capstone. You run the full agent on the Lotus case, produce a structured recommendation with reasoning trace and citations, and place every output of Hours 2-10 side-by-side. The hour is mostly running and looking.*

**Reading companion:** [`docs/hour11.md`](../docs/hour11.md).
"""),
    ("code", """\
from kg_tutorial import config, llm, display, tools, agent
from kg_tutorial.agent import run_agent
from kg_tutorial.data import load
import json

config.verify()
bundle = load.load()
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. The full Lotus answer, Gen 3

We re-run the agent on the canonical Lotus question with the full tool registry and the higher iteration budget. **Cost expectation: ~$0.15-0.40 on Sonnet for the loop + one Opus call for finalize.** Latency ~30-60 seconds.
"""),
    ("code", """\
LOTUS_Q = "Should this bank approve the account-opening application for Gamma Operations GmbH (LI)?"
final_state = run_agent(LOTUS_Q, max_iterations=4)
"""),
    ("code", """\
print("=" * 80)
print("REASONING TRACE")
print("=" * 80)
for line in final_state.trace:
    print(line)
"""),
    ("code", """\
print("=" * 80)
print("EVIDENCE COLLECTED")
print("=" * 80)
for i, e in enumerate(final_state.evidence, 1):
    print(f"\\n[{i}] tool: {e['tool']}({e['args']})")
    print(f"    summary: {e['summary']}")
    print(f"    confidence: {e['confidence']}")
"""),
    ("code", """\
print("=" * 80)
print("FINAL ANSWER (JSON)")
print("=" * 80)
display.md("```json\\n" + final_state.answer + "\\n```")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Grade the final answer

Use this template to grade the answer against the seven-point Hour 2 checklist:

| # | Criterion | Pass / Fail / Partial |
|---|---|---|
| 1 | Full ownership chain (KY → PA → LI)? | |
| 2 | UBO classified as PEP-relative (nephew rule)? | |
| 3 | Cross-link: John directs Atlas Wirecorp? | |
| 4 | Sanctions match for Atlas Wirecorp with calibrated score? | |
| 5 | Source-of-funds gap (no supporting invoice)? | |
| 6 | Adverse media linkage? | |
| 7 | Recommendation: ESCALATE / DECLINE (not APPROVE)? | |

Then grade Gen 3 against Gen 1 (Hour 2) and Gen 2 (Hour 6) on:

- **Coverage** — how many criteria were touched?
- **Citation quality** — did each claim cite a specific source (tool output / document)?
- **Calibration** — did the model express uncertainty where appropriate?
- **Defensibility** — could a control manager hand this answer to a regulator?
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. The audit trail

Production control platforms need the agent's reasoning to be *audited*. Three things must be exportable from a single run:

1. **The trace** — what nodes ran in what order.
2. **The evidence** — every tool call, its arguments, its result.
3. **The decision rationale** — the final synthesis with explicit links to evidence.

We have all three from this run. Bundle them as a single audit object:
"""),
    ("code", """\
audit_record = {
    "question": LOTUS_Q,
    "trace": final_state.trace,
    "evidence": [
        {"tool": e["tool"], "args": e["args"], "summary": e["summary"], "confidence": e["confidence"]}
        for e in final_state.evidence
    ],
    "final_answer": json.loads(final_state.answer) if final_state.answer else None,
    "iterations": final_state.iterations,
}

# Save it - a real platform would write to a tamper-evident audit log
print(json.dumps(audit_record, indent=2, default=str)[:3500])
print("..." if len(json.dumps(audit_record, default=str)) > 3500 else "")
"""),
    ("md", """\
**This is the structure regulators audit.** If the bank's decision is challenged six months later, the audit record reproduces:

- *What* the agent considered.
- *Which* tools it called and what they returned.
- *Why* the agent decided "sufficient" at the iteration it did.
- *What* the final recommendation cited.

Without this structure, the decision is opaque. With it, the platform is defensible.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Side-by-side: Gen 1 vs Gen 2 vs Gen 3

We have, by now, three Lotus answers. The hour's most important exercise: place them next to each other and read all three.
"""),
    ("code", """\
# Quick Gen 1 (Hour 2 recipe)
from kg_tutorial.retrieval import chunk_documents, VectorIndex, BM25Index, rrf_combine, rerank_with_claude

para = chunk_documents(bundle.documents, strategy="paragraph", max_chars=800)
vec = VectorIndex(name="lotus_paragraph")
if vec.count() == 0:
    vec.add(para)
bm25 = BM25Index(para)

hyb = rrf_combine([vec.search(LOTUS_Q, k=10), bm25.search(LOTUS_Q, k=10)], top_k=8)
top = rerank_with_claude(LOTUS_Q, hyb, top_n=5)
ctx = "\\n\\n".join(f"From: {h.chunk.doc_title}\\n{h.chunk.text}" for h in top)
gen1_prompt = f"You are a control manager.\\n\\nContext:\\n{ctx}\\n\\n{LOTUS_Q}\\n\\nEnd with APPROVE / DECLINE / ESCALATE."
gen1_answer = llm.ask(gen1_prompt, max_tokens=500)
"""),
    ("code", """\
# Gen 2 (Hour 6 recipe) - requires Neo4j; if unavailable, set gen2_answer = "(skipped - Neo4j not available)"
try:
    from kg_tutorial.graph import GraphDB, neo4j_subgraph_to_text
    db = GraphDB()
    rows = db.subgraph_around("e_gamma_ops", depth=3) + db.subgraph_around("dep_001", depth=2)
    graph_ctx = neo4j_subgraph_to_text(rows)
    db.close()
    gen2_prompt = f\"\"\"You are a control manager.

KG context:
{graph_ctx}

Policy chunks:
{ctx}

{LOTUS_Q}
End with APPROVE / DECLINE / ESCALATE.\"\"\"
    gen2_answer = llm.ask(gen2_prompt, max_tokens=500)
except Exception as e:
    gen2_answer = f"(Gen 2 skipped — Neo4j unavailable: {e})"
"""),
    ("code", """\
gen3_answer_obj = json.loads(final_state.answer) if final_state.answer else {}
gen3_answer = json.dumps(gen3_answer_obj, indent=2)[:1500]

print("=" * 80)
print("GEN 1 ANSWER")
print("=" * 80)
display.md(gen1_answer)
print()
print("=" * 80)
print("GEN 2 ANSWER")
print("=" * 80)
display.md(gen2_answer)
print()
print("=" * 80)
print("GEN 3 ANSWER (JSON, abbreviated)")
print("=" * 80)
display.md("```json\\n" + gen3_answer + "\\n```")
"""),
    ("md", """\
**Read all three.** Note for each:

- Did the answer reach ESCALATE or DECLINE? (APPROVE is wrong.)
- Did the answer surface the cross-link to Atlas Wirecorp?
- Did the answer give a calibrated sanctions assessment?
- How auditable is each — could you trace any claim back to a source?

Gen 1 should reliably catch some elements (the policy lookup) and miss the cross-link.
Gen 2 should catch the cross-link cleanly but produce a softer sanctions assessment.
Gen 3 should catch everything *with* the structured output that makes auditing trivial.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. Human-in-the-loop hand-off

The agent's `open_questions` field is where it surfaces what it could not verify. In production, those questions route to a human control manager — the agent stops, the human picks up.

Three things the agent should *always* hand off:

1. **Fuzzy matches in the review zone** (70-85% — the "you decide" band).
2. **Adverse media that's substantive but unclear** (negative-sentiment article on the UBO from a credible outlet, but no formal regulatory finding).
3. **Source-of-wealth questions** for PEPs/PEP-relatives — these are policy-mandatory and rarely cleanly answerable from documents alone.

Inspect what your run's agent flagged:
"""),
    ("code", """\
final_obj = json.loads(final_state.answer) if final_state.answer else {}
open_qs = final_obj.get("open_questions", [])
print(f"Open questions for human review: {len(open_qs)}")
for q in open_qs:
    print(f"  - {q}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 12

Three questions:

1. **For the Gen 3 answer, what's the single most expensive tool call you observed?** Removing it — would the answer still be correct, or would it lose a critical fact? That's the routing decision.
2. **The agent took N iterations.** Was N too many? Too few? Would Gen 3 be *cheaper* than Gen 1 in the cases where Gen 1 is the right tool?
3. **What goes wrong if a tool is *wrong*?** Imagine the sanctions list is stale — Atlas isn't on it yet. The agent's calibrated answer is now confidently wrong. How would you detect this in production?

Next: [Hour 12 — Production, eval, governance](./hour12_production_eval.ipynb). The final hour. Evaluation, routing, cost, the honest answer to "which generation?"
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour11_control_manager_agent.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
