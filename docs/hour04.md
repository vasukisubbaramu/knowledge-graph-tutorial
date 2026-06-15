# Hour 4 — Knowledge Graph foundations

A reading companion to `notebooks/hour04_kg_foundations.ipynb`.

> **One-line frame for the hour.** *A knowledge graph is not a database choice; it is a commitment to model the relationships in your domain as first-class objects with their own types, attributes, and constraints — and then to query them through that structure.*

## 1. The shape of a knowledge graph

A knowledge graph is, formally, a graph in the discrete-math sense — a set of nodes and a set of edges between them — with two crucial extensions:

- Both nodes and edges carry **types** drawn from a controlled vocabulary called the *ontology*.
- Both nodes and edges carry **properties** — arbitrary key-value pairs attached to specific instances.

The reason knowledge graphs exist as a distinct category from "a graph stored in a database" is precisely those two extensions. A property graph database can store arbitrary graphs; a *knowledge graph* commits to a meaningful schema where types correspond to concepts a domain expert recognises.

For our purposes there are two practical families:

- **Labeled Property Graphs (LPG).** Nodes have labels; edges have a type plus arbitrary properties. Neo4j is the canonical example. Cypher is the query language. This is the engineering-pragmatic family.
- **RDF** (Resource Description Framework). Edges are typed by URIs. Properties on edges require reification — extra triples that model the edge as a node so it can have its own attributes. SPARQL is the query language. This is the formal-semantics-pragmatic family.

For an in-house platform — control-management, compliance, fraud — LPG is the right default. The case for RDF is semantic interoperability across organisations and the open web, which is not the problem you have at a bank. Use LPG; specifically, use Neo4j.

## 2. Ontology

An ontology is, for our purposes, **a written-down list of the entity types and relation types the graph is allowed to contain, plus their attributes and constraints**.

You can run a graph database without an ontology — and people do. The graph then becomes a heap. The reason to invest in an ontology, especially for a regulated domain, is **governance**: a control manager must be able to point at a rule — "every customer must have a UBO chain that terminates in a natural person" — and that rule must be encoded somewhere other than tribal knowledge. The ontology is where.

A secondary benefit, which becomes load-bearing in Hour 6, is that **an LLM reading the ontology in a prompt knows what queries are valid**. Text-to-Cypher only works if the model knows the schema. Schema-free retrieval over an unknown graph fails frequently and silently.

### FIBO

The Financial Industry Business Ontology (FIBO), maintained by the EDM Council, is a free, open, OWL-formalised ontology for financial services. It defines `Person`, `LegalEntity`, `Account`, `OwnershipControl`, `Jurisdiction`, and several thousand more classes. FIBO is the *reference* ontology for the domain.

