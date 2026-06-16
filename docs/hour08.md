# Hour 8 — Gen 3: Agentic reasoning

A reading companion to `notebooks/hour08_agentic_reasoning.ipynb`.

> **One-line frame for the hour.** *An agent is a small state machine over an LLM, where the LLM is in the planning seat, a critic verifies, and state persists across iterations. Everything else — ReAct, Self-RAG, CRAG, Reflexion — is a name for a configuration of that machine.*

## 1. The shape of an agent

The standard agent loop:

```
PLAN → EXECUTE → CRITIQUE → (loop) → FINALIZE
```

- **Plan** — the LLM, given the question and the evidence so far, decides what to do next.
- **Execute** — tool calls run, results are captured.
- **Critique** — the LLM, given the evidence, decides whether it is sufficient.
- **Loop** — if insufficient, return to plan with the critic's feedback.
- **Finalize** — synthesize the answer.

Three things distinguish this from a chain of LLM calls:

1. The LLM picks the next action; you don't.
2. A critic verifies before finalizing; the answer is grounded by construction.
3. State persists across iterations; later turns build on earlier evidence.

**This is the architectural primitive of Gen 3.** Variations on it have specific names; the structure is the same.

## 2. LangGraph as the framework

We use LangGraph because it makes the state machine *visible*. The state is a dataclass; each node is a function on that state; the graph wires them. You can:

- Inspect the state at any node.
- Trace which node ran when.
- Pause and resume from any state.
- Add nodes (a new specialist, a sub-loop) without rewriting the rest.

For tutorial-scale agents you could write the loop by hand in ~50 lines of Python. For production-scale agents (with conditional routing, sub-graphs, parallelism, retries, observability), a framework like LangGraph pays for itself quickly.

## 3. ReAct, Self-RAG, CRAG, Reflexion — same machine, different configurations

The four canonical agentic-RAG patterns map onto the loop above:

- **ReAct** (Yao et al. 2022) — interleave reasoning steps and tool calls. The plan-execute alternation is ReAct.
- **Self-RAG** (Asai et al. 2023) — the model decides when to retrieve and grades its own output. The planner deciding tool calls is the "decide when to retrieve" half; the critic is the "grade your output" half.
- **CRAG** (Yan et al. 2024) — Corrective RAG: a lightweight evaluator decides whether to retry retrieval. The critic-to-plan transition is exactly this.
- **Reflexion** (Shinn et al. 2023) — a critic reads the trace and proposes a revised plan. Our critic-feedback-to-planner is a simple Reflexion.

You did not pick one pattern. You built a loop where each is one node. That generalises — the modern Gen 3 agent is the configuration of plan-execute-critique-finalize, where each node is tuned to the task.

## 4. Tools as the agent's competence boundary

The agent can only do what its tools can do. The tool catalogue *is* the agent's competence.

This is liberating and constraining. Liberating: adding a new tool is the right way to extend the agent's reach. Constraining: a missing tool means a missing competence, and a poorly-described tool means a *misused* competence.

Three practical rules:

1. **Each tool description is a one-sentence answer to "when should the agent reach for this?"** That sentence is what the LLM sees.
2. **Each tool returns a typed result.** The agent decides what to do next based on what came back; the result must be machine-readable.
3. **Each tool's confidence is calibrated.** A deterministic tool (`get_entity_details`) returns 1.0; a fuzzy/similarity tool returns < 1.0. The critic uses confidence to grade.

The `kg_tutorial.tools.REGISTRY` is the catalogue. Read each entry; read the descriptions you'd want the agent to act on.

## 5. The two characteristic failures

**Looping.** The agent gets stuck calling the same tools because the critic isn't satisfied. Mitigated by:

- `max_iterations` (hard cap).
- A critic prompt that grades on *what's missing*, not "more please."
- A planner prompt that, given prior evidence, doesn't repeat itself.

In production, hard caps go further: total token budget, total wall-clock budget, total tool-call budget.

**Wrong tool, confident answer.** The agent picks a tool that returns *something*, treats it as the answer, the critic approves. The fix is at three layers:

- Tool descriptions: write them precisely. Ambiguity in the description causes ambiguity in selection.
- Critic prompt: "is this *the right* tool for this sub-question?" not just "is the answer present?"
- Catalogue completeness: if no tool can answer the question, the agent should say so. Hour 8 explicitly tests this.

## 6. What we did not implement

Three things production agents do that we did not:

- **Parallel tool calls.** Multiple tools can run concurrently; LangGraph supports this. We serialise for simplicity.
- **Tool retries with exponential backoff.** Network calls fail; production wraps each tool in retry logic.
- **Conversation memory across turns.** Our agent is single-turn. A control-manager agent in production is multi-turn — episodic memory across the session, semantic memory across sessions.

Hour 11 adds reasoning trace and audit log; multi-turn dialog is left as an extension.

## 7. The economics

A naive observation: an agent makes more LLM calls than a single-shot pipeline. The cost shape is:

- Planner call(s) — one per loop iteration. ~$0.005 on Sonnet per call.
- Tool calls — mostly free (deterministic Python). Sanctions check, controls chain, fuzzy match are all microseconds.
- Critic call(s) — one per loop iteration.
- Finalize call — one, on Opus for quality.

For the Lotus question: ~4 Sonnet calls + 1 Opus call ≈ $0.15-0.40 per question.

For a control manager reviewing 200 alerts a day at that price, you'd spend $30-80/day, end to end. That is more than Gen 1's $1/day but it is *not* expensive for the volume of work it replaces — a control manager's hourly cost is many times this.

The decision is not "is Gen 3 affordable?" The decision is "which queries earn Gen 3's cost, and which would be over-served by it?" That's the router; that's Hour 12.

## 8. What to take away from Hour 8

- The plan-execute-critique-finalize loop as the structural primitive of Gen 3.
- LangGraph as a way to make state-machine agents *inspectable*.
- The four canonical patterns (ReAct / Self-RAG / CRAG / Reflexion) as configurations of the loop.
- The two characteristic agent failures and the mitigation patterns for each.
- A working agent that answers the Lotus question with citations and a reasoning trace.
