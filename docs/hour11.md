# Hour 11 — End-to-end Control Manager agent

A reading companion to `notebooks/hour11_control_manager_agent.ipynb`.

> **One-line frame for the hour.** *The capstone. You produce the Lotus recommendation the full Gen 3 way — with a planner, tools, critic, finalize, reasoning trace, audit log, and human-in-the-loop hand-off — and compare it to the Gen 1 and Gen 2 answers side-by-side. By the end you can defend the answer in front of a regulator.*

## 1. What the hour does

The hour is mostly running and looking. The hard work was done in earlier hours:

- The planner, executor, critic, finalize loop — Hour 8.
- The tool catalogue — Hour 7.
- The context engineering and trace structure — Hour 9.

This hour assembles them into one run of the canonical Lotus question and shows what the output of a Gen 3 control-manager platform actually *looks like*.

## 2. The full Gen 3 output

The output of one Lotus run has four parts:

1. **Reasoning trace.** A timestamped log of every node transition — plan(s), tool calls with arguments, critic verdicts, finalize. This is the answer to "what did the agent do?"

2. **Evidence record.** Every tool call's arguments, output, and confidence. This is the answer to "what did the agent see?"

3. **Final answer (structured JSON).**
   - `recommendation`: APPROVE / DECLINE / ESCALATE
   - `rationale`: 3-5 sentence explanation
   - `key_findings`: bulleted, each citing a tool name
   - `open_questions`: things the agent could not verify, flagged for human review

4. **Audit record.** All three above bundled with the question and metadata, structured for export to a tamper-evident audit log.

This is the structure regulators audit. The platform's job is to produce all four reliably for every decision.

## 3. Side-by-side: Gen 1 vs Gen 2 vs Gen 3

The hour runs the same question through all three pipelines and prints the answers next to each other. The expected qualitative differences:

| | Gen 1 | Gen 2 | Gen 3 |
|---|---|---|---|
| Ownership chain | partial (relies on right chunk) | complete + cited | complete + cited |
| Cross-link (John→Atlas) | missed | found | found |
| Sanctions match | flagged by name; no calibrated score | flagged by name; no calibrated score | calibrated score + threshold + decision |
| PEP-relative | usually caught | caught with `is_pep` + policy | caught with `is_pep` + policy + open question for SoW |
| Source-of-funds | mentioned if right chunk surfaces | mentioned cleanly | mentioned with explicit "missing supporting documents" |
| Citations | by document title | by document title + node id | by tool call + node id |
| Audit log | the answer | the answer + retrieved chunks | the answer + trace + evidence + open questions |
| Recommendation | uncertain | ESCALATE / DECLINE | ESCALATE / DECLINE with open questions |

Read all three. The differences are stark; the audit story is the largest.

## 4. The reasoning trace is the audit log

A control-management platform owes regulators evidence that decisions were made *systematically*. The trace is the systematic evidence:

- Which evidence was considered (every tool call is logged).
- What was concluded at each step (planner, critic verdicts).
- Where the decision was finalized (and why "sufficient" was decided).
- What was *not* verified (the open_questions field).

Without the trace, a regulator's question — "show me why you approved this customer" — has only the answer for evidence. With the trace, the chain of reasoning is reproducible. **Defensibility is the first-class output of Gen 3, not the answer itself.**

## 5. Human-in-the-loop hand-off

The agent's `open_questions` field is where it surfaces what it could not verify with the available tools. These are the questions that should route to a human reviewer.

In production, three categories should always hand off:

1. **Fuzzy matches in the review band** (70-85% similarity — the "you decide" zone the bank's policy specifies).
2. **Adverse media that is substantive but ambiguous** — a credible negative article, no formal finding.
3. **Source-of-wealth questions for PEPs and PEP-relatives** — these are policy-mandatory and rarely cleanly answerable from documents alone.

The platform's design intent should be **agent decides what's clear, human decides what's not** — and the agent's job includes correctly identifying which is which.

A subtle point: the agent does not *escalate* in the sense of "I can't answer." It answers what it can and flags what it cannot. The human review is over the flags, not over the whole case. This separation is what makes the platform scale: a manager handling 200 alerts a day cannot fully review every one but *can* review the open questions.

## 6. What can still go wrong

Three production failure modes to remember:

1. **The sanctions list is stale.** The fuzzy matcher gives a calibrated answer based on the list it sees. If the list isn't current, the answer is confidently wrong. Mitigation: refresh schedule + freshness monitoring + agent halt if list is more than N hours old.
2. **A tool throws.** Network failures, schema drift, API changes. The agent's evidence collection captures the failure (rather than silently using fewer facts). The critic should treat tool failures as insufficient evidence, not as absence of risk.
3. **The agent's planner is over-confident.** It calls fewer tools than warranted because Claude judged the question simple. Mitigation: floor on tool calls per category of question; the router (Hour 12) enforces it.

Each of these is a real production incident waiting to happen. Each has a specific mitigation; none is fully solved by any single Gen 3 design choice. The platform owner's job includes operating the platform — monitoring for these failure modes and responding when they occur.

## 7. What to take away from Hour 11

- A working end-to-end Gen 3 answer to the Lotus question, with citations and audit trail.
- The four parts of a Gen 3 output: trace, evidence, structured answer, audit record.
- A precise sense of how Gen 3 differs from Gen 1 and Gen 2 — not just in answer quality but in *defensibility*.
- The human-in-the-loop design pattern: agent answers what's clear, flags what's not.
- The three characteristic production failure modes and their mitigations.

You have built the platform. Hour 12 measures it.
