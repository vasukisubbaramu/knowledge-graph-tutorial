"""Build notebooks/hour08_agentic_reasoning.ipynb — Gen 3 agent loop hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 8 — Gen 3: Agentic reasoning

> *60 minutes dense, 2–3 hours to absorb. The first proper Gen 3 hour. You build a LangGraph agent with a plan → execute → critique → finalize loop, watch it answer the Lotus questions, and inspect the reasoning trace. Then you make it fail in the two characteristic ways agents fail.*

**Reading companion:** [`docs/hour08.md`](../docs/hour08.md).

**Prerequisite:** `pip install langgraph langchain-anthropic langchain-core` (covered by the README install command).
"""),
    ("code", """\
from kg_tutorial import config, llm, display, tools, agent
from kg_tutorial.agent import AgentState, run_agent

config.verify()
print(f"Agent assembled from: {list(tools.REGISTRY)}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. What an agent actually is

Strip away the marketing and an agent is a small state machine over an LLM:

```
START
  │
  ▼
PLAN ──> decide what tools to call next
  │
  ▼
EXECUTE ──> call them, collect results
  │
  ▼
CRITIQUE ──> "is what we have enough to answer the question?"
  │
  ├── no  ──> PLAN (with the critique as feedback)
  │
  └── yes ──> FINALIZE ──> synthesize the answer
                              │
                              ▼
                            END
```

Three things make this an agent and not just a sequence of LLM calls:

1. **The LLM is in the planning seat.** It decides which tool to call, not the developer.
2. **There is a critic.** Output is graded against the question; insufficient output triggers another loop.
3. **State persists across the loop.** Evidence collected in iteration 1 informs the plan in iteration 2.

LangGraph's job is to make this explicit. The state is a dataclass; transitions are functions on the state; the framework wires them into a graph and runs it. The agent state is in `kg_tutorial.agent.AgentState`.
"""),
    ("code", """\
# Inspect the state we built around
import inspect
print(inspect.getsource(AgentState))
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. The four nodes of the loop

The agent has four named transitions, each a small function on `AgentState`.

- `plan_step` — calls Claude with the question, the tool catalogue, the evidence so far, and the critic's feedback. Returns a list of tool calls.
- `execute_step` — runs each tool call, attaches the result to `state.evidence`.
- `critique_step` — calls Claude with the evidence and the question, decides if it's sufficient.
- `finalize_step` — calls Claude (Opus) to produce a structured JSON answer.

The loop is plan → execute → critique → (loop if not enough; finalize if enough); a hard cap of `max_iterations=4` prevents runaway loops.
"""),
    ("code", """\
# Look at the planner prompt — this is the centre of agent design
print(agent.PLANNER_PROMPT[:1200])
"""),
    ("md", """\
**The prompt is the API.** What the agent can and cannot do is determined by the prompt + the tool descriptions. The Hour 11 agent has the same loop structure with a richer prompt and more specialised tools.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Run the agent on a simple question first

A warmup. Easy question, the agent should call one tool and finish.
"""),
    ("code", """\
# WARMUP: simple question
state = run_agent("Is John Q. Public a PEP? Cite the reason.", max_iterations=2)
print("=== TRACE ===")
for line in state.trace:
    print(line)
print()
print("=== ANSWER ===")
display.md(state.answer)
"""),
    ("md", """\
Look at the trace. You should see one plan → execute → critique pass, then finalize. The plan should have called `get_entity_details` for John, the critic should have judged that sufficient, and the finalizer should have produced a 1-2 sentence answer with the PEP reason.

This is what an agent loop looks like *when it works*.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Run on a medium question

The cross-link question — Hour 3's Diagnostic 2. Gen 1 missed this entirely.
"""),
    ("code", """\
state = run_agent("List every entity that John Q. Public controls directly or indirectly.")
print("=== TRACE ===")
for line in state.trace:
    print(line)
print()
print("=== ANSWER ===")
display.md(state.answer)
"""),
    ("md", """\
**The agent should:**

1. Plan one call to `controlled_by(person_id="p_john_q_public")`.
2. Get back four entities including Atlas Wirecorp.
3. Critic judges sufficient.
4. Finalize lists all four.

If you see the agent making *additional* tool calls — say, `get_entity_details` on each entity — it's because the planner decided it wanted more context. That's not wrong; it's a *cost decision*. A production agent has explicit budget guards (no more than N tool calls per question).
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. Run on the Lotus question

The big one. ~3-4 tool calls expected. Cost ~$0.10 on Sonnet for plan/critique + one Opus call for finalize.
"""),
    ("code", """\
state = run_agent("Should this bank approve the account-opening application for Gamma Operations GmbH?")
print("=== TRACE ===")
for line in state.trace:
    print(line)
print()
print("=== ANSWER ===")
display.md(state.answer)
"""),
    ("md", """\
**Grade the answer.** The same checklist from Hour 2:

1. Full ownership chain (KY → PA → LI)? ✓ should be present (controls_chain tool)
2. PEP-relative classification? ✓ should be present (get_entity_details + policy lookup)
3. Cross-link to Atlas Wirecorp? ✓ should be present (controlled_by tool)
4. Sanctions alias match with calibrated score? ✓ should be present (sanctions_check tool)
5. SoF gap? ✓ should be present (document_search tool)
6. Recommendation: ESCALATE or DECLINE (not APPROVE)
7. Citations to specific tools/evidence pieces?

This is Gen 3 working. **Compare to Gen 1's answer in Hour 2 and Gen 2's in Hour 6.** Gen 3's answer is *not* magic — it is the union of the tools' outputs, synthesized by Claude. The agent's value is *picking* the tools and *verifying* the result.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. The two characteristic failures

Agents fail in two characteristic ways. This section runs each.

### Failure A — looping

The agent gets stuck calling the same tool repeatedly because the critic isn't satisfied. Mitigated by `max_iterations`.
"""),
    ("code", """\
# Force a low iteration cap and a question that needs more
state = run_agent(
    "Provide a comprehensive risk assessment covering every possible angle of this customer.",
    max_iterations=1,
)
print(f"Iterations completed: {state.iterations}")
print(f"Final critique: {state.critique[:200]}")
print()
print("Answer (truncated):")
print(state.answer[:600])
"""),
    ("md", """\
The agent runs once, the critic says "insufficient," the iteration cap kicks in, and we finalize with what we have. **This is the correct behaviour** — the alternative is unbounded cost. Production agents have hard caps; tutorial agents do too.
"""),
    ("md", """\
### Failure B — wrong tool, confident answer

The agent picks the wrong tool, the tool returns *something*, the agent treats it as the answer. The critic helps catch this — but only sometimes. Try a question outside the tool catalogue:
"""),
    ("code", """\
state = run_agent("What is the expected loss on this account over the next 12 months?")
print("=== TRACE ===")
for line in state.trace:
    print(line)
print()
print("=== ANSWER ===")
display.md(state.answer[:1500])
"""),
    ("md", """\
None of our tools can answer this — there's no loss-modelling tool. A *well-designed* agent should return "I cannot answer with available tools." Whether yours does depends on Claude's reading of the catalogue.

**The lesson:** the tool catalogue *is* the agent's competence boundary. Adding a tool extends competence; missing tools mean missing competence; mis-described tools cause confused competence.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. ReAct, Self-RAG, CRAG, Reflexion — what we just implemented

The agent above implements a pattern variant of each of the four canonical agentic-RAG techniques:

- **ReAct** (Reason + Act, Yao et al. 2022) — interleave reasoning and tool calls. Our plan → execute is the ReAct loop in a tidied-up form.
- **Self-RAG** (Asai et al. 2023) — the model decides when to retrieve and grades its own output. Our planner decides when to call tools; our critic grades.
- **CRAG** (Corrective RAG, Yan et al. 2024) — a lightweight evaluator decides whether to retry retrieval. Our critic → plan transition is exactly this.
- **Reflexion** (Shinn et al. 2023) — a critic reads the trace and proposes a revised plan; the agent re-tries. Our critique becomes the planner's feedback on the next iteration.

We didn't pick "a technique" and implement it; we built a single loop where each of these techniques is one node. **This generalises** — the modern Gen 3 agent is not a single algorithm but a configuration of plan-execute-critique-finalize, where each node is tuned to the task.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 9

Three questions:

1. **In the Lotus run above, how many tool calls did the agent make?** What did each cost in latency? Now imagine a control manager running 200 cases a day at that cost. Is your platform's budget compatible?
2. **The critic decided "sufficient" at some iteration. Was it right?** Read the evidence and the final answer; find one claim that was *not* covered by evidence. The critic missed it. Production critics are tuned to be strict.
3. **What would change if you removed one tool from the registry?** Pick one (e.g., `sanctions_check`) and predict what the Lotus answer would now look like. The point: tools are not interchangeable.

Next: [Hour 9 — Context Graphs](./hour09_context_graphs.ipynb). The complement to agent design: structuring the *input* the agent reasons over.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour08_agentic_reasoning.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
