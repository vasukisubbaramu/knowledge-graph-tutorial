# Hour 12 — Production, evaluation, governance

A reading companion to `notebooks/hour12_production_eval.ipynb`.

> **One-line frame for the hour.** *A serious platform routes between generations; an even-more-serious one measures the routing and improves it continuously. The honest answer to "which generation?" is "depends — and here's the harness that tells you."*

## 1. The eval harness, minimum viable

The harness in this hour is a small fixture:

- A set of canonical Lotus questions (5 cases), each with expected facts and must-cite ids.
- Each generation as an "answer function" — `gen1(q) -> str`, `gen2(q) -> str`, `gen3(q) -> str`.
- A loop that runs every case through every generation, scored by an LLM-as-judge against the expected facts.

This is the *educational floor* of evaluation. Production eval is a system in its own right (RAGAS, Trulens, custom harnesses). The architectural shape is the same.

The metrics produced:

- **Recall**: what fraction of expected facts the answer expressed.
- **Citation precision**: of the must-cite ids, how many actually appear in the answer.
- **Latency**: wall-clock per case.
- **Cost**: API spend per case (approximate, derived from token counts).

These are the dimensions a control manager actually cares about. A high-recall answer that takes 60 seconds and costs a dollar is *not* better than a 90% recall answer that takes 2 seconds and costs a penny — for the same query class.

## 2. Reading the cross-generation table

The hour produces a matrix: 5 cases × 3 generations = 15 cells. Read it for three things:

1. **Where Gen 1 wins.** The PEP policy lookup. Similarity-shaped questions over prose are Gen 1's territory; nothing later was meant to replace it.
2. **Where Gen 2 wins.** Multi-hop chain questions, set-aggregation across entities. Gen 2 is the cheapest tool that does these correctly.
3. **Where Gen 3 wins.** Sanctions match with calibrated score, the full open-ended Lotus question. Gen 3 is the only mode that can do these with audit-grade output.

The matrix is not "Gen 3 dominates" or "Gen 1 dominates." It's the production routing argument made explicit.

## 3. The router

A query router picks the generation per question. Two implementations are common:

- **LLM-based**: a fast model classifies the question. Flexible, picks well on novel queries, but adds 100-500ms and a few cents per question.
- **Rule-based**: regex / keyword / classifier rules. Fast, free, brittle on novel queries.

Production usually layers both: deterministic rules catch the obvious cases ("if the question mentions 'policy', route to Gen 1"); the LLM handles the rest.

The hour shows a pure-LLM router for clarity. In production you'd layer:

```
question
  ├── deterministic rules (cheap, fast, catch the obvious)
  │     ├── "what is our policy on X?" → gen1
  │     ├── "list every X that controls Y" → gen2
  │     └── "should we approve / escalate / decline X?" → gen3
  └── LLM classifier (for everything else)
```

The router is the platform's **unit-economics dial**. A router that sends too much to Gen 3 is over-spending; one that sends too much to Gen 1 is under-serving. Hour 12's eval harness gives you the ground truth to tune against.

## 4. Cost math, made explicit

Approximate per-call costs:

| Mode | Avg cost | Avg latency |
|---|---|---|
| Gen 1 | ~$0.005 | ~1-2 s |
| Gen 2 | ~$0.015 | ~3-5 s |
| Gen 3 | ~$0.20 | ~30-60 s |

For a desk handling 200 cases/day:

| Routing strategy | Daily cost |
|---|---|
| All Gen 1 (bad answers on hard cases) | ~$1 |
| All Gen 2 (no calibrated sanctions) | ~$3 |
| All Gen 3 (over-served on easy cases) | ~$40 |
| Routed (60/30/10 split, indicative) | ~$15 |

The routed cost is meaningfully lower than all-Gen 3 *and produces better answers* — because each query gets the mode best for its shape, and Gen 3 is reserved for cases that earn it.

This is the unit-economics argument. The router is what makes Gen 3 affordable at the bank's scale.