Should you adopt FIBO directly for an in-house platform? Almost certainly not. FIBO is large; you need a small fraction. The right pattern is to **borrow vocabulary from FIBO where it teaches a distinction** ("LegalEntity" not "Company" — because FIBO is right that a trust isn't a company), and design the rest minimally.

### Schema-strict vs schema-flexible

There is a long-running debate between *schema-strict* — the ontology is enforced, nothing else can be inserted — and *schema-flexible* — any property is allowed, the ontology is documentation. Neo4j is schema-flexible by default; you can tighten it with constraints.

For a control-management platform, **schema-strict is the right default**. A malformed insert in this domain is a data-quality bug that produces wrong UBO chains. Hour 5 enforces strictness by writing through a single typed loader.

## 3. The Lotus ontology in concrete

The notebook walks through the ontology design in detail. The short version:

**Node labels.** `Person`, `LegalEntity`, `Account`, `Deposit`, `SanctionsRecord`, `AdverseMediaItem`.

**Edge types.** `:CONTROLS` (with a `control_type` property — UBO/Director/Parent/POA/Shareholder), `:HOLDS`, `:DEPOSITS_TO`, `:MENTIONS`.

Two design decisions worth absorbing because they are general:

1. **Collapse related edge types into one, with a discriminator property, when you frequently want to ask "any kind of."** Cypher `(p)-[:CONTROLS]->(e)` matches any kind of control. With separate edge types you'd write `[:UBO|DIRECTOR|PARENT|POA|SHAREHOLDER]` — verbose and forgetful.

2. **Model attributes that depend on a *pair* on the edge, not on the node.** `ownership_pct` is an edge property because the same person can own different percentages of different entities. Putting it on the node would be wrong.

3. **Promote n-ary relationships to nodes — and eventually to hyperedges.** A `Deposit` is a node because it has several participants (account, counterparty, jurisdiction, time, amount, purpose). Binary edges can carry properties but not participants. Hour 10 extends this to hyperedges where the deposit *is* a single relationship across all participants.

## 4. Cypher in the minimum

Cypher is Neo4j's query language. Five idioms cover almost everything you'll see in this tutorial:

```cypher
// 1. Find nodes of a label
MATCH (p:Person) RETURN p.full_name

// 2. Find connected nodes
MATCH (p:Person)-[:CONTROLS]->(e:LegalEntity) RETURN p.full_name, e.legal_name

// 3. Multi-hop traversal — variable-length paths
MATCH (root:LegalEntity {id: 'e_gamma_ops'})<-[:CONTROLS*1..5]-(controller)
RETURN controller

// 4. Filter on properties
MATCH (e:LegalEntity) WHERE e.jurisdiction IN ['KY', 'PA', 'LI']
RETURN e.legal_name

// 5. Aggregate
MATCH (p:Person)-[r:CONTROLS]->(e:LegalEntity)
WHERE p.is_pep = true
RETURN p.full_name, count(e) AS n_entities ORDER BY n_entities DESC
```

The two ideas that matter most:

- **Patterns.** Cypher's query model is "match this graph pattern." You write the *shape* you're looking for and the engine finds all subgraphs that fit it. This is fundamentally different from SQL's "join these tables on these columns."
- **Variable-length paths** (`*1..5`). The single most consequential thing Cypher does that SQL can't reasonably do. Traverses 1 to N hops along matching edges and returns all of them. This is the operator that solves multi-hop UBO chains in one query.

## 5. Where this strains

KGs are powerful and not free. Five strains:

1. **Schema drift.** New regulations bring new entity types. Each addition is real work — extractors, queries, backfill.
2. **Crisp matching only.** Cypher `=` is character-by-character. Fuzzy matching is a *tool* called from outside Cypher; Hour 7 builds it.
3. **No first-class temporal semantics.** "Who was the UBO on 5 March 2024?" requires hand-written date arithmetic. TIE and similar temporal-KG approaches address this; we don't.
4. **Construction cost.** Building a high-quality KG from documents is the engineering problem in Gen 2. Hour 5 demonstrates the cost in detail.
5. **Reasoning lives outside the KG.** The KG retrieves; the LLM reasons. The KG cannot tell you "is this customer high-risk" — only "what is the structure." The reasoning is the next layer and the next layer is fallible.

A useful framing: **the KG is precision; the LLM is interpretation. Gen 2 systems fail when teams ask the KG to interpret or the LLM to be precise.**

## 6. Frontier — where KG research is heading

Two threads worth naming because they recur:

- **KG foundation models (ULTRA, GAMMA).** A pre-trained model that does inductive link prediction on *any* KG, with *any* entity and relation vocabulary, *without seeing those vocabularies in training*. The trick is to represent relations by their interactions rather than by their identity. Practically: "drop a fresh KG in and let a foundation model reason over it" has gone from hand-wave to working result. For control management this is on the horizon for tasks like "predict which UBO declarations are likely to be incomplete given the structural pattern of declarations from this jurisdiction."

- **Temporal KG completion (TIE).** Real-world KGs are temporal — ownership changes, listings expire, sanctions update daily. TIE introduces incremental embedding updates that retain old knowledge while incorporating new, without catastrophic forgetting. For sanctions screening this is the relevant production direction.

These are signposts. The classical stack we build in Hours 5-11 is the production reality today; these are the next frontier.

## 7. What to take away from Hour 4

- A working mental model of LPG vs RDF, with a clear reason to use LPG (Neo4j) for in-house platforms.
- An understanding of what an ontology is, and why it is *governance* before it is engineering.
- The Lotus ontology in your head — 6 node labels, 4 edge types — and the two design decisions (collapse related edges, edge properties not node properties).
- Cypher's five idioms and the variable-length path operator as the key power.
- The five strains, and which are addressed by Hours 7-11 vs which sit on the research frontier.
