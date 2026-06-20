# Hour 13a — KG Foundation Models (the ULTRA / GAMMA direction)

A reading companion to `notebooks/hour13a_kg_foundation_models.ipynb`.

> **One-line frame for the hour.** *ULTRA's bet: relations are typed by their interactions with each other, not by their names. The structural pattern transfers across schemas; the names don't have to. GAMMA refines the bet with richer geometric representations.*

## 1. The assumption being broken

The 12-hour tutorial silently assumes you designed the ontology yourself. Hour 4 was that design work; Hour 5's extractors targeted your ontology; Hour 6's Cypher referenced your relation names; Hour 11's agent prompts named your tools. The entire stack is *per-organization*.

That's the right shape for one bank, one platform. It is the wrong shape when:

- The bank acquires another institution whose KG uses different relation names. Today: a multi-month schema-mapping project.
- A regulator's external KG uses a different vocabulary (FATF concepts, EU registry concepts). Bridging is engineering.
- A new entity type emerges from regulation and every downstream query needs updating.

ULTRA proposes that the structural pattern of how relations interact — not the names — carries information about the relations. A model that learns this pattern transfers across KGs zero-shot.

## 2. The relation interaction graph

ULTRA's central object is the **relation interaction graph (RIG)**. Nodes are *relations* (not entities). Edges encode meta-properties:

- *head-head* — two relations originate at the same node type.
- *tail-tail* — two relations end at the same node type.
- *composable* — relation A's tail type matches relation B's head type, so A then B is a valid path.

For the Lotus schema the RIG has 7 relation nodes and dozens of meta-edges. Each relation has a *structural fingerprint* — its pattern of in-going and out-going interactions with other relations.

The fingerprint is what ULTRA learns to read. It does not depend on the relation's name. Rename `CONTROLS` to `OWNS`; the fingerprint is identical.

## 3. Transferability — demonstrated cheaply

The notebook synthesises a "rival bank" schema with renamed relations and identical structure. Each relation in the rival schema has a unique structural fingerprint match to a Lotus relation. The bijection is automatic — no schema-mapping work.

This is a toy demonstration of the principle, not an implementation of ULTRA. The principle is what matters: *the structural pattern carries information about the relation independently of its name.*

For practical M&A integration: import the acquired KG; align relations by structural fingerprint; queries written against the original ontology Just Work over the joint graph. Today this is a project; with ULTRA-class methods it's a configuration step.

## 4. Held-out link prediction — the principle

The actual ULTRA evaluation is *inductive link prediction*: pretrain on KGs A, B, C; deploy on a never-seen KG D; predict missing edges in D, zero-shot.

The notebook demonstrates the principle with a structural baseline:

1. Hide a known edge — the John → ACME UBO edge.
2. Compute what should connect a Person to a LegalEntity.
3. Score each candidate relation by how well its endpoints match.

A correctly-set-up baseline ranks `UBO`, `Director`, `Shareholder`, `POA` (the Person→LegalEntity relations) above unrelated relations like `HOLDS` or `DEPOSITS_TO`. The baseline narrows the gap from "any of seven relations" to "one of four plausible ones" — using only structural information. A learned model with more features (composition patterns, neighbourhood structure, learned conditional embeddings) does much better.

## 5. ULTRA's actual mechanism

Three components above the toy baseline:

- **Rich RIG.** ULTRA's relation interaction graph has more edge types than the head/tail/composable trio, and the RIG is itself learned during pretraining across diverse KGs.
- **Conditional relation embeddings.** ULTRA does not learn a fixed embedding for each relation. Given a query, it *generates* a context-dependent embedding for the relevant relation — depending on the surrounding entities, the path being scored, and the local RIG slice.
- **Inductive scoring.** Standard KG embedding models need retraining for each new KG because every entity has a learned vector. ULTRA's scoring uses the *structure around* entities, not their identities. New KG, no retraining.

The combination is what produces the headline result: a single pretrained model doing inductive link prediction on 57 KGs, often beating supervised state-of-the-art on each specific graph.

## 6. GAMMA's extension

GAMMA is methodological depth on ULTRA. Where ULTRA uses a single algebraic transformation in message passing (typically element-wise multiplication, a real-valued operation), GAMMA uses multi-head geometric attention spanning four algebras:

