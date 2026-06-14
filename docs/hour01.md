# Hour 1 — The retrieval problem and why Gen 1 → 3

A reading companion to `notebooks/hour01_concepts.ipynb`. The notebook walks you through the same arc with code; this document is the conceptual spine you can read without a computer.

> **One-line frame for the whole tutorial.** *Different shapes of questions deserve different shapes of retrieval, and the role of a "generation" is which shape it natively handles.*

## 1. Why retrieve at all

A language model trained on data up to time $T$ cannot know facts that exist only at $T + \epsilon$ or behind your firewall. Even when it has the facts in its training set, it has no robust mechanism to be *made* to use the ones you care about — its retrieval, such as it is, runs over the model's parameters, not over your corpus, and is opaque to you. Retrieval-Augmented Generation puts the corpus *outside* the model and the retrieval *inside* your control.

That, fundamentally, is the only architectural fact common to Gen 1, Gen 2, and Gen 3. Everything else is design choice.

Three classes of failure that retrieval has to solve:

- **Closed-world ignorance** — the model has never seen the entity. Any retrieval addresses this.
- **Disconnected facts** — the model has retrieved two relevant chunks but never relates them. Graph-aware retrieval addresses this.
- **No verification** — the model answers confidently using partial context. Agentic retrieval with self-critique addresses this.

This taxonomy is the load-bearing structure of the next 11 hours. Memorize it.

## 2. Gen 1 — Vector RAG

```text
Question -> Embed -> Top-k chunks -> Prompt(context, question) -> Answer
```

A user query is embedded into a vector. A vector store retrieves the *k* most similar chunks of your corpus by cosine similarity. The LLM is then given the question and the retrieved text, with a prompt of the form *"Given the context, answer the question."*

This works astonishingly well when the underlying signal *is* semantic similarity over text. "Find me the section of policy about politically exposed persons" is a Gen 1 question. So is "what does this control framework say about sanctions tolerance?" The model retrieves, the model summarizes, the user is happy.

It works badly when the answer is *constructed by relating* facts that live in different chunks. "Who is the ultimate beneficial owner of Gamma Operations?" is not a similarity question — there is no chunk that *says* "the ultimate beneficial owner of Gamma Operations is John Q. Public." That fact is the composition of three ownership edges, each in a different document. Vector retrieval will surface three chunks; the LLM will get them all, may make the connection, and may not. There is nothing in the architecture that *guarantees* the multi-hop relation is preserved.

Three quiet assumptions Gen 1 makes that you should hold in mind:

- **Chunks are independent**. Similarity reasons about pairs, not paths.
- **Ranking is contextless**. A chunk that *looks like* the question wins over a chunk that *answers* the question, when those differ.
- **The model receives prose, not entities**. Co-referencing "John" across chunks is the model's job, not the retriever's.

## 3. Gen 2 — Graph RAG

```text
Documents -> (extract entities + relations) -> Knowledge Graph
Question -> entity-link -> subgraph retrieval -> (subgraph + supporting text) -> LLM -> Answer
```

Gen 2 says: structure your knowledge as a graph at *ingest* time. Entities (Person, Organization, Account, Transaction) become nodes; relationships (Controls, Owns, Resides, Pays) become edges. Once the graph is built, multi-hop questions become traversals.

"Who controls Gamma Operations?" is now: start at the Gamma Operations node, traverse incoming `CONTROLS` edges to depth 3, return the natural persons reached. The answer is constructed by *querying* the structure, not by hoping the LLM relates separately-retrieved chunks.

The dominant implementation patterns in 2026:

- **Schema-guided**: you design the ontology, the extractor maps to it, the queries are written against it. High setup cost, high reliability. (Hour 4 builds one for KYC + UBO.)
- **Schema-free** (Microsoft GraphRAG): the extractor invents entities and relations, communities are clustered, summaries are pre-computed. Lower setup cost, higher fuzziness. (Hour 5 demos this.)

Three quiet assumptions Gen 2 makes:

- **Extraction is reliable**. If the extractor missed an edge, the query missed it too.
- **Reality fits a static schema**. Schema drift is operational pain.
- **Queries are crisp**. Cypher asks "matches `'Atlas Wire Corporation'` exactly?", not "matches a likely alias of it?". Real-world entity resolution involves transliteration, typo tolerance, jurisdictional variants — none of which Cypher does natively.

The interesting failure surface in Gen 2 is not *recall* — graph traversal recalls perfectly given a correct graph. It's *fidelity to reality*. Real-world data does not arrive crisply.

## 4. Gen 3 — Agentic + Hybrid

```text
Question -> Planning agent
              ├── decompose into sub-questions
              ├── route each to (vector | graph | structured | tool)
              ├── execute, observe, possibly iterate
              ├── self-critique: "did I answer the question? are citations sufficient?"
              └── final answer + audit trail
```