## 5. The governance checklist

A control-management platform is regulated. Ten items a regulator would expect:

1. **Explainability.** Every recommendation has a reasoning trace and citations to specific evidence.
2. **Reproducibility.** Re-running the same query against the same data produces the same answer (within tolerance).
3. **Audit trail.** Trace + evidence + final answer retained per the regulatory retention period.
4. **Model governance.** Every model (LLM, embedding, fuzzy matcher) has a version, a validation report, a fallback.
5. **Data lineage.** Each fact in the graph cites its source — document, registry, feed, manual override.
6. **HITL gates.** No automated decisions in the highest-risk categories.
7. **Bias monitoring.** Regular tests for differential behaviour across jurisdictions and customer segments.
8. **Sanctions / list freshness.** Lists refreshed daily, with verification and alarms.
9. **Tool failure handling.** Errors bounded, retried, escalated — not silently swallowed.
10. **Cost guardrails.** Hard caps on tokens, tool calls, and runtime per case.

Each item maps to an architectural choice somewhere in Hours 4-11. Re-read the list; trace each item to a specific design decision.

## 6. The honest answer to "which generation?"

You came in with a framing: Gen 3 > Gen 2 > Gen 1.

You leave with a different framing: **each generation is the best tool for a class of queries; production routes between them; the router is a first-class engineering artefact.**

The marketing pitch is a story; the architecture is the routing. The routing is informed by the eval harness; the harness is informed by your platform's actual question mix; the question mix is informed by what your control managers actually do all day.

That virtuous cycle — observe → measure → route → re-observe — is the operational reality of running the platform. It is not a one-time architectural decision; it is a continuous practice.

## 7. The frontier — KumoRFM and "Gen 4"

Throughout the tutorial we've assumed the architectural unit is the *query → retrieve → answer* pipeline. The implicit progression has been: better retrieval (Gen 1), better structure (Gen 2), better orchestration (Gen 3).

**KumoRFM** (Fey et al. 2025) proposes a different architectural unit: a foundation model that does in-context learning over multi-table relational data *directly*, without a per-task retrieval pipeline. The model is the retriever and the reasoner.

For enterprise data — overwhelmingly relational (CDD tables, transaction tables, sanctions tables, account tables) — this collapses Gen 1/2/3 into "one model, one query, one answer." Production deployment is years out for high-stakes domains like control management, but the direction is clear.

Whether you call this Gen 4 is a marketing question. The substantive question is: what changes for you when the architectural unit shifts? The answer is much the same as it was at the start of this tutorial: the failure modes are still *relational, similarity, and verification*; the engineering effort is still mostly entity resolution and provenance; the governance burden is still highest where stakes are highest. The principles transfer.

## 8. What to take away from Hour 12

- A working eval harness comparing all three generations on the same questions.
- The cost / latency / quality tradeoff made numerical.
- A query router and a clear case for why routing is the platform's unit-economics dial.
- The ten-item governance checklist and its mapping to architectural choices.
- An honest, durable answer to "which generation?" — *it depends, here's how to find out, and here's how to keep finding out as the platform changes*.

## 9. What to take away from twelve hours

You came in believing Gen 3 strictly dominates Gen 2 strictly dominates Gen 1. You leave understanding:

- Each generation has a query shape it's best at.
- A serious production platform routes between them.
- The architectural moves that matter most are *graph structure where relations matter, tools where calibrated answers matter, agents where verification matters.*
- The remaining engineering effort — most of it — is data lineage, entity resolution, prompt and context engineering, evaluation, and governance.
- The frontier is foundation models that subsume retrieval, but the principles you learned still hold.

You built the same Lotus case three ways. You watched Gen 1 miss the cross-link by construction. You watched Gen 2 find the cross-link but fumble the sanctions alias. You watched Gen 3 catch both with a defensible audit trail.

Hold those three answers in your head when somebody on your team asks "which architecture should we use?"

The answer is now obvious: **it depends — and you have a framework for deciding.**
