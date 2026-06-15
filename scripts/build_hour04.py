"""Build notebooks/hour04_kg_foundations.ipynb — Gen 2 design hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 4 — Knowledge Graph foundations

> *60 minutes dense, 2–3 hours to absorb. The most opinionated hour of the tutorial. You will design the ontology you'll use for the next three hours, learn just enough Cypher to follow Hours 5–6, and end with a working NetworkX visualization of the Lotus structural graph — no Neo4j required yet (Hour 5 loads it).*

**Reading companion:** [`docs/hour04.md`](../docs/hour04.md). **Domain primer:** [`docs/kyc_ubo_primer.html`](../docs/kyc_ubo_primer.html).

The hour is structured around three questions: *(a) what is a KG, structurally?*  *(b) what does a good ontology look like for KYC + UBO?* and *(c) what is the minimum query language you need to actually use one?*
"""),
    ("code", """\
from kg_tutorial import config, llm, display
from kg_tutorial.data import load
from kg_tutorial.graph import bundle_to_networkx, lotus_subgraph, draw_graph, networkx_to_text

config.verify()
bundle = load.load()
print(f"Dataset: {bundle.stats()}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. What is a knowledge graph, structurally?

A knowledge graph is a graph in the formal sense — a set of **nodes** and a set of **edges between them** — where both the nodes and the edges carry **types** and **properties**. The difference between "a graph database" and "a knowledge graph" is exactly that nodes and edges are typed and that types correspond to concepts a domain expert would recognise.

Two dominant families:

| Family | Concrete | What edges look like | Typical store |
|---|---|---|---|
| **Labeled Property Graphs (LPG)** | Neo4j, Memgraph, ArangoDB | Edges have a type and arbitrary properties. Nodes have labels and properties. | Cypher / Gremlin |
| **RDF (Resource Description Framework)** | GraphDB, Stardog, Virtuoso | Edges are typed by an IRI (URL). Properties on edges require *reification*. | SPARQL |

LPG is the *engineering-pragmatic* answer; RDF is the *formal-semantics-pragmatic* answer. RDF was the W3C bet on semantic interop across the web; LPG was the database industry's bet on making graphs fast and convenient at the application layer. **For an in-house control-manager platform, LPG is almost always the right call** — the data is yours, the model is yours, the tradeoff that RDF wins (semantic interchange) doesn't pay off. We use Neo4j.

(We will return to RDF in §6 because the academic-frontier papers on KG foundation models — ULTRA, GAMMA — assume RDF-style triples. The conceptual mapping is straightforward.)
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. A toy KG to introduce the shape

Three nodes, two edges. Look at this drawing before you read the rest of the hour — it's the simplest object you'll encounter and the entire ontology design problem is about scaling it without losing legibility.
"""),
    ("code", """\
import networkx as nx
toy = nx.MultiDiGraph()
toy.add_node("p_john", label="Person", name="John Q. Public")
toy.add_node("e_acme", label="LegalEntity", name="ACME Holdings", jurisdiction="KY")
toy.add_node("e_alphabeta", label="LegalEntity", name="AlphaBeta Trading", jurisdiction="PA")
toy.add_edge("p_john", "e_acme", type="UBO", ownership_pct=50)
toy.add_edge("e_acme", "e_alphabeta", type="Parent", ownership_pct=100)
draw_graph(toy, title="A toy KG — three nodes, two edges", layout="circular")
"""),
    ("md", """\
**Observe four things** about even this trivial graph:

1. **Nodes have a label** (`Person`, `LegalEntity`). The label is the type. The query language uses labels to filter.
2. **Edges have a type** (`UBO`, `Parent`). The edge type is the relationship name. Same query-language role as the label.
3. **Edges carry properties** (`ownership_pct=50`). This is the LPG superpower; in RDF, attributes on relationships require reification (extra triples) and the model loses crispness.
4. **The graph is directed.** "John controls ACME" is not the same statement as "ACME controls John." The directionality is *the* representation of the asymmetry that makes UBO a graph problem.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Ontology — what it is, why it matters

An *ontology* is, for our purposes, **a written-down list of the entity types and relation types that the graph is allowed to contain, plus their attributes and constraints**.

You can run a graph database without an ontology. People do — the graph then becomes a heap. The reason to invest in an ontology, especially for a regulated domain like KYC, is *governance*: a control manager auditing a decision must be able to point at the rule that says "every customer must have a UBO chain that terminates in a natural person." That rule is an ontology constraint. It is also what a downstream LLM agent will read to understand what edges and labels exist (Hour 6 text-to-Cypher).

### FIBO

For financial services, there is a well-developed and freely available ontology: **FIBO** — the Financial Industry Business Ontology, maintained by the EDM Council. FIBO defines, in formal OWL, classes for `Person`, `FinancialInstitution`, `Account`, `OwnershipControl`, `LegalEntity`, `Jurisdiction`, and several hundred more.

**Should you use FIBO directly?** Almost certainly not. FIBO is comprehensive — meaning it has thousands of classes most of which you don't need. The right pattern is to **borrow vocabulary from FIBO where it teaches a useful distinction** (you'll use "LegalEntity" not "Company" because FIBO is right that a trust isn't a company), and design the rest minimally.

### Schema-strict vs schema-flexible

There is a long-running debate in the KG community between *schema-strict* (the ontology is enforced; nothing else can be inserted) and *schema-flexible* (any property is allowed; the ontology is documentation). Neo4j is schema-flexible by default; you can enforce more with constraints.

For a control-management platform, **schema-strict is the right default**: a malformed insert in this domain is a data quality bug that produces wrong UBO chains. Hour 5 enforces ours by writing through a single typed loader.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Designing the Lotus ontology

We've already designed it implicitly — `kg_tutorial.data.schema` contains the Pydantic models that *are* the ontology. Let's make the implicit design explicit.

### Entity types (node labels)

| Label | What it represents | Key attributes |
|---|---|---|
| `Person` | A natural person | `full_name`, `is_pep`, `pep_reason`, `residence_country`, `nationalities` |
| `LegalEntity` | A non-natural legal person | `legal_name`, `jurisdiction`, `entity_type`, `registration_number` |
| `Account` | A bank account | `account_number`, `status`, `currency` |
| `Deposit` | A single inbound transaction | `amount_eur`, `value_date`, `counterparty_name`, `purpose_code` |
| `SanctionsRecord` | An entry on a sanctions list | `name`, `aliases`, `list_source`, `country`, `reason` |
| `AdverseMediaItem` | A news snippet | `headline`, `snippet`, `source_outlet`, `sentiment` |

### Relation types (edge labels)

| Relation | Direction | Properties | Purpose |
|---|---|---|---|
| `:CONTROLS` | Person/LegalEntity → LegalEntity | `control_type` (UBO/Director/Parent/POA), `ownership_pct`, `source` | UBO tracing |
| `:HOLDS` | LegalEntity → Account | — | Account ownership |
| `:DEPOSITS_TO` | Deposit → Account | — | Inbound flow |
| `:MENTIONS` | AdverseMediaItem → Person/LegalEntity | — | Adverse media linkage |

**Two design decisions worth pausing on.**
"""),
    # ------------------------------------------------------------------
    ("md", """\
### Decision 1: `UBO` as a *control_type property* on `:CONTROLS`, not as its own edge

The naive design has separate edges: `:UBO`, `:DIRECTOR`, `:PARENT`, `:POA`, `:SHAREHOLDER`. We collapsed them into one `:CONTROLS` edge with a `control_type` property. Three reasons:

1. **Cypher locality.** "All entities X controls, regardless of how" is one pattern: `MATCH (X)-[:CONTROLS]->(e)`. With separate edge types you'd need `[:UBO|DIRECTOR|PARENT|POA|SHAREHOLDER]`.
2. **Reasoning about totality.** A person might be both a UBO and a director of the same entity. Two edges of different types is fine; one edge with both properties is messier. We chose two edges.
3. **The mistake people make.** Modeling `ownership_pct` as a *node property* on the entity rather than an *edge property*. Ownership is a relationship attribute (depends on who is being owned by whom and through which control type), not an entity attribute. **Always model attributes that depend on a pair on the edge, not on the node.**

### Decision 2: `Deposit` is a *node*, not a binary edge

The "natural" graph encoding of a deposit is an edge: `Counterparty --DEPOSITS--> Account`. But a deposit has many participants: source-of-funds entity, originating bank, beneficiary, value date, jurisdiction, purpose code, narrative. Binary edges carry properties but they don't carry *participants*. We promoted Deposit to a node.

Hour 10 takes this further — modeling a deposit as a **hyperedge** that connects all participants at once. That reframing is what hypergraphs buy you.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. Build the Lotus structural graph

Now load the synthetic data into a NetworkX graph and visualize the Lotus chain. No Neo4j yet — that's Hour 5. The point here is to see the structure.
"""),
    ("code", """\
G = bundle_to_networkx(bundle)
print(f"Full graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print()
print("Node labels:")
from collections import Counter
labels = Counter(d.get("label") for _, d in G.nodes(data=True))
for lbl, n in labels.most_common():
    print(f"  {lbl:>18}: {n}")
print()
print("Edge types:")
edge_types = Counter(d.get("type") for _, _, d in G.edges(data=True))
for et, n in edge_types.most_common():
    print(f"  {et:>18}: {n}")
"""),
    ("md", """\
Most of the graph is noise (legitimate-looking companies, persons, sanctions entries). The Lotus case is 12 nodes. Let's draw just those.
"""),
    ("code", """\
sub = lotus_subgraph(G)
print(f"Lotus subgraph: {sub.number_of_nodes()} nodes, {sub.number_of_edges()} edges")
draw_graph(sub, title="The Lotus case as a knowledge graph", figsize=(13, 9))
"""),
    ("md", """\
**Read the drawing carefully.**

- The vertical ownership chain on the right: John → ACME → AlphaBeta → Gamma — the regulatory UBO question.
- The diagonal edge from John to Atlas Wirecorp: John's directorship is the **cross-link** Gen 1 failed to surface.
- The Deposit node connects to the Account but its counterparty name is a property — the sanctions linkage is *not* an edge in this base graph because the alias match hasn't been resolved.
- Adverse media → John and ACME: a secondary source you can corroborate with.

A human reading this graph can answer the Lotus question in 30 seconds. A KG retrieval system that walks these edges can, too. **That is the entire promise of Gen 2.** The question for Hour 5 is: how does this graph get built?
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. Cypher in the next 10 minutes

Cypher is Neo4j's query language. You will see a lot of it in Hours 5–6. This is the minimum to follow along; the [Cypher manual](https://neo4j.com/docs/cypher-manual/current/) has the rest when you need it.

### The five idioms you'll see

```cypher
// 1. Find nodes of a label
MATCH (p:Person)
RETURN p.full_name

// 2. Find connected nodes
MATCH (p:Person)-[:CONTROLS]->(e:LegalEntity)
RETURN p.full_name, e.legal_name

// 3. Multi-hop traversal — variable-length paths
MATCH (root:LegalEntity {id: 'e_gamma_ops'})<-[:CONTROLS*1..5]-(controller)
RETURN controller

// 4. Filter on properties
MATCH (e:LegalEntity)
WHERE e.jurisdiction IN ['KY', 'PA', 'LI', 'BVI']
RETURN e.legal_name, e.jurisdiction

// 5. Aggregate
MATCH (p:Person)-[r:CONTROLS]->(e:LegalEntity)
WHERE p.is_pep = true
RETURN p.full_name, count(e) AS n_entities
ORDER BY n_entities DESC
```

### The two ideas that matter most

1. **Patterns.** Cypher's query model is "match this graph pattern." You write the shape and the engine finds all subgraphs that fit. This is fundamentally different from SQL's "join these tables on these columns."
2. **Variable-length paths** (`*1..5`). The single most consequential thing Cypher does that SQL can't reasonably do. It traverses 1 to 5 hops along any path of matching edges and returns all of them. **This is the operator that solves multi-hop UBO chains in one query.**

That's it for syntax — the rest is detail. Hour 6 builds queries over Lotus.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. Where this strains

KGs are powerful. They are not free. Five strains worth knowing about now:

1. **Schema drift.** A new regulation introduces a new entity type — say, "Trust Protector." Adding to the ontology, updating extractors, updating queries, and backfilling are all real work.
2. **Crisp matching only.** `MATCH (s:SanctionsRecord {name: 'ATLAS WIRECORP'})` returns nothing because the list entry is `'ATLAS WIRE CORPORATION'`. Cypher's `=` is character-by-character. Fuzzy match requires custom operators or — more practically — an external tool the agent calls. (Hour 7.)
3. **Temporal reasoning.** Our edges have `effective_from` properties but Cypher doesn't have first-class temporal semantics. "Who was the UBO on 5 March 2024?" requires hand-written date arithmetic. TIE and other temporal-KG papers address this. (Hour 7.)
4. **Construction cost.** Building a high-quality KG from documents is *the* engineering problem in Gen 2. Hour 5 demonstrates the cost.
5. **Reasoning lives outside the KG.** The KG retrieves; the LLM reasons. Cypher cannot answer "is this customer high-risk?" — it answers "what is the structure?" The reasoning is in the next layer, and the next layer is fallible.

A useful framing: **the KG is precision; the LLM is interpretation. Gen 2 systems fail when teams ask the KG to interpret or the LLM to be precise.**
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 8. Frontier — where KG research is heading

Two threads worth knowing about, both showing up in the user's reference papers:

### KG foundation models — ULTRA and GAMMA

The most striking recent development in KG research is the discovery that you can pre-train a single model that does inductive link prediction on **any** KG, with **any** entity and relation vocabulary, *without seeing those vocabularies in training*. **ULTRA** (ICLR 2024, Galkin et al.) and its follow-on **GAMMA** (Xin et al., 2025) build representations of *relations* rather than of *entities* — relations are typed by their interactions with other relations, which transfers across graphs.

What this means practically: the dream of "drop a fresh KG in and let a foundation model reason over it" has gone from hand-wave to working result. For control management this is on the horizon for tasks like "predict which UBO declarations are likely to be incomplete given the structural pattern of declarations from this jurisdiction." Hour 7 returns to this.

### Temporal KG completion — TIE

Real-world KGs change over time. A naive system rebuilt every night is expensive and forgets nothing it should remember. **TIE** (Wu et al.) introduces incremental embedding updates that retain old knowledge while incorporating new — without catastrophic forgetting. For sanctions screening, where lists update daily, this is the relevant production direction.

These are signposts. The next four hours implement the classical stack; revisit them after Hour 12 when you understand what the classical stack does not solve.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 9. Save the design for Hour 5

The ontology we just designed lives in `kg_tutorial.data.schema`. Hour 5 imports it and uses it as the *target schema* for both the spaCy NER baseline and the Claude-based extractor.

Print a quick checklist of the design — make sure you can describe each row from memory before moving on.
"""),
    ("code", """\
checklist = [
    "Node labels: Person, LegalEntity, Account, Deposit, SanctionsRecord, AdverseMediaItem",
    "Edge types: CONTROLS, HOLDS, DEPOSITS_TO, MENTIONS",
    "CONTROLS carries 'control_type' (UBO/Director/Parent/POA/Shareholder) and 'ownership_pct'",
    "Direction always: controller → controlled",
    "Deposit is a node (not an edge) — Hour 10 promotes it further to a hyperedge",
    "Sanctions matching is NOT modelled as an edge — it's a fuzzy match (Hour 7)",
]
for i, item in enumerate(checklist, 1):
    print(f"  {i}. {item}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 5

Three questions:

1. **In your own platform, what is the *minimum* ontology that would let you answer 80% of control-manager queries?** Aim for 6–8 node labels, 4–6 relation types. The instinct is to model everything; the discipline is to model less and add when justified.
2. **Where would FIBO's vocabulary teach you a distinction your current schema doesn't make?** (`LegalEntity` vs `FinancialInstitution`, `OwnershipControl` vs `ContractualControl`.)
3. **What is the *single* most common shape of query a control manager would write?** If it's multi-hop traversal, you're in Gen 2 territory. If it's "find similar text," you're still in Gen 1.

Next: [Hour 5 — KG construction](./hour05_kg_construction.ipynb). You'll build the Lotus KG two ways (structured load + extraction) and compare. **Neo4j Desktop is required from this hour onwards** — make sure it's started before you begin.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour04_kg_foundations.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