Gen 3 is not "Gen 2 plus reasoning." It is **orchestration**: an agent that decides what shape of retrieval each sub-question deserves, and **verifies its own output** before returning it.

The mental model is closer to a junior analyst than to a search engine. The agent receives a question; decomposes it; selects tools (semantic search, graph traversal, sanctions API, fuzzy name matcher); executes; reflects; possibly re-tries; produces a final report with citations and a self-rating.

This is where the contemporary research patterns live:

- **ReAct** (Reason–Act loops): interleaved reasoning steps and tool calls.
- **Self-RAG**: the model is trained or prompted to retrieve only when needed and to grade its own response against the retrieved evidence.
- **CRAG** (Corrective RAG): a lightweight evaluator decides whether the retrieved context is sufficient; if not, the retrieval is corrected (broader, narrower, or different source).
- **Reflexion**: a critic reads the trace and proposes a revised plan; the agent re-tries.

Three quiet assumptions Gen 3 makes, and their costs:

- **The agent will know when to stop**. Loop control is a real engineering problem. (Hour 8.)
- **The tools are correctly described**. If your tool spec is wrong, the agent will use it wrong. (Hour 11.)
- **You can afford the latency**. A naive Gen 3 agent for one KYC decision might take 30 seconds and a dollar. Whether that's acceptable depends entirely on *which* decisions you route to it. (Hour 12 builds the routing.)

## 5. The Cost–Capability–Latency triangle

A control manager handles 200 alerts a day. They cannot afford to spend 30 seconds and \\$0.40 per alert on Gen 3 — but they also cannot afford to *miss* a sanctions match by spending one second on Gen 1. The right architecture is *hybrid* and *routed*: each query class is handled by the cheapest sufficient mode, with explicit policy on when to escalate.

|                | Gen 1 (Vector) | Gen 2 (Graph) | Gen 3 (Agentic) |
|----------------|----------------|---------------|-----------------|
| Setup cost     | Low            | High          | Very high       |
| Per-query cost | Cheap          | Modest        | Expensive       |
| Latency        | <1 s           | 1–3 s         | 5–60 s          |
| Capability     | Similarity     | Multi-hop relational | Open-ended + verified |
| Failure        | Misses connections | Brittle extraction | Loops, hallucination under stress |
| Audit          | Cited chunks   | Cited subgraph | Reasoning trace |

The right question to take away from Hour 1 is *not* "should I move to Gen 3?" It is **"what mix of Gen 1, Gen 2, and Gen 3 does each query class in my platform deserve, and how do I prove the mix is right?"**

## 6. "Is Gen 1 stale?"

Gen 1 is not stale. The vendor framing — Gen 1 → Gen 2 → Gen 3, each strictly dominating the previous — is wrong as architecture even when it's right as a sales pitch. Vector RAG is the right tool for similarity-shaped questions; that class of question is not going anywhere.

Every Gen 2 system has Gen 1 inside it (similarity over community summaries, document chunks, fallback fact lookup). Every Gen 3 system has Gen 1 *and* Gen 2 as tools — the agent calls them. The layering is:

```
Gen 3 (orchestrate + verify)
  ├── Gen 2 (structure + multi-hop)
  ├── Gen 1 (similarity over unstructured text)
  └── Tools (sanctions, code, calculators, fuzzy match, ...)
```

Gen 1 is the floor. Gen 2 is the walls. Gen 3 is the project manager. They build the same house.

## 7. Frontier signposts

Three pointers to research the user is already reading. None are implemented in this tutorial; each is the obvious next direction after Hour 12.

- **ULTRA / GAMMA** — KG foundation models. The aim: a single pre-trained model that can do inductive link prediction on *any* KG, with *any* vocabulary, without training. This is the "transformer moment" for KGs, three to five years late. (Galkin et al. 2023; Xin et al. 2025.) Hour 4 cites them, Hour 7 returns to them.
- **TIE** — Temporal KG completion with incremental learning. KGs in finance are temporal; ownership changes, listings expire, sanctions are added. TIE handles this without catastrophic forgetting. (Wu et al.) Hour 7 cites.
- **KumoRFM** — Relational foundation models. Enterprise data is overwhelmingly *relational*, not graph or text. KumoRFM extends in-context learning to multi-table relational settings. This is plausibly the next architectural step *after* Gen 3 for enterprise use. (Fey et al. 2025.) Hour 12 cites.

## 8. What you should leave Hour 1 carrying

- The three classes of failure and which generation fixes each.
- Three architecture diagrams: Gen 1, Gen 2, Gen 3.
- The triangle table.
- The Lotus case shape, well enough to draw it from memory.
- A clear answer to the question "is Gen 1 stale?": no.
- A reframed question to take into the rest of the tutorial: *not* "which generation wins?" but *"which mix does each query class deserve, and how do I prove the mix is right?"*

Hour 2 is hands-on: building a Gen 1 system over the seven Lotus documents and watching it run smack into the limits described above.
