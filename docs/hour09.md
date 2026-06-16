# Hour 9 — Gen 3: Context Graphs

A reading companion to `notebooks/hour09_context_graphs.ipynb`.

> **One-line frame for the hour.** *The discipline replacing "prompt engineering" is **context engineering** — the deliberate assembly of the input the LLM reasons over, drawn from KGs, document retrievers, tool outputs, and prior dialog, with sources and structure that make the answer auditable.*

## 1. Why "knowledge graph" and "context graph" are different

A knowledge graph is the long-lived store: schema-bound, queryable, large, persistent.

A context graph is the transient, query-specific structured input you build for the LLM at inference time. It is constructed *fresh per query* and discarded after the answer is produced (or cached if the query repeats).

A context graph typically contains:

- A *slice* of the KG (relevant nodes, edges, properties).
- A *handful* of unstructured chunks the retrievers brought back.
- *Outputs* of tool calls (sanctions scores, fuzzy matches, adverse-media hits).
- *Prior dialog turns* (for conversational agents).
- *Explicit constraints* (policy thresholds, output format, citation requirements).

A context graph is not a graph database. It is a structured assembly that gives the LLM exactly the right shape and content for the question it must answer.

## 2. Context engineering as a discipline

Prompt engineering was about phrasing the *instruction*. Context engineering is about *assembling the input* — what evidence to include, in what order, with what structure, from which sources, with which provenance.

The shift happened around 2024 when instruction-tuned models became capable enough that marginal wording changes plateaued in value. The marginal gain from better-curated input did not plateau. By 2026 every serious LLM platform has more engineering investment in context assembly than in prompt phrasing.

What context engineering produces (when done well):

- **Smaller contexts.** A context-engineered prompt is 1-3k tokens; a naive "stuff everything" prompt is 10-30k tokens.
- **Higher precision.** Every fact relevant to the answer is present; nothing irrelevant is present.
- **Auditable citations.** Every claim in the answer points to a source in the context.

What it requires:

- An anchor identifier — what entity is this question about?
- A subgraph fetch from the KG around the anchor (1-3 hops).
- Selective document retrieval, scoped to the question.
- Tool outputs in lieu of raw documents where calibrated answers exist.
- Explicit constraints and output format.

## 3. The three memory types

Sessions that span multiple questions over the same case need more than working memory. Three types in play:

| Memory | What it holds | Lifetime | Where it lives |
|---|---|---|---|
| **Working** | The current question, evidence collected this turn, critic feedback | One turn | The agent state |
| **Episodic** | Prior turns of the current session — what was asked, what was concluded | One session | A session-scoped store (Redis / Postgres / a simple dict) |
| **Semantic** | What was learned that's worth keeping across sessions | Indefinite | A persistent store (vector DB / KG / file) |

For a control-manager platform, episodic memory is critical: a manager working a case across an afternoon asks several questions about the same customer. The platform should not re-derive the UBO chain on every question. Semantic memory captures domain facts and user preferences ("this manager always wants a regulatory citation").

Hour 9 focuses on working memory — the context built for one turn. Hour 11 adds episodic via the agent state and audit log.

## 4. The token economy

A practical observation. The Hour 9 example builds a ~1500-token context graph; the naive equivalent is ~10000 tokens. For one query the difference is small. Across an agent loop with 3-4 LLM calls and 200 cases/day, the difference is *the platform's unit economics*.

Three heuristics for keeping the context tight:

1. **Anchor first, then expand.** Identify the entity the question is about; pull only the minimum context around it.
2. **Tool outputs over raw documents.** `sanctions_check` returns 1 line; the equivalent OFAC list chunk is 100 lines. Calibrated tool output > unstructured prose.
3. **Reuse, don't recompute.** Cache tool outputs by (tool, args) within a session. The agent calling `get_entity_details("p_john_q_public")` twice in one session should pay the cost once.

## 5. Trace as memory

The agent's reasoning trace — the list of plan, execute, critique, finalize events — is itself a form of working memory. It records:

- What the agent did.
- In what order.
- With what arguments.
- What each step concluded.

This trace is **the audit log** the control-management platform owes regulators. Without it you have an answer; with it you have a defensible decision. Hour 11 makes the trace a first-class output.

Worth noting: in agentic systems the trace is also the *debugging primitive*. When the agent answers wrong, the trace shows where it went wrong — wrong tool, wrong argument, wrong critic verdict, premature finalize. Without the trace, you debug by re-running.

## 6. The three-line summary

Context engineering. Three points to internalize:

- Build the context *fresh per question* from KG slices + tool outputs + selective chunks + constraints.
- Keep it *tight* — anchor first, tool outputs over docs, reuse aggressively.
- Make it *auditable* — every fact has a source; the trace is exportable.

## 7. What to take away from Hour 9

- The conceptual distinction between knowledge graph (storage) and context graph (input).
- The discipline name — context engineering — and what it produces vs prompt engineering.
- The three memory types, especially how episodic memory accelerates multi-turn sessions.
- A worked example of building a tight, audit-ready context graph for one Lotus sub-question.
- The token-economy heuristics that determine your platform's unit economics.
