# Hour 5 — Gen 2: KG construction

A reading companion to `notebooks/hour05_kg_construction.ipynb`.

> **One-line frame for the hour.** *Building a knowledge graph from real data is mostly an entity-resolution and reconciliation problem. The extraction step gets the attention; the resolution step is where the cost lives.*

## 1. The three production paths to a KG

There are three ways production knowledge graphs get built:

| Path | When you use it | Cost | Reliability |
|---|---|---|---|
| **Structured load** | Source is a database / API with known schema | Cheap | High |
| **Schema-guided extraction** | Source is unstructured text with a known ontology | Medium | Medium |
| **Schema-free extraction** | Source is unstructured text, ontology is being learned | High | Variable |

Production platforms blend the first two. Structured sources — internal customer master data, registry feeds, sanctions list APIs — load directly. Unstructured sources — CDD forms, RM memos, correspondence, news — extract. The two graphs are then *reconciled* against each other, and that reconciliation step is where most of the engineering effort actually goes.

The notebook demonstrates paths 1 and 2 on the same data, exactly so the comparison is visible.

## 2. Path A — structured load

We have the canonical Pydantic data. We have a `DatasetBundle`. The Lotus chain is already coherent in code. Loading it is mechanical: iterate the bundle, write `MERGE` statements per node and edge.

The reason to use `MERGE` rather than `CREATE` is idempotence: re-running the loader should be safe. `MERGE` matches an existing node by its identifying properties and creates it only if absent.

A few practical notes:

- **Per-label MERGE.** `MERGE (p:Person {id: 'p_john_q_public'})` is unambiguous; `MERGE (n {id: ...})` would match across all labels and is dangerous.
- **Properties separated from MERGE.** `SET p.full_name = ...` after MERGE; don't put descriptive properties in the MERGE pattern. The MERGE pattern is the *identity*; SET sets the *content*.
- **Constraints first.** In production you create unique constraints (`CREATE CONSTRAINT FOR (p:Person) REQUIRE p.id IS UNIQUE`) before loading. This makes MERGE fast (it uses the constraint's index) and protects you against duplicate insertion.

## 3. Path B — schema-guided extraction

The realistic case: we have only unstructured documents. We want to build the same graph.

The notebook runs two extractors on the same documents:

- **spaCy NER baseline.** Out-of-the-box `en_core_web_sm`. Fast, deterministic, no training.
- **Claude with the ontology in the prompt.** Schema-guided.

### What spaCy gets right

`PERSON`, `ORG`, `GPE`, `DATE`, `MONEY`, `PERCENT` — the canonical NER vocabulary. For ~80% of the entity surface in a typical CDD form, spaCy is competent. It is also free and deterministic — both of which matter at scale.

### What spaCy gets wrong

- No bank-specific entity types. "UBO" is not in the vocabulary; "PEP-relative" certainly isn't.
- No relation extraction. Knowing that "John Q. Public" is a PERSON and "ACME Holdings" is an ORG doesn't tell you that the first owns the second.
- Imperfect entity-type assignment on legal entities. "ACME Holdings Ltd" sometimes tagged as ORG, sometimes split, sometimes mistagged as PERSON.

### What Claude (schema-guided) gets right

Given the ontology in the system prompt, Claude returns both entities and *typed relations*. Crucially:

- Relations come with properties — `(John Q. Public) --[UBO {percent: 50}]--> (ACME Holdings Ltd)`.
- Bank-specific concepts (PEP-relative, UBO, fiduciary) are recognised because they're in the schema.
- Context-dependent relations work — "the nephew of the sitting MP" surfaces as a `RELATED_TO` family edge.

### What Claude gets wrong

- **Hallucinated relations.** Two persons mentioned in proximity sometimes get a `RELATED_TO`. Hour 5's lab asks you to find one by hand.
- **Surface-form variation.** "John Q. Public", "J. Q. Public", "Mr Public" all extracted as separate surfaces. Reconciliation (next section) collapses them — but it depends on the resolver being good.
- **Cost.** ~$0.01 per document on Sonnet. For 100k documents, that's $1k each refresh — non-trivial in absolute terms, trivial relative to the alternative (build it by hand).

## 4. The reconciliation problem

Both extractors return *surface strings*. The graph wants canonical IDs. The bridge is *entity resolution* — for each extracted mention, decide which canonical entity it refers to (or whether it's a new entity).

For the tutorial we use a SequenceMatcher-based fuzzy matcher against the known surface forms. It works for most cases, fails for transliterations and acronyms, and is small enough to inspect.

In production, entity resolution is a substantial system in its own right:

- **Blocking.** Don't compare every extracted mention to every canonical entity — bucket by phonetic key or token shingles first.
- **Multi-feature scoring.** Combine string similarity with surrounding-text features (jurisdiction, role, dates).
- **Calibrated thresholds.** Decision thresholds tuned to operational precision/recall, not picked off the chart.
- **Human-in-the-loop for ambiguous cases.** A control manager reviews matches in [70%, 90%] confidence; auto-accepts above, auto-rejects below.

**The single biggest source of silent error in production KGs is entity resolution failure** — two different surface forms that should resolve to the same canonical id but don't, creating phantom duplicate nodes. The graph looks fine; queries find only half the edges; nobody notices until a regulator finds it for them.

## 5. The Microsoft GraphRAG pattern (schema-free)

For completeness: the third path. **Schema-free extraction** — popularised by Microsoft's GraphRAG paper — invents entity types and relations as it goes, then clusters the resulting graph into communities and pre-computes summaries at each community level. The query pattern is then: find the relevant community, summarise from the pre-computed summary, answer.

For a regulated domain this is the wrong default — regulators want a defensible model, not an emergent one. But schema-free has a place: **discovery**. Run a schema-free extractor over your archive of CDD forms. Look at the relation types it finds that weren't in your ontology. The ones that recur are gaps to consider.

## 6. Five operational realities

What the lab is too short to cover but you should know about:

1. **Incremental updates.** Production KGs are not rebuilt nightly from scratch. They are updated incrementally — new documents arrive, new entities resolve, new edges merge. Idempotent loaders are not optional.
2. **Provenance.** Every node and edge has a `source` property pointing to where it came from — which document, which API call, which manual override. Without provenance you cannot audit; without audit, the bank cannot deploy.
3. **Bi-temporal modelling.** Valid-time (when does the fact apply in the world?) and transaction-time (when did we know about it?) are separate concerns. Real production KGs model both. We do not, in the tutorial. TIE is the research direction.
4. **Schema evolution as a normal event.** The ontology will change. You need a migration story — old documents extracted under the old schema, new ones under the new, queries that span both.
5. **Cost monitoring.** LLM-extraction costs add up fast at production scale. Cache aggressively, watermark inputs to detect unchanged documents, and treat the extraction layer as ETL — with all the rigour that implies.

## 7. What to take away from Hour 5

- The three production paths to a KG and when each is right.
- Why the engineering effort in Gen 2 production is *reconciliation*, not extraction.
- spaCy's strengths (cheap, deterministic, decent entity surface) and limits (no relations, no bank concepts).
- Claude's strengths (typed relations from prose) and limits (hallucinations, cost, surface-form variation).
- The five operational realities — none of which the tutorial implements but all of which production needs.

Hour 6 takes the graph you built and writes queries against it. The Lotus answer that Gen 2 produces is the test of whether the construction was worth it.
