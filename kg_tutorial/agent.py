"""A small agent built on LangGraph — used by Hours 8 and 11.

The agent's architecture is intentionally minimal so the moving parts are
visible:

    PLAN -> EXECUTE -> CRITIQUE -> (loop or finalize)

The state is a single dataclass; the transitions are functions on that
state. LangGraph wires them together. The reason to use LangGraph rather
than rolling your own loop is *inspectability* — every state transition
is visible, the graph is debuggable, and you can interrupt and resume.

Hours 8 / 11 customise the prompts and add tools; the structure here is
the same in both.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from kg_tutorial import config, llm, tools


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    question: str
    plan: list[str] = field(default_factory=list)        # the planner's task list
    evidence: list[dict] = field(default_factory=list)   # tool results collected so far
    critique: str = ""                                   # critic's last feedback
    answer: str = ""                                     # final answer when done
    iterations: int = 0
    max_iterations: int = 4
    trace: list[str] = field(default_factory=list)       # human-readable log of what happened


# ---------------------------------------------------------------------------
# The three node functions
# ---------------------------------------------------------------------------

PLANNER_PROMPT = """You are the planner step of a control-management agent.

The user's question is below. Your job is to decompose it into 2-5 atomic
sub-tasks, each of which is answerable by ONE tool call. For each sub-task,
state which tool to call and what arguments.

{tools_catalogue}

USER QUESTION:
{question}

PRIOR EVIDENCE (may be empty):
{evidence_summary}

CRITIC FEEDBACK (may be empty):
{critique}

Reply as JSON: a list of objects with keys `tool` and `args`. If you have
enough evidence to answer the question, return an empty list.
"""


def plan_step(state: AgentState) -> AgentState:
    """Ask the planner what to do next."""
    evidence_summary = "\n".join(f"- {e['tool']}: {e['summary']}" for e in state.evidence) or "(none)"
    raw = llm.ask_json(
        PLANNER_PROMPT.format(
            tools_catalogue=tools.describe_tools(),
            question=state.question,
            evidence_summary=evidence_summary,
            critique=state.critique or "(none)",
        ),
        max_tokens=600,
    )
    state.plan = raw if isinstance(raw, list) else []
    state.trace.append(f"PLAN: {len(state.plan)} sub-tasks")
    return state


def execute_step(state: AgentState) -> AgentState:
    """Run every tool call in the current plan, collect evidence."""
    for step in state.plan:
        try:
            tool_name = step["tool"]
            args = step.get("args", {})
            result = tools.call(tool_name, **args)
            state.evidence.append({
                "tool": tool_name,
                "args": args,
                "summary": result.summary,
                "confidence": result.confidence,
                "evidence": result.evidence,
                "notes": result.notes,
            })
            state.trace.append(f"  EXEC: {tool_name}({args}) -> {result.summary[:80]}")
        except Exception as e:
            state.evidence.append({
                "tool": step.get("tool", "?"),
                "args": step.get("args", {}),
                "summary": f"FAILED: {type(e).__name__}: {e}",
                "confidence": 0.0,
                "evidence": {},
                "notes": "tool failed",
            })
            state.trace.append(f"  EXEC FAILED: {step}: {e}")
    state.plan = []
    return state


CRITIC_PROMPT = """You are the critic step of a control-management agent.

Evidence collected so far:
{evidence_summary}

User question: {question}

Decide: do we have enough evidence to answer the question with citations,
or do we need more tool calls? Reply as JSON:
  {{"sufficient": bool, "feedback": "...", "missing": "..." (or "")}}

Be strict: if a key claim cannot be cited from the evidence, sufficient
must be false. Specific evidence missing should be named in `missing`.
"""


def critique_step(state: AgentState) -> AgentState:
    """Grade the evidence-so-far against the question."""
    if not state.evidence:
        state.critique = "No evidence yet."
        state.trace.append("CRITIQUE: empty evidence")
        return state
    evidence_summary = "\n".join(
        f"- {e['tool']}({e['args']}): {e['summary']} (conf={e['confidence']})"
        for e in state.evidence
    )
    judged = llm.ask_json(
        CRITIC_PROMPT.format(question=state.question, evidence_summary=evidence_summary),
        max_tokens=400,
    )
    sufficient = bool(judged.get("sufficient"))
    feedback = judged.get("feedback", "")
    missing = judged.get("missing", "")
    state.critique = ("OK: " if sufficient else "INSUFFICIENT: ") + feedback + (f" Missing: {missing}" if missing else "")
    state.trace.append(f"CRITIQUE: sufficient={sufficient} :: {feedback[:80]}")
    return state


FINALIZER_PROMPT = """You are the final answer step of a control-management agent.

Question: {question}

Evidence (cite specific items in your answer):
{evidence_detail}

Write a structured recommendation as JSON with these keys:
  - "recommendation": "APPROVE" | "DECLINE" | "ESCALATE"
  - "rationale": a 3-5 sentence explanation
  - "key_findings": [list of bulleted findings, each with a citation to a tool name]
  - "open_questions": [things you couldn't verify and would need a human to address]
"""


def finalize_step(state: AgentState) -> AgentState:
    """Produce the structured final answer."""
    evidence_detail = json.dumps(state.evidence, indent=2, default=str)
    judged = llm.ask_json(
        FINALIZER_PROMPT.format(question=state.question, evidence_detail=evidence_detail),
        max_tokens=1200,
        model=config.MODEL_REASONING,  # use Opus for the final synthesis
    )
    state.answer = json.dumps(judged, indent=2)
    state.trace.append(f"FINAL: {judged.get('recommendation', '?')}")
    return state


# ---------------------------------------------------------------------------
# Loop control
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> str:
    """Decide where to go next: plan more, finalize, or stop on budget."""
    if state.iterations >= state.max_iterations:
        return "finalize"
    if state.critique.startswith("OK:"):
        return "finalize"
    return "plan"


# ---------------------------------------------------------------------------
# Build the LangGraph state graph
# ---------------------------------------------------------------------------

def build_agent():
    """Compose the agent as a LangGraph StateGraph.

    Importing langgraph only here — keeps the module importable for the
    other notebooks even if langgraph isn't installed yet.
    """
    from langgraph.graph import StateGraph, END

    g = StateGraph(AgentState)
    g.add_node("plan", plan_step)
    g.add_node("execute", execute_step)
    g.add_node("critique", critique_step)
    g.add_node("finalize", finalize_step)

    g.set_entry_point("plan")
    g.add_edge("plan", "execute")
    g.add_edge("execute", "critique")
    g.add_conditional_edges(
        "critique",
        # increment iteration count then route
        lambda s: (setattr(s, "iterations", s.iterations + 1), should_continue(s))[-1],
        {"plan": "plan", "finalize": "finalize"},
    )
    g.add_edge("finalize", END)
    return g.compile()


def run_agent(question: str, max_iterations: int = 4) -> AgentState:
    """Run the agent end-to-end. Returns the final state, including trace."""
    state = AgentState(question=question, max_iterations=max_iterations)
    app = build_agent()
    final = app.invoke(state)
    if isinstance(final, dict):
        # LangGraph returns the state as a dict; rehydrate for ergonomics
        return AgentState(**final)
    return final
