# Hour 13b — Temporal Knowledge Graphs (the TIE direction)

A reading companion to `notebooks/hour13b_temporal_kg.ipynb`.

> **One-line frame for the hour.** *The tutorial's main 12 hours worked in the present tense. Regulated finance does not. This hour makes the deferred temporal axis explicit: the schema-level approximation, which production runs on, and the embedding-level mechanism (TIE) sitting on the research frontier.*

## 1. Why this hour exists

The 12-hour tutorial's failure modes were Gen 1's three (closed-world, disconnected, no verification) plus Gen 2's three strains (fuzzy match, schema rigidity, temporal). We addressed five of six in Hours 7-12. The sixth — temporal — was deferred to the frontier.

The reason for the defer was honest. Temporal reasoning at scale requires either:

- **Schema-level bi-temporal modelling** with disciplined querying, which is operational rigour rather than novel architecture.
- **Embedding-level mechanisms** (the TIE family) that handle continuous learning without catastrophic forgetting, which is genuinely research-grade.

Most production platforms run on the first; the second is on the horizon. This hour gives you both — and the practical case for when each is the right investment.

## 2. The schema-level approximation

Add `effective_from` / `effective_to` to every fact. (Optionally add `known_from` / `known_until` too — that's the second time axis, the system's knowledge time, distinct from real-world validity time.)

Your queries then filter through these properties. *"As of 2024-03-31, was Atlas Wirecorp sanctioned?"* becomes:

```cypher
MATCH (s:SanctionsRecord {id: 's_atlas'})
WHERE s.listed_date <= date('2024-03-31')
RETURN s
```

The query returns nothing — Atlas wasn't listed yet. The answer is *correct at the time*.

The Lotus dataset already has these fields on every fact that matters: `effective_from` / `effective_to` on controls, `listed_date` on sanctions, `published_date` on adverse media, `value_date` on deposits, `open_date` on accounts, `incorporation_date` on entities, `date_of_birth` on persons. The tutorial's main hours just didn't query through them. The hour does.

### What you get from the schema layer alone

- **Point-in-time reconstruction.** "What did we know on date X?"
- **Diff-based monitoring.** "What changed between date X and date Y?"
- **Auditable replay.** "Re-run the agent on the date-X view of the data, get the date-X answer."
- **Event-driven KYC.** New sanctions listing → automatic re-review of every customer who touches the entity.

These are the four queries a regulator most often wants. The schema layer is sufficient for all four.

### What the schema layer doesn't give you

- **Reasoning by a learned model that has itself changed over time.** If your vector embeddings, your learned classifier, your fine-tuned agent have shifted, "what did the *model* think on date X" requires the model itself to be reconstructible. The data being bi-temporal is necessary but not sufficient.
- **Continuous incorporation of new facts** without re-training from scratch nightly. The schema layer says "here's what was true"; it doesn't help you re-train the learned components efficiently.
- **Calibrated confidence that adapts as the world changes.** A confidence score derived from the embedding distribution at training time doesn't update as that distribution shifts.

For all three, the TIE-family mechanisms become valuable.

## 3. TIE — what the embedding-level layer adds

**TIE: Time-aware Incremental Embedding for temporal knowledge graph completion.** Wu, Xu, Zhang, Ma, Coates, Cheung. SIGIR 2021.

Three mechanisms:

### Time-aware encoding

Every entity and relation embedding carries a temporal component. Conceptually, `embedding(John, t=2020)` and `embedding(John, t=2024)` are different vectors — because John's role in the world has changed (became a PEP-relative when his aunt joined Parliament in 2019; the adverse-media article published 2024).

In practice this is implemented either by adding a learned time vector to every embedding, or by using temporal positional encoding (think transformer positional encoding, but the position is time).

### Experience replay

When the KG is updated with new facts, the model is fine-tuned on a *mix* of new facts and a sample of old facts. The replay sample prevents the new training from overwriting old knowledge. The sample size tunes the trade-off between learning new things and preserving old ones.

The intuition: imagine training a classifier on January data, then training the same model on February data without showing it any January examples. February's distribution dominates and the model forgets January. Experience replay mixes a controlled sample of January back in — the model learns February while remembering January.

### Temporal regularization

A penalty on representations that drift faster than the underlying facts have changed. If John's set of facts hasn't changed between 2024 and 2025, John's embedding shouldn't drift much either. Implemented as a regularization term on the difference between consecutive temporal embeddings.

### The intransigence metric

TIE's contribution to evaluation, not just methods: a metric for *how much the model resists updating*. Paired with the standard *forgetting* metric, this lets you see the trade-off explicitly and tune to it.

A production platform tunes its experience-replay sample size and regularization weight to balance forgetting against intransigence — and TIE makes the trade-off legible rather than buried in a single hyperparameter.

## 4. When the TIE-family becomes the right investment

Three conditions, any one of which justifies looking at embedding-level temporal modelling:

- You have a learned model in the loop (vector retrieval, learned link prediction, fine-tuned agent components) that must retain old behaviour while incorporating new facts.
- You face regulator questions that require *training-time* reproducibility, not just inference-time data replay.
- The cost of nightly retraining-from-scratch is becoming material — in compute, in time, in operational risk.

If none of these holds, the schema-level approximation is sufficient. Most teams stay there for years and ship plenty of value.

## 5. The honest limits of even TIE

Three things TIE doesn't fix:

- **Schema evolution.** New regulations bring new entity types (Trust Protectors, Beneficial Ownership Registers, novel risk categories). Time-aware embeddings model facts changing over time; they don't naturally model the *vocabulary* changing. ULTRA-class methods (Hour 13a) address this axis.
- **Cross-system temporal consistency.** Your KG is bi-temporal. The external sanctions feed is bi-temporal. The customer master is bi-temporal. Joining them requires consistent time semantics across systems — which is a data-quality problem, not a model problem.
- **Time-anchored prompts.** Even if every tool and every retrieval is time-filtered, the LLM in the loop has training data fixed at some recent date. Asking Claude in 2026 about a 2022 view of the world will leak modern reasoning patterns into the answer. Production replay requires the agent's *prompts* (not just its data) to be time-anchored — a discipline rather than a mechanism.

## 6. What to take away from Hour 13b

- The schema-level approximation works today and addresses 80% of audit-shaped temporal queries.
- The TIE-family addresses the remaining 20% — the cases where the model itself must change over time without forgetting.
- Three conditions tell you whether to invest in the embedding-level layer; absent those conditions, the schema layer is enough.
- Even TIE doesn't fix schema evolution, cross-system consistency, or LLM training-data anchoring.

The next hour (13c) tackles the second deferred direction — the paradigm shift to relational foundation models.
