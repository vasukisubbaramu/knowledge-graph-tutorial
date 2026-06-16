# Hour 10 — Gen 3: Hypergraphs

A reading companion to `notebooks/hour10_hypergraphs.ipynb`.

> **One-line frame for the hour.** *A hypergraph is the natural representation of a transaction — a single n-ary relation that connects all participants of an event at once. Reach for hypergraphs when "what was involved in this event" is the dominant query.*

## 1. The limit of binary edges

A binary edge has exactly two endpoints. It's a perfect representation of "John controls ACME" — one relation, two participants.

It is not a clean representation of "this deposit happened." A deposit involves at least:

- Originating entity
- Beneficiary account
- Amount (in a currency)
- Origin jurisdiction
- Destination jurisdiction
- Value date
- Purpose code
- Source-of-funds narrative
- Originating bank

Modeling as binary edges fragments the joint structure. You typically end up with a *promoted relationship* — a node (`Deposit_node`) that exists only to hold the relation, with binary edges connecting it to each participant. This is **reification**. It works, but every query over "the deposit's participants" requires multiple joins and the joint identity of the event is implicit.

A **hyperedge** is the direct fix: a single typed relation connecting all participants at once, with the relation itself carrying properties.

## 2. The Lotus deposit as a hyperedge

In code:

```python
Hyperedge(
    id="dep_001",
    type="Deposit",
    roles={
        "originator": "e_atlas_wirecorp",
        "beneficiary_account": "a_gamma_001",
        "jurisdiction_origin": "AE",
        "jurisdiction_destination": "LI",
        "currency": "EUR",
        "purpose_code": "INTC",
    },
    properties={"amount_eur": 500_000.0, "value_date": "2026-06-03"},
)
```

One hyperedge. Six participants. Each in a named role. Properties on the relation itself.

The key innovation over reification is **roles**. A hyperedge knows not just *who participates* but *in what capacity*. "Atlas Wirecorp is the originator" is structurally different from "Atlas Wirecorp is the beneficiary." Binary edges with a `Deposit_node` can encode this via the edge type name (`has_originator`, `has_beneficiary`), but the query language can't reason about roles as first-class objects.

## 3. What becomes easy

Three queries that hypergraphs make direct:

**Q1 — "All hyperedges where Atlas Wirecorp is the originator (specifically)."**
One filter on the role. Reified-binary equivalent: traverse from Atlas → its `has_originator`-typed outbound edges → the `Deposit_node` at the other end.

**Q2 — "All deposits where the destination jurisdiction is Liechtenstein."**
One role filter. Reified equivalent: a join across the deposit-node and the jurisdiction-node, filtered.

**Q3 — "All entities that share at least one hyperedge with the Gamma account."**
A direct sweep over hyperedges containing the account. Reified equivalent: traverse from the account through its deposit-nodes to the non-account participants.

The hypergraph collapses chains. In a reified-binary model these queries are possible but contorted; the contortion costs developer attention, query performance, and clarity for downstream consumers.

## 4. When to reach for hypergraphs (the practical test)

Three honest questions:

1. **Do your most interesting relations have more than 2 participants?** Deposits do. Trades do. Alerts that involve multiple flagged entities do. UBO ownership does not.
2. **Do you frequently query "everything involved in this event"?** Transaction monitoring yes. Customer-master queries no.
3. **Do role-based queries dominate?** "All hyperedges where X is in role Y" — common in transaction work. Less common in static reference data.

Two of three yes → hypergraphs earn their keep.

A reasonable rule: **start with the binary/reified model in Neo4j (or any LPG store), promote to hypergraph in modelling when joint queries get hard.** You almost never need to change storage — you change how you *query*.

## 5. Storage vs modelling

Most LPG databases — Neo4j included — do not have native hyperedge support. They emulate via reification. Native hypergraph stores exist (some RDF stores; specialist research databases) but are uncommon in financial services.

The practical pattern:

- **Modelling.** Think in hyperedges. Document them in your ontology with named roles.
- **Storage.** Reify. Each hyperedge becomes a node with typed edges to participants. The node's type encodes the relation type; each edge encodes one role.
- **Query.** Build a small DSL — or a query helper module — that lets you write "find hyperedges where role X is Y" and translates to the reified Cypher.

`kg_tutorial.hyper.Hypergraph` is the in-memory version of that DSL. Production would back it with Neo4j.

## 6. HyperGraphRAG

Recent work demonstrates retrieval over hypergraphs for question answering, using hyperedge-level embeddings (an embedding of the whole n-ary fact) rather than node-level embeddings.

The retrieval question becomes "which hyperedges are most relevant to the query," not "which nodes are most similar." For transaction-shaped questions this dramatically reduces retrieval noise — you don't get back fragments that need to be re-joined; you get back the whole event.

The implementation work is in the embedding step:

- *Surface-form embedding.* Concatenate the participants' names and embed. Simple, surprisingly effective.
- *Learned joint embedding.* Train on triples (hyperedge, query, relevance). Better quality, more engineering.
- *LLM-generated summary embedding.* Have the LLM produce a natural-language summary of each hyperedge, embed the summary.

We don't implement HyperGraphRAG in the tutorial. The conceptual sketch is enough to recognise the pattern.

## 7. The cost of hypergraphs

Two real costs:

- **Modeller cognitive load.** Hyperedges with named roles require disciplined naming and a richer ontology. The team has to learn.
- **Tool support is patchier.** Visualisations, query languages, and standard libraries assume binary edges. Hypergraph tooling exists but is less mature.

These costs are why most production teams reach for hypergraphs only when the joint-query pattern dominates. For static reference data, binary edges remain the right default.

## 8. What to take away from Hour 10

- The conceptual difference between binary edges + reification and native hyperedges.
- The Lotus deposit as a worked example of n-ary structure.
- The three honest tests for whether your domain wants hypergraphs.
- The storage-vs-modelling pattern: model as hyperedges, store as reified-binary, query via a small DSL.
- HyperGraphRAG as the research direction for hypergraph-aware retrieval — and why we don't implement it here.
