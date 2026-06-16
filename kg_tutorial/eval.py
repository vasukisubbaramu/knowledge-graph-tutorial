"""A tiny evaluation harness for Hour 12.

The point: a small set of ground-truth questions + expected facts, run
through each generation's stack, scored on the dimensions a control
manager actually cares about — answer correctness, citation quality,
cost, latency.

This is deliberately simple. Production eval (RAGAS, Trulens, custom
harnesses) is a system; this is the educational floor.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from kg_tutorial import config, llm


@dataclass
class EvalCase:
    """One ground-truth case.

    `expected_facts` is a list of strings that MUST appear (semantically,
    not as substrings) in a correct answer. We grade with an LLM judge.
    """

    id: str
    question: str
    expected_facts: list[str]
    must_cite: list[str] = field(default_factory=list)   # doc/node ids that should be referenced
    expected_decision: str | None = None                  # APPROVE / DECLINE / ESCALATE


def lotus_eval_cases() -> list[EvalCase]:
    """The canonical eval set for the Lotus scenario."""
    return [
        EvalCase(
            id="ubo_chain",
            question="Trace the full ownership chain of Gamma Operations GmbH to its natural-person UBO.",
            expected_facts=[
                "Gamma Operations GmbH is 75% owned by AlphaBeta Trading SA",
                "AlphaBeta Trading SA is 100% owned by ACME Holdings Ltd",
                "ACME Holdings Ltd is 50% owned by John Q. Public",
                "John Q. Public is the natural-person UBO",
            ],
            must_cite=["e_gamma_ops", "e_alphabeta_trading", "e_acme_holdings", "p_john_q_public"],
        ),
        EvalCase(
            id="cross_link",
            question="List every entity that John Q. Public controls directly or indirectly.",
            expected_facts=[
                "ACME Holdings Ltd",
                "AlphaBeta Trading SA",
                "Gamma Operations GmbH",
                "Atlas Wirecorp",
            ],
            must_cite=["p_john_q_public", "e_atlas_wirecorp"],
        ),
        EvalCase(
            id="pep_classification",
            question="Is John Q. Public classified as a PEP-relative under this bank's policy? Why?",
            expected_facts=[
                "John Q. Public is the nephew of MP Alice Public",
                "the bank's PEP policy treats nephews of sitting MPs as PEP-relatives",
                "Enhanced Due Diligence is required",
            ],
            must_cite=["p_john_q_public", "d_policy_pep"],
        ),
        EvalCase(
            id="sanctions_atlas",
            question=(
                "The first inbound deposit is from 'ATLAS WIRECORP'. Is that counterparty subject "
                "to any sanctions? Cite the list entry."
            ),
            expected_facts=[
                "OFAC has an entry for ATLAS WIRE CORPORATION",
                "the name match is fuzzy / near-miss",
                "fuzzy score is above the bank's policy threshold of 85%",
                "the deposit should be escalated",
            ],
            must_cite=["s_atlas"],
        ),
        EvalCase(
            id="lotus_full",
            question="Should this bank approve the account-opening application for Gamma Operations GmbH?",
            expected_facts=[
                "multi-jurisdictional UBO chain through Cayman, Panama, and Liechtenstein",
                "UBO is a PEP-relative",
                "deposit originator is sanctioned (fuzzy match above policy threshold)",
                "source-of-funds is not adequately supported",
                "decision should be ESCALATE or DECLINE — not APPROVE",
            ],
            must_cite=["e_gamma_ops", "p_john_q_public", "s_atlas"],
            expected_decision="ESCALATE",
        ),
    ]


# ---------------------------------------------------------------------------
# Per-run telemetry
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    case_id: str
    generation: str
    answer: str
    elapsed_seconds: float
    cost_usd: float = 0.0  # approximate, set by the harness if known
    citations_found: list[str] = field(default_factory=list)


def run_case(case: EvalCase, generation: str, answer_fn: Callable[[str], str]) -> RunResult:
    """Run one case through one generation's stack, time it, return the result."""
    t0 = time.perf_counter()
    answer = answer_fn(case.question)
    elapsed = time.perf_counter() - t0
    found = [cid for cid in case.must_cite if cid in answer]
    return RunResult(
        case_id=case.id,
        generation=generation,
        answer=answer,
        elapsed_seconds=elapsed,
        citations_found=found,
    )


# ---------------------------------------------------------------------------
# LLM-as-judge scoring
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You are evaluating a control-manager system's answer to a KYC question.

QUESTION: {question}

EXPECTED FACTS (each fact must be expressed, not necessarily verbatim):
{expected_facts}

ACTUAL ANSWER:
{answer}

For each expected fact, indicate whether the actual answer expresses it. Reply as JSON:
  [{{"fact": "...", "found": true|false, "explanation": "..."}}]
"""


def judge(case: EvalCase, answer: str) -> list[dict]:
    """LLM-as-judge scoring of one answer against expected facts."""
    facts_text = "\n".join(f"  - {f}" for f in case.expected_facts)
    return llm.ask_json(
        JUDGE_PROMPT.format(question=case.question, expected_facts=facts_text, answer=answer),
        max_tokens=800,
    )


def summarize_judgement(judgement: list[dict]) -> tuple[float, str]:
    """Return (recall, one-line summary)."""
    n = len(judgement) or 1
    hits = sum(1 for j in judgement if j.get("found"))
    return hits / n, f"{hits}/{n} expected facts expressed"


# ---------------------------------------------------------------------------
# Routing: pick the right generation for a query
# ---------------------------------------------------------------------------

ROUTER_PROMPT = """You route a user question to one of three retrieval stacks.

STACKS
- gen1: Vector + BM25 + LLM rerank. Best for: similarity-shaped questions over unstructured documents (policy lookup, definitions, boilerplate).
- gen2: Knowledge-graph traversal + structured queries. Best for: multi-hop relational questions, set aggregation across entities, ownership chains.
- gen3: Agentic loop with tools and self-critique. Best for: open-ended decisions, sanctions verification, fuzzy matching, anything requiring verification.

QUESTION: {question}

Reply with JSON: {{"stack": "gen1" | "gen2" | "gen3", "reason": "..."}}
"""


def route(question: str) -> dict:
    return llm.ask_json(ROUTER_PROMPT.format(question=question), max_tokens=200)
