# Hour 3 — Where Gen 1 breaks

A reading companion to `notebooks/hour03_gen1_limits.ipynb`.

> **One-line frame for the hour.** *Gen 1's failures are not stupidity — they are structural consequences of the assumption that retrieval is similarity. The job of this hour is to make the structure visible.*

## 1. The point of failure-driven teaching

The temptation in a tutorial is to introduce Gen 2 and Gen 3 as "newer, better versions" of Gen 1, and to motivate them by handwaving at limitations. That approach produces students who can recite the limitations but cannot recognise them in their own systems.

The opposite approach — make three concrete queries fail in three structurally different ways, then dissect the failures — produces engineers who know which failure mode they are looking at when their production system underperforms, and which architecture move addresses it.

Hour 3 takes the latter approach.

## 2. The three structural limits

There are exactly three failure classes that motivate the entire Gen 2 → Gen 3 progression. They map cleanly to the three diagnostic queries in the notebook:

| Failure class | What it looks like | What architecture move fixes it |
|---|---|---|
| **Multi-hop relational** | "Who is the UBO?" — the answer is a path. Vector retrieval returns chunks. | KG traversal (Hour 6). |
| **Cross-document aggregation** | "What entities does X control?" — the answer is a set. Retrieval returns chunks. | KG queries with set semantics (Hour 6). |
| **Inference under name mismatch** | "Is `ATLAS WIRECORP` on the OFAC list?" — the answer requires fuzzy comparison and a calibrated threshold. | Tool use within an agent (Hour 11). |

The notebook runs each diagnostic, shows the chunks that were retrieved, shows the model's answer, and explains *why* the failure is structural. The "why" is the load-bearing content.

## 3. Diagnostic 1 in long form — multi-hop relational

When the question is "trace the ownership chain", the *answer* is a path through the KG: Gamma → AlphaBeta → ACME → John, with percentages on each edge. A path is fundamentally a relational object. The vector retriever sees the question as a string, embeds it, and retrieves chunks whose embeddings are close. Whether the chunk contains a *path* or merely *a name* is not a property the retriever can see.

In our specific dataset, the CDD form happens to contain a paragraph that summarises the chain. If that paragraph makes the top-k, the model answers correctly — by reading off the chunk. But that is *the data being friendly*. In production, the chain is documented in three separate registries in three separate jurisdictions, in three separate documents. The retriever returns the Liechtenstein document — closest to the query. The Cayman and Panama documents do not enter the model's context. The model answers the first hop and stops.

This is not a tuning problem. Increasing k retrieves *more chunks* but not *more paths* — the same chunk per ownership layer is still missed because each layer's chunk was scored on a *different* concept the query did not mention.

The fix is a different data model. A graph store, queried with `MATCH (p:Person)-[:CONTROLS*]->(e:Entity {id: 'e_gamma_ops'})`, walks the chain by construction.

## 4. Diagnostic 2 in long form — cross-document aggregation

When the question is "list every entity X controls", the *answer* is a set. A set is not a chunk. The model has to build the set by composing chunks. If a chunk is missed, an entity is missed silently. The model does not know the set is incomplete — it has no representation of "complete."

The pathological case is the Lotus **cross-link**: John controls ACME (and through ACME, AlphaBeta and Gamma), but John *also* controls Atlas Wirecorp directly. The Atlas directorship is, in our dataset, a single sentence in the source-of-funds questionnaire, surrounded by talk about deposits, not about control. The vector retriever scores it low for "control" queries. The fact does not enter the context. The model lists three entities; the truth is four.

What this exposes: *the retriever's measure of relevance is local to the chunk, not to the question's set-completeness requirement.* No amount of retriever tuning fixes this — the retriever genuinely cannot tell that the missing chunk is the most important one. The fix, again, is a different data model: a graph where John is the source of multiple control edges, and a query `MATCH (john:Person {id: 'p_john_q_public'})-[:CONTROLS]->(e)` returns all four entities exhaustively.

## 5. Diagnostic 3 in long form — inference under name mismatch

This one is special: it is not really a retrieval problem at all. The OFAC list says `ATLAS WIRE CORPORATION`; the deposit narrative says `ATLAS WIRECORP`. The right answer requires *fuzzy string comparison with a calibrated threshold* — that is what a sanctions screening system *is*.

If we try to solve it by embedding the OFAC list as text and retrieving by similarity, two things go wrong. First, embeddings of short strings (names) are noisy — BGE was trained on long-form text. Second, similarity scores have no *calibrated threshold*: the bank's policy says "escalate at 85% fuzzy match," and similarity doesn't have a meaningful 85% mark. We're using the wrong instrument.

A SequenceMatcher-based fuzzy score returns a clean number with a calibrated threshold. So would Jaro-Winkler, token-set ratio, a learned matcher trained on aliasing patterns, or an LLM specifically prompted to score name similarity. All of those are *tools*. None of them are *retrievers*.

This diagnostic exposes the broader truth: **Gen 1's hammer is similarity. It will reach for similarity even when similarity is the wrong instrument.** The Gen 3 fix is not to add a tool to Gen 1; it is to give the agent multiple tools and let it choose. Hour 11.

## 6. The diagnostic matrix

The summary table in the notebook is the single artefact most worth taking away from the hour. To restate:

|  | D1: multi-hop | D2: aggregation | D3: alias match |
|---|---|---|---|
| Gen 1 | Partial (lucky data) | Misses cross-link | Wrong instrument |
| Gen 2 | Cypher walks the chain | Set semantics natural | Still needs fuzzy operator |
| Gen 3 | Decompose + verify | Routes to graph | Routes to fuzzy-match tool |

Reading this table from left to right is the *architectural arc* of this tutorial. The next nine hours fill in the right two columns.

## 7. The honest counter-point

Gen 1 is excellent at:

- Policy and regulation lookup.
- Definition retrieval.
- Boilerplate retrieval.
- Discoverability ("where in the documents is X discussed?").
- Speed and cost.

A control-manager platform will route many query classes to Gen 1 and *not* lose by it. The mistake is using Gen 1 for query classes whose failure modes are the ones in this hour. Hour 12 builds the routing.

## 8. What to take away from Hour 3

- Three structural failure classes: multi-hop, aggregation, alias. Recognise them in your own system by their *shape*, not their content.
- Gen 1's failure on D1 and D2 is *because* retrieval is similarity. It cannot be fixed without changing the data model. That motivates Gen 2.
- Gen 1's failure on D3 is *because* the wrong instrument was reached for. That motivates Gen 3 (tool use within an agent).
- Gen 1 is not dead. It is the right tool for similarity-shaped queries — which is many of them, especially the cheap, fast, high-volume ones a control manager runs all day.
