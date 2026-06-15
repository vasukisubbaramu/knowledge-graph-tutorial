"""Build notebooks/hour05_kg_construction.ipynb — Gen 2 build hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 5 — Gen 2: KG construction

> *60 minutes dense, 2–3 hours to absorb. You will build the Lotus knowledge graph in Neo4j two different ways — once from the structured Pydantic data (the easy path) and once by extracting from the unstructured documents (the production reality). The compare-and-contrast is the lesson.*

**Reading companion:** [`docs/hour05.md`](../docs/hour05.md).

**Prerequisite:** Neo4j Desktop is installed, the local DBMS is running, and the password in `.env` matches. If `hour00_setup.ipynb`'s Neo4j check printed `Neo4j is up. Current node count: 0`, you're good.
"""),
    ("code", """\
from kg_tutorial import config, llm, display
from kg_tutorial.data import load
from kg_tutorial.graph import GraphDB, bundle_to_networkx, lotus_subgraph, draw_graph
from kg_tutorial.extract import spacy_extract, claude_extract, reconcile_to_canonical

config.verify()
bundle = load.load()

db = GraphDB()
print(f"Neo4j connected at {config.NEO4J_URI}")
print(f"Current state: {db.count_by_label() or 'empty'}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. Two paths to the same graph

Production KGs are built one of three ways:

| Path | When you use it | Cost | Reliability |
|---|---|---|---|
| **Structured load** | The source is a database / API with known schema | Cheap | High |
| **Schema-guided extraction** | The source is unstructured text with a known ontology | Medium | Medium |
| **Schema-free extraction** | The source is unstructured text and the ontology is being learned | High | Variable |

We will do the first two on the same data and compare. The third (Microsoft GraphRAG style — communities and summaries) is sketched at the end.

The point of doing it twice is **not** that one is "the right way" — production KGs blend both. Structured sources (registry feeds, internal master data) load directly. Unstructured sources (memos, correspondence, news) extract. The two graphs are then *reconciled* — and that reconciliation is where most of the engineering effort actually goes.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Path A — structured load

The synthetic dataset already *is* the canonical truth. We have Pydantic models, we have a populated `DatasetBundle`. The Lotus chain is already coherent. Load it.
"""),
    ("code", """\
db.reset()  # start clean
db.load_bundle(bundle)
print("Loaded. Counts by label:")
for label, n in db.count_by_label().items():
    print(f"  {label:>20}: {n}")
"""),
    ("md", """\
Open Neo4j Browser (the Neo4j Desktop opens it with one click). Run this in the Browser:

```cypher
MATCH (p:Person {id: 'p_john_q_public'})-[:CONTROLS*1..4]-(e)
RETURN p, e
```

You should see the Lotus chain rendered visually. Or run the same query here:
"""),
    ("code", """\
rows = db.query(\"\"\"
MATCH (p:Person {id: 'p_john_q_public'})-[r:CONTROLS]->(e:LegalEntity)
RETURN p.full_name AS person, type(r) AS rel, r.control_type AS type, r.ownership_pct AS pct, e.legal_name AS entity, e.jurisdiction AS juris
\"\"\")
for r in rows:
    pct = f" ({r['pct']:.0f}%)" if r['pct'] is not None else ""
    print(f"  {r['person']} --{r['type']}{pct}--> {r['entity']} ({r['juris']})")
"""),
    ("md", """\
You should see John controlling ACME (UBO 50%) **and** Atlas Wirecorp (Director). **That second edge — the cross-link Gen 1 failed to surface — is now first-class.** Walking from John reaches both entities in one query.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Path B — extraction from documents

Now the realistic case. Imagine we did *not* have the canonical Pydantic data. We have only the 7 unstructured documents. Can we build the same graph?

We try two extractors:

- **spaCy NER baseline.** Out-of-the-box, no domain training.
- **Claude with the ontology as a system prompt.** Schema-guided.

For each document, we run the extractor, count what was found, and (after both) load into a *separate* Neo4j graph so we can compare to Path A.
"""),
    ("code", """\
# Pick the CDD form — the densest document — for first inspection
cdd = next(d for d in bundle.documents if d.id == "d_cdd_gamma_ops")
print(f"Document: {cdd.title}")
print(f"Length: {len(cdd.body)} chars")
"""),
    # spaCy
    ("md", """\
### Path B1 — spaCy NER baseline
"""),
    ("code", """\
spacy_result = spacy_extract(cdd.body)
print(f"spaCy found {len(spacy_result.entities)} entities, {len(spacy_result.relations)} relations.")
print()
print("First 15 entities (surface, type):")
for e in spacy_result.entities[:15]:
    print(f"  {e.surface:>40}  [{e.entity_type}]")
"""),
    ("md", """\
**Inspect the output.** spaCy will reliably find:

- PERSON: John Q. Public, Maria Rossi, Alice Public
- ORG: AlphaBeta Trading SA, ACME Holdings Ltd, Gamma Operations GmbH
- GPE: Monaco, Liechtenstein, Cayman Islands, Panama
- DATE / MONEY / PERCENT spans

It will *not* find:

- "UBO" — not a named entity type
- "PEP-relative" — same
- The relationship that John is a UBO of ACME (no relation extraction)
- The relationship that AlphaBeta is a 75% parent of Gamma (no relations)

This is the baseline. **It's not bad** — for free, with no training, you get 80% of the entity surface. It's just not enough for KYC.
"""),
    # Claude
    ("md", """\
### Path B2 — Claude schema-guided extraction

We give Claude the ontology (entity types + relation types) and ask for both entities *and* relations, in JSON.

(One Claude call. ~10 seconds. About \\$0.01 on Sonnet.)
"""),
    ("code", """\
claude_result = claude_extract(cdd.body)
print(f"Claude found {len(claude_result.entities)} entities, {len(claude_result.relations)} relations.")
print()
print("ENTITIES (first 15):")
for e in claude_result.entities[:15]:
    print(f"  {e.surface:>40}  [{e.entity_type}]")
print()
print("RELATIONS:")
for r in claude_result.relations:
    props = f"  {r.properties}" if r.properties else ""
    print(f"  ({r.head_surface}) --[{r.relation}]--> ({r.tail_surface}){props}")
"""),
    ("md", """\
**Inspect the relations.** Claude will extract things like:

- `(John Q. Public) --[UBO {percent: 50}]--> (ACME Holdings Ltd)`
- `(ACME Holdings Ltd) --[PARENT {percent: 100}]--> (AlphaBeta Trading SA)`
- `(Maria Rossi) --[DIRECTOR]--> (Gamma Operations GmbH)`

These are the relationships our ontology defines and they were extracted from prose. **That is what schema-guided LLM extraction buys you over spaCy** — and it is precisely the thing every Gen 2 system depends on.

**Stop and think about what just happened.** We did not train a model. We did not write a relation extractor. We wrote a prompt that included the ontology. Claude obeyed.

This is also where Gen 2's brittleness lives: the extractor will sometimes hallucinate relations (especially `RELATED_TO` between two persons both mentioned in passing), and it will sometimes miss subtle ones. Hour 5's lab is to find one of each, by hand.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Extract from all 7 documents

Run Claude over each document and collect everything. We'll then reconcile and load.
"""),
    ("code", """\
all_extractions = {}
for doc in bundle.documents:
    print(f"Extracting from {doc.title[:60]}...")
    all_extractions[doc.id] = claude_extract(doc.body)

print()
print("Summary:")
for did, r in all_extractions.items():
    print(f"  {did:>30}: {len(r.entities):>3} entities, {len(r.relations):>3} relations")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. Entity resolution — surface forms to canonical IDs

We extracted *surface strings* (`"John Q. Public"`, `"J. Q. Public"`, `"Mr Public"`) — possibly each occurring multiple times in slightly different forms. Before loading into Neo4j we must reconcile each surface to a **canonical id** (`p_john_q_public`).

In production this is a learned entity resolver. For the lab, a SequenceMatcher-based fuzzy match against the known surface forms is sufficient and pedagogically clear.
"""),
    ("code", """\
# Build the candidates list: (canonical_id, [surface forms])
person_candidates = [
    (p.id, [p.full_name] + p.aliases) for p in bundle.persons
]
entity_candidates = [
    (e.id, [e.legal_name] + e.aliases) for e in bundle.entities
]

# Try resolving some example extracted surfaces
samples = ["John Q. Public", "J. Q. Public", "Johnny", "ACME Holdings", "Acme Hldgs", "AlphaBeta Trading SA"]
print("RECONCILIATION TEST:")
for s in samples:
    pid = reconcile_to_canonical(s, person_candidates)
    eid = reconcile_to_canonical(s, entity_candidates)
    best = pid or eid or "(no match)"
    print(f"  {s:>30} -> {best}")
"""),
    ("md", """\
The fuzzy matcher handles most variations cleanly but will fail on extreme aliases (e.g. transliterations). Production systems add learned matchers, blocking, and human-in-the-loop review for low-confidence matches. **The single biggest source of error in production KGs is silent entity-resolution failure** — two different surface forms that should resolve to the same id but don't, creating phantom duplicate nodes.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. Load the extracted graph

We load extraction-derived entities and relations into a *separate* set of nodes labeled with `Extracted` prefixes, so we can compare side-by-side with the canonical graph.
"""),
    ("code", """\
# Wipe the extracted side
db.query("MATCH (n:Extracted) DETACH DELETE n")

# Insert reconciled extractions
inserted_nodes = 0
inserted_edges = 0
for doc_id, result in all_extractions.items():
    # Reconcile each relation head/tail
    for rel in result.relations:
        h_id = reconcile_to_canonical(rel.head_surface, person_candidates + entity_candidates)
        t_id = reconcile_to_canonical(rel.tail_surface, entity_candidates)
        if not (h_id and t_id):
            continue  # unresolvable — skip and log
        # Use Extracted label set so the comparison is clean
        db.query(
            \"\"\"
            MERGE (h:Extracted {id: $h})
            MERGE (t:Extracted {id: $t})
            MERGE (h)-[r:EXTRACTED_REL {type: $rel}]->(t)
            SET r.source_document = $src
            \"\"\",
            {"h": h_id, "t": t_id, "rel": rel.relation, "src": doc_id},
        )
        inserted_edges += 1

print(f"Loaded extraction graph: {inserted_edges} relation edges")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. Compare the two graphs

How does the extraction graph compare to the canonical one? In particular: does the cross-link (John → Atlas Wirecorp directorship) come out?
"""),
    ("code", """\
# Canonical edges from/to John
print("CANONICAL (Path A) — John's outgoing CONTROLS edges:")
rows = db.query(\"\"\"
MATCH (p:Person {id: 'p_john_q_public'})-[r:CONTROLS]->(e:LegalEntity)
RETURN r.control_type AS type, r.ownership_pct AS pct, e.legal_name AS entity
\"\"\")
for r in rows:
    pct = f" ({r['pct']:.0f}%)" if r['pct'] is not None else ""
    print(f"  --{r['type']}{pct}--> {r['entity']}")

print()
print("EXTRACTED (Path B) — what came out of the documents:")
rows = db.query(\"\"\"
MATCH (h:Extracted {id: 'p_john_q_public'})-[r:EXTRACTED_REL]->(t:Extracted)
RETURN r.type AS rel, r.source_document AS src, t.id AS tail
\"\"\")
for r in rows:
    print(f"  --{r['rel']}--> {r['tail']}   [from {r['src']}]")
"""),
    ("md", """\
**Inspect the comparison.** Several things may be true:

- The canonical chain (UBO of ACME, Director of Atlas) is present in both — extraction worked.
- The extracted graph may have *additional* relations the canonical one doesn't — e.g. RELATED_TO Alice Public. That's interesting; the policy treats it as a PEP-relative trigger.
- The extracted graph may be *missing* a fact — e.g. the Atlas directorship if no document mentioned it explicitly. Worth checking by hand which document was the source.

**This is the production reality of Gen 2:** extracted graphs are noisier and looser than canonical ones. The reconciliation pipeline is where you spend the engineering effort. Done well, you get a graph that includes *more* than the structured sources because LLMs can extract subtle relations from prose.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 8. Schema-free extraction — the GraphRAG pattern

For completeness: there's a third pattern — **schema-free extraction** — popularised by Microsoft's GraphRAG. The extractor invents entity types and relations as it goes, then clusters communities and pre-computes summaries at each community level. The result is a graph that you didn't design but that captures the document corpus's own structure.

For KYC, schema-free is the wrong default — regulators want to see a defensible model. But schema-free has a place: **discovery**. Run schema-free over your archive of CDD forms from the last year, see what relation types the extractor finds that weren't in your ontology. The ones that show up frequently are gaps in your ontology.

We won't implement schema-free here; the conceptual sketch is enough.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 9. Where this strains

Three honest limits, all of which Hour 7 (Gen 2's full strain) revisits:

1. **Extractor inconsistency.** Run the same document through Claude twice with the same prompt; relations may shift slightly. Production extraction pipelines use temperature=0, JSON schemas, and (often) majority-vote across multiple calls.
2. **Reconciliation silent failures.** Two surface forms that *should* resolve to the same id but don't, creating phantom duplicate nodes. The cost is later: queries find half the edges.
3. **The cost.** One Claude call per document at ingest time, every time the document changes. For a CDD archive of 100k documents, this is real money. Cache, watermark, and treat the extraction layer like any other ETL pipeline.

**The single most consequential decision in Gen 2 construction is not the extractor — it's the ontology.** A weak ontology produces a graph that nobody can query. A baroque ontology produces extractor failures. Get the ontology right (Hour 4 was that work) and the rest is engineering.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 10. Frontier — KumoRFM and the relational angle

A signpost worth flagging here, not Hour 12: most enterprise data isn't documents *or* graphs — it's **relational tables**. Your CDD master data, your transaction table, your sanctions list, your account master — those are relational. KGs are often the *output* of joining relational data, not the input.

**KumoRFM** (Fey et al., 2025) is a foundation model for in-context learning over multi-table relational data. The idea: rather than build a KG from your tables, fit a foundation model that can answer KG-like questions directly over the relational schema. This is plausibly the next architectural step after Gen 3 for enterprise platforms.

For now, the classical pipeline — relational sources → KG construction → KG queries → LLM reasoning — is what production looks like, and it's what Hours 6 and 11 walk through. Hour 12 returns to KumoRFM as the "where is this all heading" closing thought.
"""),
    # ------------------------------------------------------------------
    ("code", """\
db.close()
"""),
    ("md", """\
---

## Stop and think before Hour 6

Three questions:

1. **For the extracted graph above, what is the most consequential *missing* edge?** Find one by hand. Trace why the extractor missed it — was it not in any document, or in a document the extractor was confused by?
2. **For the extracted graph, what is the most consequential *spurious* edge?** Find one. Trace why the extractor invented it — was it the prompt being ambiguous, or the document being florid?
3. **In your own platform's documents, which entity type would extraction find most reliably, and which would it find least reliably?** That ranking tells you where to spend reconciliation engineering effort first.

Next: [Hour 6 — Cypher queries and Gen 2's Lotus answer](./hour06_kg_querying.ipynb). You'll write a dozen queries that would be impossible or expensive in Gen 1, then produce Gen 2's full recommendation on the Lotus case and compare it to Gen 1's.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour05_kg_construction.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
