# Hour 7 — Hybrid retrieval and the Gen 2 → 3 seam

A reading companion to `notebooks/hour07_hybrid_retrieval.ipynb`.

> **One-line frame for the hour.** *Even before an LLM agent drives the loop, decomposing a question by hand and routing each sub-question to the right retriever produces dramatically better answers than any single mode. That experience is the conceptual scaffolding for Hour 8's agent.*

## 1. The three modes, in production

By Hour 7 you have three working retrieval modes:

- **Vector + BM25 + LLM rerank** (Hour 2) — for similarity-shaped questions over unstructured text.
- **Graph traversal via Cypher** (Hour 6) — for multi-hop relational queries.
- **Direct tools** (`sanctions_check`, `fuzzy_name_match`, `controls_chain`, `controlled_by`, `adverse_media_check`, `document_search`, `get_entity_details`) — for calibrated answers with deterministic confidence.

A production platform does not pick one. It uses all three, routing each sub-question to the mode that best fits its shape.

## 2. Why "decompose first" is the load-bearing move

The Lotus question — "should we approve Gamma Operations?" — has the *appearance* of one question. Architecturally it is five:

1. Who is the UBO? (relational)
2. Is the UBO a PEP / PEP-relative? (relational + document)
3. What else does the UBO control? (relational)
4. Is the deposit's originator sanctioned? (fuzzy match + policy)
5. Is source-of-funds adequately documented? (document)

Each sub-question has a *natural* retrieval mode. A monolithic context that tries to answer all five from one retriever inevitably drops one or two. **Decomposition is the architectural move that unlocks hybrid.**

The hour shows the decomposition by hand. Hour 8's agent automates it.

## 3. The fuzzy match — why tools matter

Hour 3's Diagnostic 3 failed because Gen 1 reached for similarity when it should have reached for fuzzy matching. We saw a four-line `SequenceMatcher` produce the right answer that hours of retriever tuning could not.

This hour formalises that lesson as a *tool*. The `sanctions_check` tool:

- Takes a name.
- Compares against all entries on the sanctions lists (primary names + aliases).
- Returns ESCALATE / REVIEW / CLEAR per the bank's policy thresholds (85% / 70%).
- Cites the matched list entries.

The result is a calibrated, defensible answer. *That* is what an audit needs. Vector retrieval cannot produce it.

The broader lesson: **whenever a question has a calibrated, deterministic answer, build it as a tool — not as a retrieval pattern.** Sanctions match, age check, currency conversion, jurisdiction risk lookup, account-balance check — all tools.

## 4. The hand-coded hybrid

The hour assembles five sub-answers into one Claude call. The pattern:

```
question
   ├── decompose
   │     ├── controls_chain   → UBO chain
   │     ├── get_entity_details → PEP status
   │     ├── controlled_by    → cross-link
   │     ├── sanctions_check  → calibrated decision
   │     └── document_search  → SoF policy
   ├── concatenate evidence with provenance
   └── synthesize via LLM
```

This is not yet an agent. The decomposition was hand-written. There is no critic. There is no loop. **But it is a correct, defensible answer to the Lotus question** — significantly better than any single-mode answer in earlier hours.

This is also what most successful 2026 Gen 3 platforms look like in practice: hand-decomposed pipelines that *use* an agent for specific verification or open-ended sub-questions, rather than letting the agent drive the entire conversation. The fully agent-driven design (Hour 8 and 11) is the right model for *unknown-shape* queries; the hand-decomposed hybrid is the right model for *known-shape* queries that recur all day.

## 5. Why this is not yet Gen 3

Two specific things make this hour a *seam* and not the destination:

- **Who decided which tool to call?** You did. The agent would.
- **Who verified the answer is grounded?** Nobody. The agent's critic would.

The next hour introduces both.

## 6. Temporal, deferred honestly

This hour acknowledges and *defers* the temporal problem. Our schema has `effective_from` and `effective_to` on edges; Cypher does not have first-class temporal semantics; production approximations are hand-coded date filters. Real production KGs model bi-temporal facts. We do not implement bi-temporal modelling. **TIE** is the research direction.

The honest framing: temporal is the one Gen 2 strain we acknowledge and do not solve. For the tutorial's scope, the cost of properly handling it would dwarf its educational benefit. For your platform's scope, it is potentially a make-or-break engineering investment.

## 7. What to take away from Hour 7

- A working hand-coded hybrid retriever that routes sub-questions to retrieval modes.
- The fuzzy-match tool as the prototypical "calibrated tool" pattern.
- The realisation that *decomposition is the load-bearing move*.
- A precise sense of what the next hour adds: planner (decides the decomposition), critic (verifies the answer), loop (iterates).
- An honest deferral on temporal reasoning.
