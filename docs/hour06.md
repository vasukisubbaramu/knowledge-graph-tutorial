# Hour 6 — Gen 2: Querying the graph

A reading companion to `notebooks/hour06_kg_querying.ipynb`.

> **One-line frame for the hour.** *Cypher answers structural questions cleanly that Gen 1 could not answer at all. The remaining three weaknesses — fuzzy matching, temporal reasoning, open-ended verification — define the Gen 3 agenda.*

## 1. The Gen 2 wins, by query class

The notebook walks through six worked Cypher queries. Each maps to a Gen 1 failure class from Hour 3.

### Query class 1 — multi-hop relational

```cypher
MATCH path = (root:LegalEntity {id: 'e_gamma_ops'})<-[:CONTROLS*1..5]-(controller)
RETURN path
```

The variable-length path operator `*1..5` is the single most consequential operator in Cypher. It traverses paths of length 1 to 5 hops along matching edges. The Lotus chain — Gamma → AlphaBeta → ACME → John — is one query, returned as a path. Gen 1 attempted this with retrieval; success was contingent on a single chunk containing the full chain. Gen 2 makes it structural.

### Query class 2 — cross-document aggregation

```cypher
MATCH (john:Person {id: 'p_john_q_public'})-[:CONTROLS*1..4]->(e:LegalEntity)
RETURN DISTINCT e
```

The set of entities John controls — directly or transitively. The cross-link to Atlas Wirecorp is found because the directorship is an edge in the graph, not a sentence in a document. Gen 1 missed this exact case in Hour 3, Diagnostic 2.

### Query class 3 — labeled + aggregated

```cypher
MATCH (p:Person)-[:CONTROLS]->(e:LegalEntity)
WHERE p.is_pep = true
RETURN p, count(DISTINCT e) AS entities_controlled
```

PEPs and PEP-relatives among controllers, ranked. SQL would need a join across three tables and a `GROUP BY`; Cypher is one pattern.

### The pattern

All three queries share a structure: **start from a known node, traverse along typed edges, filter or aggregate the result**. This is what graph databases do well. When the question maps onto this structure, Gen 2 is unbeatable.

## 2. The Gen 2 strain — fuzzy matching

Cypher's `=` is character-by-character. The sanctions list says `ATLAS WIRE CORPORATION`. The deposit narrative says `ATLAS WIRECORP`. Strict equality finds nothing. `CONTAINS` finds something but at high recall and low precision — the substring "ATLAS" matches a lot of false positives, and you get a boolean rather than a calibrated score.

A control manager cannot escalate on a boolean. The bank's policy says "fuzzy match >= 85 → escalate." Eighty-five is a number; Cypher's CONTAINS does not produce a number. The right instrument for fuzzy matching is a calibrated fuzzy string scorer (Jaro-Winkler, token-set ratio, a learned matcher, an LLM-based matcher) **invoked as a tool**, not embedded in a query.

This is the seam between Gen 2 and Gen 3. Gen 3's agent invokes the fuzzy matcher when it decides the question warrants it; Gen 2 cannot do that decision-making.

## 3. Text-to-Cypher

Asking a control manager to write Cypher is a non-starter. The realistic interaction is natural language → Cypher → results. The notebook implements this with one Claude call per query, the ontology in the system prompt.

When text-to-Cypher works it feels like magic. When it fails — wrong label, hallucinated property, missing filter — it fails in instructive ways. Production text-to-Cypher systems mitigate failures with:

- A validated schema description in the system prompt (we have one).
- Few-shot examples of successful queries for common patterns.
- A post-hoc Cypher validator that catches syntax errors before execution and prompts a retry.
- An explicit fallback: "I cannot answer this with the available schema."
- Conversation memory — if the first query returned nothing, the agent can reason about why and try a variation. (This is the bridge to Hour 8.)

A natural reading of text-to-Cypher is that it's the *single-LLM-call version* of an agent. Hour 8 introduces the proper multi-step version with self-critique.

## 4. Subgraph retrieval for an LLM

The Gen 2 retrieval-for-LLM pattern that pays off:

