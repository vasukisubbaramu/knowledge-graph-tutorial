# Hour 13c — Relational Foundation Models (the KumoRFM direction)

A reading companion to `notebooks/hour13c_relational_fm.ipynb`.

> **One-line frame for the hour.** *KumoRFM proposes a paradigm shift: skip KG construction, let a foundation model reason over relational tables directly. The honest deployment pattern is not "Gen 4 replaces Gen 3" but "Gen 4 triages, Gen 3 adjudicates."*

## 1. The architectural shift in one paragraph

The 12-hour tutorial assumed a retrieval pipeline as the unit: query → retrieve (vector, graph, or tool) → reason → answer. KumoRFM proposes a different unit: relational tables + task → foundation model → prediction. No KG construction step. No bespoke ontology. No per-task model training. The model reads the relational tables in-context and produces a calibrated prediction for any task expressible against those tables.

For enterprise data — overwhelmingly relational (customer tables, account tables, transaction tables, sanctions tables) — this collapses Gens 1/2/3 into "one model, one query, one prediction." The cost: explainability and defensibility.

## 2. The Lotus tables exported

The notebook writes seven CSVs from the existing Pydantic data:

- `persons.csv` (id, full_name, is_pep, pep_reason, residence_country, date_of_birth)
- `legal_entities.csv` (id, legal_name, jurisdiction, entity_type, incorporation_date)
- `accounts.csv` (id, account_number, holder_entity_id, status, open_date, currency)
- `controls.csv` (id, controller_id, controlled_id, control_type, ownership_pct, effective_from)
- `deposits.csv` (id, account_id, amount_eur, value_date, counterparty_name, counterparty_country, purpose_code)
- `sanctions.csv` (id, list_source, name, aliases, listed_date, country)

These are the substrate. The Knowledge Graph you built in Hours 5-6 was a *derived view* of this substrate. KumoRFM's claim is that the model can reason over the substrate directly, skipping the KG.

This is not free. The tables don't carry the typed, traversable structure that makes Cypher cheap. The relational FM's job is to do the traversal *implicitly* via attention across foreign-key joins.

## 3. Features as a window into the model

The notebook computes seven hand-coded features per account: chain depth, offshore jurisdiction count, PEP-relative depth, max fuzzy sanctions score, adverse-media count, total inbound, counterparty concentration. These are exactly the features a relational FM would learn from training data — we extract them explicitly to make what the model would compute *visible*.

The features are a clean reduction of everything the Gen 3 agent in Hour 11 painstakingly retrieved. In one feature vector you carry the risk-relevant signals. The relational FM produces a score; the score reduces to a triage decision (low/medium/high).

## 4. The triage-layer architecture

The honest pattern for deploying KumoRFM-class methods in regulated finance:

```
incoming case
    │
    ▼
relational-FM scoring  (~1s, near-zero marginal cost)
    │ produces a calibrated score + feature contributions
    ▼
band routing
    │
    ├── LOW    → auto-approve with audit summary
    ├── MEDIUM → Gen 1/2 retrieval for context, light human review
    └── HIGH   → Gen 3 agent (full reasoning trace + citations)
```

The triage layer handles volume. The Gen 3 agent handles defensibility. The same routing pattern as Hour 12, with one more tier in front.

Read this as a generalisation of the Hour 12 router, not a replacement.

## 5. What KumoRFM actually adds beyond a stand-in

Four mechanisms our stand-in doesn't capture:

- **Table-agnostic encoding.** Our stand-in is hard-coded for the Lotus schema. KumoRFM encodes *any* relational schema, generalising across domains without retraining.
- **Relational graph transformer.** The model attends across tables connected by foreign-key joins — a graph transformer over the schema's join graph. This is what makes multi-hop reasoning possible without explicit KG construction.
- **In-context learning.** At inference time you supply a few labelled examples of the task; the model adapts without fine-tuning. The same model handles fraud, churn, risk classification by being shown different examples.
- **Sub-second inference.** Production-grade triage requires speed; KumoRFM delivers it.

The architectural significance is in the combination: the model is *task-general*, *domain-general*, and *fast*. That combination is what makes the triage layer viable.

## 6. What is lost — and why it matters for regulated work

What you give up by routing a case to the relational FM:

- **No reasoning trace.** Score + feature contributions, not a step-by-step argument.
- **No citation chain.** The model attends across all relevant facts implicitly; you cannot point at "this specific OFAC entry drove the sanctions component."
- **No open-questions surface.** No analogue to the agent's `open_questions` — what couldn't be verified.
- **No domain-specific tool calls.** The fuzzy-match tool, the sanctions-check tool — these disappear into the model's implicit features.

For regulated decisions these are structural properties of feed-forward models, not transition issues that disappear with better tooling. Hence the triage pattern: Gen 3 stays for cases that need defensibility; KumoRFM handles volume.

## 7. The deployment honesty

Three things determine whether you can put a relational FM in front of Gen 3:

1. **Calibration on your data.** The stand-in's weights are hand-set; a learned model needs labelled cases. Labels in compliance are scarce, expensive, and slow to accumulate. The first six months of deployment are a labelling project.
2. **Drift monitoring.** When the underlying data distribution shifts (new sanctions regimes, new risk typologies), the model's calibration degrades. Production systems route more cases to Gen 3 during detected drift.
3. **Regulatory acceptance.** Even with the triage pattern, a regulator may require *every* case to have a Gen 3-style audit trail. If so, the relational FM still has value for prioritisation (order in which a human reviews cases) but not for auto-approval.

Treat KumoRFM-class deployment as an 18-36 month programme, not a model deployment.

## 8. Three architectural choices the frontier rewards

If you're building today and the relational FM is on a 2-3 year horizon, three design decisions made now will let you adopt it cleanly when it lands:

1. **Keep the relational tables clean and joined.** The KG you build now is a derived view; the substrate is the tables. A relational FM consumes the substrate; if the substrate is dirty (orphan rows, inconsistent keys), the FM is starving.
2. **Engineer the agent for tool extension.** The Hour 8/11 agent's competence is the tool catalogue. When better scoring (relational FM) becomes available, you wrap it as a tool the agent can call. The agent stays the orchestrator; the new model is one of its tools.
3. **Build a calibration / labelling pipeline.** Every Gen 3 agent decision is also a *labelled example*. Capture them. Six months in, you have a training set for the triage model.

## 9. What to take away from Hour 13c

- The relational substrate is what a foundation model would consume directly, skipping the KG.
- Our stand-in classifier shows the *shape* of the input/output; KumoRFM-class methods deliver it without per-task training.
- The honest deployment pattern is a triage layer, not a replacement.
- Three structural properties (no trace, no citations, no open questions) make the triage pattern necessary for regulated decisions.
- Deployment is an 18-36 month programme; the model is the easy part.

The next hour (13a) tackles the third deferred direction — universal inductive reasoning over arbitrary KGs.
