"""Build notebooks/hour13c_relational_fm.ipynb — KumoRFM direction."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 13c — Relational Foundation Models (the KumoRFM direction)

> *45-60 minutes dense, 2 hours to absorb. The most architecturally provocative of the three Tier 2 hours. KumoRFM proposes that for enterprise data — which is overwhelmingly relational — the entire Gen 1/2/3 retrieval pipeline can be replaced by a foundation model that reads relational tables directly. This hour builds the architectural shape with a stand-in classifier on the Lotus tables, then frames KumoRFM-class methods as a **triage layer** in front of the Gen 3 agent rather than as a replacement.*

**Reading companion:** [`docs/hour13c.md`](../docs/hour13c.md). **Frontier doc:** [`docs/reading_the_frontier.html`](../docs/reading_the_frontier.html) §6.
"""),
    ("code", """\
from pathlib import Path
from kg_tutorial import config, llm, display
from kg_tutorial.data import load
from kg_tutorial.relational_fm import (
    export_tables,
    lotus_features,
    score_account,
    WEIGHTS,
    AccountFeatures,
)

config.verify()
bundle = load.load()
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. The architectural shift

The 12-hour tutorial assumed the architectural unit:

```
query  →  retrieve  →  reason  →  answer
            ├── vector store (Gen 1)
            ├── knowledge graph (Gen 2)
            └── tools + agent (Gen 3)
```

Every generation assumed *retrieval* as a separate step. The KG is constructed once, queried many times. The vector store is built once, queried many times. The agent orchestrates the queries.

KumoRFM proposes a different unit:

```
relational tables + task  →  foundation model  →  prediction
```

No KG construction step. No bespoke ontology. No per-task model training. The model reads the relational tables directly (in-context) and produces a calibrated answer for any task that can be expressed against those tables.

For the Lotus case, the question shifts from *"build a KG, query it, reason"* to *"feed the persons / entities / accounts / deposits / sanctions tables in, ask 'is this customer high-risk?', get a score."*

This hour does not deploy KumoRFM — the actual model is research-grade and not widely accessible. We build the *architectural shape* with a stand-in classifier so you can see what changes and what stays the same.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Export the Lotus data to relational tables

Our synthetic data lives as Pydantic objects. Export each entity type to a flat CSV — exactly the input shape a relational FM expects.
"""),
    ("code", """\
out_dir = Path(config.DATA_DIR).parent / "relational"
written = export_tables(bundle, out_dir)
print(f"Wrote {len(written)} tables to {out_dir}:")
for name, path in written.items():
    n_rows = sum(1 for _ in path.open()) - 1
    print(f"  {name:<18}  {n_rows:>4} rows  -> {path.name}")
"""),
    ("md", """\
**The tables are the bank's substrate.** The KG you built in Hours 5-6 was a *derived view* of these tables. KumoRFM's bet is that the model can reason over the substrate directly, skipping the KG-construction step.

This is not a free lunch. The relational tables are *not* equivalent to the KG: they don't carry the typed, traversable structure that makes multi-hop queries cheap in Cypher. The relational FM's job is to do the traversal *implicitly* via attention across foreign-key joins.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Features that a relational FM would learn

The first thing a relational FM does, conceptually, is encode each table's rows into representations that can attend across tables. For our purposes — and to make the architectural shape concrete on a MacBook — we extract the same features by hand. **What we are doing here is not the model's mechanism; it is a window into what the model would have to compute internally.**
"""),
    ("code", """\
# Extract features for the Lotus account
features = lotus_features(bundle, "a_gamma_001")
print(f"Account: {features.account_id}")
print()
print(f"  chain_depth                       : {features.chain_depth}")
print(f"  n_offshore_jurisdictions          : {features.n_offshore_jurisdictions}")
print(f"  pep_relative_depth                : {features.pep_relative_depth}")
print(f"  max_fuzzy_sanctions_score         : {features.max_fuzzy_sanctions_score:.1f}")
print(f"  n_adverse_media_on_chain          : {features.n_adverse_media_on_chain}")
print(f"  total_inbound_eur                 : {features.total_inbound_eur:,.0f}")
print(f"  counterparty_country_concentration: {features.counterparty_country_concentration:.2f}")
print()
print(f"  Reached entities: {features.reached_entity_ids}")
print(f"  Reached persons:  {features.reached_person_ids}")
"""),
    ("md", """\
**Read the feature vector.** These seven numbers encode:

- A 3-hop ownership chain across multiple jurisdictions (chain_depth=3)
- Three offshore jurisdictions in the chain (KY, PA, LI; AE if you count UAE)
- A PEP in the chain at the top (pep_relative_depth=1)
- A near-match sanctions hit (max_fuzzy ~93)
- One adverse-media item touching the chain
- A specific inbound volume
- A specific concentration of inbound by country

Every fact the Gen 3 agent in Hour 11 painstakingly retrieved is reduced to a number here. The relational FM would learn these (and many more) features implicitly from training data; we extract them explicitly to make the architecture inspectable.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Score the account

A calibrated risk function over the features. **Weights are hand-set** in the stand-in; in a learned model they'd come from fitting on labelled cases.
"""),
    ("code", """\
print("Calibrated feature weights (the model's inductive bias):")
for k, v in WEIGHTS.items():
    print(f"  {k:<18}: {v:.2f}")
"""),
    ("code", """\
result = score_account(features)
print(f"=== Risk Score for Gamma Operations GmbH ===")
print(f"  Total score: {result.score:.3f}")
print(f"  Band:        {result.band}")
print()
print(f"  Feature contributions:")
for k, v in sorted(result.contributions.items(), key=lambda x: -x[1]):
    print(f"    {k:<18}: {v:.3f}")
"""),
    ("md", """\
**The score is HIGH.** Looking at the contributions, the top drivers should be:

1. `fuzzy_sanctions` — the strongest single signal (Atlas alias ~93%).
2. `pep_relative` — the PEP at the top of the chain.
3. `offshore_count` — three offshore jurisdictions in the chain.

The model produced a calibrated number that summarises the case. **In under a millisecond.**

Compare this to the Hour 11 agent: ~30-60 seconds, ~$0.10-0.40 per case, with a full reasoning trace. The relational-FM approach is roughly *100,000× faster and 100× cheaper*. The cost: no narrative explanation, no citation chain, no surfacing of open questions.

This is the architectural trade-off in one comparison.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. Score every account, see the distribution

A relational FM's value proposition is at scale: re-scoring every account, every day, on every list refresh. With one account it's a curiosity; with thousands it's a triage system.

(We only have one Lotus account, but we can score the noise-account-equivalents by featurising the same way.)
"""),
    ("code", """\
# Build feature vectors for every entity that holds an account (in our synthetic
# dataset, only Gamma. For demonstration, also score every entity AS IF it held
# an account at the same level — gives us a distribution to plot.)
all_scores = []
for entity in bundle.entities:
    # Pretend this entity holds an account for scoring purposes
    feats = AccountFeatures(account_id=f"hypothetical_{entity.id}")
    from kg_tutorial.relational_fm import _walk_up_chain
    reached_e, reached_p, max_d = _walk_up_chain(bundle, entity.id)
    feats.chain_depth = max_d
    chain_juris = {entity.jurisdiction} | {next((e.jurisdiction for e in bundle.entities if e.id == eid), "??") for eid in reached_e}
    from kg_tutorial.relational_fm import OFFSHORE_JURISDICTIONS
    feats.n_offshore_jurisdictions = len(chain_juris & OFFSHORE_JURISDICTIONS)
    pep_persons = {p.id for p in bundle.persons if p.is_pep}
    feats.pep_relative_depth = 1 if (set(reached_p) & pep_persons) else 99
    # Skip the more expensive features for the noise entities — they have no deposits
    feats.max_fuzzy_sanctions_score = 0.0
    feats.n_adverse_media_on_chain = sum(1 for a in bundle.adverse_media
                                          if any(m in set(reached_p) | set(reached_e) | {entity.id} for m in a.mentioned_ids))
    feats.counterparty_country_concentration = 0.5
    r = score_account(feats)
    all_scores.append((entity.legal_name[:30], r.score, r.band))

all_scores.sort(key=lambda x: -x[1])
print(f"Risk distribution across {len(all_scores)} entities:")
print()
for name, score, band in all_scores[:8]:
    print(f"  [{band:>6}] {score:.3f}  {name}")
print(f"  ... ({len(all_scores) - 8} more)")
print()
high = sum(1 for _, _, b in all_scores if b == "HIGH")
medium = sum(1 for _, _, b in all_scores if b == "MEDIUM")
low = sum(1 for _, _, b in all_scores if b == "LOW")
print(f"Distribution: HIGH={high}, MEDIUM={medium}, LOW={low}")
"""),
    ("md", """\
**The triage value is now visible.** Of the 12 entities, only a small fraction land in HIGH. Those are the ones a Gen 3 agent should see.

The other low-risk cases get *auto-approval with audit summary*. That is the value of a triage layer: 90% of cases handled by the fast/cheap model; the remaining 10% routed to the slow/expensive agent for defensible output.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. The triage-layer architecture

Now the picture explicit. With a relational FM in front:

```
incoming case
    │
    ▼
relational-FM scoring  (~1 ms, ~$0.00001)
    │ produces calibrated score + feature contributions
    ▼
band routing
    │
    ├── LOW    → auto-approve with the score's feature breakdown as audit
    ├── MEDIUM → Gen 1/2 retrieval for additional context, light review
    └── HIGH   → Gen 3 agent (full reasoning trace + citations)
```

This is the **same routing pattern** as Hour 12, with one more tier in front. Instead of asking *"which retrieval generation should this query use?"*, you ask *"is this case worth Gen 3's cost?"* For the answer-no cases, the relational FM is sufficient. For the answer-yes cases, it triages to the auditable layer.

Read the architecture as a generalisation of Hour 12's router, not a replacement.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. What KumoRFM actually adds beyond our stand-in

The stand-in classifier above has the *architectural shape* but not KumoRFM's mechanism. The real contributions of KumoRFM-class methods:
"""),
    ("md", """\
### 7.1 Table-agnostic encoding

Our stand-in is hard-coded for the Lotus schema. KumoRFM encodes *any* relational schema — Customer-Account-Transaction-Sanction at one bank looks the same as Member-Policy-Claim at an insurer, structurally. The model generalises across schemas without retraining.

For an enterprise, this means: stand up the model once, point it at any database, get predictions. No per-domain model build.
"""),
    ("md", """\
### 7.2 Relational graph transformer

The model attends across tables connected by foreign-key joins — a graph transformer over the relational schema's join graph. This is what lets it reason multi-hop without explicit KG construction. Our stand-in computes hand-coded features (`chain_depth`, `pep_relative_depth`); KumoRFM learns analogues from attention patterns.
"""),
    ("md", """\
### 7.3 In-context learning

At inference time, you provide a few labelled examples of the task and the model adapts. *No fine-tuning.* For our stand-in we hand-set the WEIGHTS dictionary; for KumoRFM you'd provide examples like *"this customer was approved with these tables; this one was declined."* The model learns the task from the examples in context.

This is the property that makes the architecture genuinely paradigm-shifting. The same model handles fraud detection, churn prediction, and risk classification — on the same database — by being shown a few examples of each.
"""),
    ("md", """\
### 7.4 Sub-second inference

Our stand-in is sub-millisecond because the function is hand-coded. KumoRFM's published inference time is <1 second. For a production triage layer running on every case, every list refresh, every transaction, the speed-cost combination is what makes the triage layer viable.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 8. What is lost (and why this matters for control management)

A naive read says "Gen 4 dominates Gen 3." A careful read says "Gen 4 complements Gen 3, in a triage pattern, and gives up the things Gen 3 was built for."

What you give up by routing a case to the relational FM:

- **No reasoning trace.** The model output is a score plus feature contributions; not a step-by-step argument.
- **No citation chain.** The model attends across all relevant facts implicitly; it does not surface *which specific OFAC entry* drove the sanctions component.
- **No open-questions surface.** The Gen 3 agent's `open_questions` field — what couldn't be verified — has no analogue in a feed-forward model.
- **No domain-specific tool calls.** The fuzzy-match tool, the sanctions-check tool, the policy-lookup tool all disappear into the model's implicit features. You cannot point at "the tool said 93% match" — you can only point at "the model gave this case a 0.7 score, with the sanctions feature contributing 0.3."

For regulated decisions, these are not transition issues that will disappear with better tooling. They are structural properties of feed-forward models. **The triage pattern preserves Gen 3 for the cases that need defensibility; relational FMs handle the volume.**
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 9. The deployment honesty

Three things that determine whether you can actually put a relational FM in front of Gen 3:

1. **Calibration on your data.** The stand-in's weights were hand-set; a learned model needs labelled cases. Labels in compliance are scarce, expensive, and slow to accumulate. The first six months of deployment are a labelling project.

2. **Drift monitoring.** When the underlying data distribution shifts (new sanctions regimes, new typologies of risk), the model's calibration degrades. You need monitoring that detects when the feature distribution at inference time has drifted from training-time — and routes more cases to the Gen 3 agent during drift.

3. **Regulatory acceptance.** Even with a triage pattern, a regulator may require that *every* case have a Gen 3-style audit trail, regardless of risk band. If so, the relational FM has no place in the decision loop — it can still drive *prioritisation* (which cases for the human to look at first) but not auto-approval.

Treat KumoRFM-class deployment as a 18-36 month programme, not a model deployment. The model is the easy part.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 13a

Three questions:

1. **In your platform's cases, what fraction would honestly be safe to auto-approve via a triage layer?** That fraction is the cost-saving case for KumoRFM-class deployment.
2. **For the cases the triage layer would auto-approve, what is the regulator's likely tolerance?** Some regimes allow algorithmic auto-approval below a threshold; others require human sign-off on every case regardless of risk score.
3. **For our stand-in classifier, which feature would you most want to learn rather than hand-set?** That answers "what is the labelling project we'd run first."

Next: [Hour 13a — KG Foundation Models (ULTRA + GAMMA)](./hour13a_kg_foundation_models.ipynb). The final Tier 2 hour. Cross-schema reasoning, inductive transfer.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour13c_relational_fm.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