1. Identify the relevant *anchor nodes* for the question (the customer, the deposit, the UBO).
2. Pull the subgraph within N hops (typically 2-3).
3. Serialize the subgraph as a list of triples — nodes with their labels and properties, edges with their types and properties.
4. Send the serialized subgraph as context to the LLM, with the question.

This is dramatically denser and more structured than Gen 1's "top-k chunks of prose." The model sees the structure, not just the text. Hallucinations drop because there is less unstructured context to confuse it.

Compared to Gen 1:

- **Density.** A 2-hop subgraph around Gamma is ~30 lines of text. The equivalent prose context to convey the same information is 5-8 chunks.
- **Structure.** Triples are unambiguous. Prose requires the model to do co-reference resolution and chain-of-thought composition.
- **Citability.** Every fact has an id; the model can cite an edge.

Compared to Gen 3:

- **Single retrieval.** Gen 2 does one subgraph pull. Gen 3 may do several, refine based on the first result, and verify.

## 5. The Lotus answer, Gen 2

The notebook produces Gen 2's recommendation on the Lotus case by combining:

- A 3-hop subgraph around `e_gamma_ops`.
- A 2-hop subgraph around the deposit `dep_001`.
- A small set of policy chunks from the vector + BM25 + reranker pipeline (Hour 2's Gen 1 stack used as a sub-tool).

The expected qualitative differences from Gen 1's answer:

- **Ownership chain.** Gen 2 will list KY → PA → LI exhaustively; Gen 1 was contingent on the right chunk being retrieved.
- **The cross-link.** Gen 2 surfaces "John is *also* a director of Atlas Wirecorp" because the edge is in the subgraph; Gen 1 missed this by construction.
- **PEP-relative classification.** Both Gen 1 and Gen 2 should catch this; Gen 2 with cleaner provenance because `is_pep = true` is on the node.
- **Sanctions link.** Both will flag the deposit's counterparty name. Neither produces a calibrated fuzzy score — that's Hour 7.
- **Source of Funds gap.** Both should catch this from the SoF questionnaire chunk; Gen 2 will phrase it more crisply because it can cite the graph fact "this is the first deposit, EUR 500K, with no contractual support."

The right move for the reader: produce both answers (you did Gen 1 in Hour 2 and Gen 2 now) and compare them paragraph by paragraph. The differences are not subtle.

## 6. What Gen 2 still cannot do

By the end of Hour 6 you should have a precise picture of three remaining limits:

1. **Fuzzy sanctions match.** Already discussed. Hour 7 builds the tool.
2. **Temporal reasoning.** "Who was the UBO on 5 March 2024?" requires the graph to model bi-temporal facts (valid time + transaction time) and Cypher to support temporal joins. Our schema doesn't; Cypher doesn't first-class temporal semantics. TIE (Wu et al.) is the research direction; production approximations exist (every edge has `effective_from` and `effective_to`, queries hand-compute time slices).
3. **Open-ended reasoning with verification.** "Is the bank exposed to reputational risk if it onboards this customer?" is not a Cypher query. The KG retrieves; the LLM reasons; but the LLM does not naturally verify its own reasoning against the graph. The agentic loop in Hour 8 introduces self-critique; the end-to-end agent in Hour 11 makes verification first-class.

Each of these motivates a specific architectural move:

- Hour 7 — **Hybrid retrieval**: combine the graph's precision with vector's fuzziness, and call a fuzzy-match tool when the question demands it. The seam between Gen 2 and Gen 3.
- Hour 8 — **Agentic reasoning**: ReAct, Self-RAG, CRAG, Reflexion. The agent decides when to call which retriever, when to escalate, when to verify.
- Hour 11 — **End-to-end agent**: full Lotus recommendation with reasoning trace, calibrated confidence, citation chain, HITL hand-off.

## 7. What to take away from Hour 6

- The six Cypher idioms, especially variable-length path traversal.
- The pattern for KG-augmented LLM context — subgraph retrieval, triple serialization, structured prompt.
- The text-to-Cypher pattern and its failure modes.
- A clear comparison between Gen 1's and Gen 2's answers on the Lotus case — both as documents and as architectural artefacts.
- The three remaining strains: fuzzy match, temporal, open-ended verification.
- A concrete map of which Hour 7-11 lab addresses each strain.