- **Real** for symmetric relations (siblings, partners).
- **Complex** for asymmetric, antisymmetric relations (controls, owns).
- **Split-complex** for hierarchical, transitive relations (parent-of, subsidiary-of).
- **Dual number** for periodic/cyclic patterns (less common in static KGs; useful for temporal ones).

A learnable gating mechanism with entropy regularisation picks the right algebra per link. The reported improvement: 5.5% MRR over ULTRA on inductive benchmarks, with most of the gain on benchmarks containing mixed relation types.

**The practitioner take:** the geometric structure of relations matters and should be modelled. For control-management KGs — a mix of symmetric, asymmetric, and hierarchical relations — multi-algebra approaches are structurally well-matched.

When somebody pitches you "KG foundation models," ULTRA vs GAMMA is roughly the difference between a learned attention and a hand-tuned one. You'll see GAMMA-class methods evolve; the durable insight is that relations have geometric structure worth representing.

## 7. From sketch to production

A production deployment of ULTRA/GAMMA-class methods requires four things, and the toy in the notebook only demonstrates the first one:

1. **A pretrained checkpoint that runs on your compute.** Public ULTRA checkpoints exist. They run on CPU for small graphs but production-scale wants GPU. For a single-bank platform this is a fixed cost.
2. **A KG with clean entity resolution.** Structural reasoning is robust to renamed relations; it is *not* robust to phantom-duplicate entities. Hour 5's reconciliation is upstream, not displaced.
3. **A use case where link prediction is the right shape.** Missing UBO declarations; predicted account-opening risk; anomalous-relation flagging — yes. Generating a control manager's narrative answer — no. *ULTRA scores edges; it does not produce arguments.*
4. **A defensibility story.** Same as KumoRFM: predictions, not citations. The triage-layer pattern applies. Use ULTRA-class scoring to *prioritise* declarations for review; route flagged cases to the Gen 3 agent for the auditable analysis.

## 8. Three architectural choices the frontier rewards

If ULTRA-class methods are 2-3 years out for your bank, three choices made now adopt them cleanly:

- **Treat the ontology as a contract, not a constant.** Document it. Version it. Maintain a canonical mapping (FIBO-derived or in-house). When ULTRA lands, you map to the canonical, not re-engineer the agent.
- **Build entity resolution as a service.** ULTRA amplifies good entity resolution and amplifies bad. A single service — surface form + context → canonical id with confidence — that everything else calls. Future foundation models call it too.
- **Capture every Gen 3 decision as a labelled example.** The audit log from Hour 11 *is* a training set for the eventual scoring model. Labels are what the agent decided; features are what was in the KG at the time. Capture them from day one.

## 9. The honest limits

Three things even the ULTRA/GAMMA family does not address:

- **Schema drift over time.** ULTRA generalises across schemas at a point in time. It does not handle a schema that evolves mid-deployment — new entity types from new regulations, new relation types from new product lines. Bi-temporal modelling (Hour 13b) is orthogonal and still needed.
- **A wrong KG.** ULTRA reasons about graph structure. If the graph encodes a fact wrongly (phantom UBO edge from a hallucinated extraction, missing edge from a missed extraction), the reasoning inherits the error. Garbage in, garbage out — for foundation models too.
- **Compositionality has limits.** "John controls ACME via a 5-hop chain through three jurisdictions and a nominee director" composes many relations. ULTRA scores edges and short paths well; long compositional chains are harder. For control management's deepest UBO chains this is a real limit, not a marketing concern.

## 10. What to take away from Hour 13a

- The structural fingerprint principle — relations typed by their interactions, not their names.
- The relation interaction graph as the object that carries the fingerprint.
- A toy demonstration of structural transferability between a Lotus-original schema and a "rival bank" renamed schema.
- A toy link-prediction baseline that narrows the gap using only structure.
- ULTRA's actual mechanism (RIG + conditional embeddings + inductive scoring) above the toy.
- GAMMA's multi-algebra refinement.
- The triage-layer deployment pattern, recurring for the third Tier 2 hour in a row.
- The three architectural choices that make the frontier reachable.
- The honest limits — schema drift, KG correctness, deep compositionality.

The appendix is complete. The principles from Hours 0-12 transfer: relational / similarity / verification failure modes; entity resolution; provenance; governance. The frontier papers describe better ways to satisfy those principles.
