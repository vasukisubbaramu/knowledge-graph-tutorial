"""Build notebooks/hour13b_temporal_kg.ipynb — temporal KGs (TIE direction)."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 13b — Temporal Knowledge Graphs (the TIE direction)

> *45-60 minutes dense, 2 hours to absorb. The first of three Tier 2 appendix hours. The tutorial's main 12 hours deferred temporal reasoning — Hour 6 acknowledged that Cypher does not have first-class temporal semantics; Hour 7 named TIE as the research direction. This hour makes the deferred axis explicit. You build a temporally-filtered view of the Lotus graph, run bi-temporal queries against it, and see the embedding-level mechanism TIE proposes — without training it.*

**Reading companion:** [`docs/hour13b.md`](../docs/hour13b.md). **Frontier doc:** [`docs/reading_the_frontier.html`](../docs/reading_the_frontier.html) §5.

**Prerequisite:** Hours 0-12. Neo4j optional — the labs run on NetworkX.
"""),
    ("code", """\
from datetime import date
from kg_tutorial import config, llm, display, tools
from kg_tutorial.data import load
from kg_tutorial.temporal import (
    effective_controls_at,
    effective_sanctions_at,
    effective_adverse_media_at,
    bundle_at,
    diff,
    LOTUS_SNAPSHOT_DATES,
)
from kg_tutorial.graph import bundle_to_networkx, lotus_subgraph, draw_graph

config.verify()
bundle = load.load()
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. Why this hour exists

The 12-hour tutorial worked on the present tense. Every query was *"what is true now?"* Every answer was answerable from the current snapshot of the data.

Regulators don't work in the present tense. The questions a control-management platform must answer include:

- *"What did we know about this customer when we approved them in 2024?"* (point-in-time reconstruction)
- *"This customer's UBO disclosure was updated in 2025. Has our risk classification been updated accordingly, without losing the prior classification rationale?"* (bi-temporal update without forgetting)
- *"Reconstruct the platform's reasoning for this case on the date it was decided."* (auditable temporal replay)

None of these is hard in principle. All of them are absent in the tutorial's main 12 hours. The reason: temporal reasoning at scale is *the* deferred problem in the production Gen 2 / Gen 3 architecture.

There are two layers to address. The **schema layer** — adding `effective_from` / `effective_to` properties to every fact and querying through them — is what production systems do today. The **embedding layer** — what TIE proposes — is the research-frontier extension. We do the schema layer in code and sketch the embedding layer in concept.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. The temporal fields you already have

The Lotus dataset already carries dates on every fact that matters. Inspect them:
"""),
    ("code", """\
print("Persons (date_of_birth):")
for p in bundle.persons[:4]:
    print(f"  {p.full_name:<25} born {p.date_of_birth}")

print()
print("Legal entities (incorporation_date):")
for e in bundle.entities[:4]:
    print(f"  {e.legal_name:<35} incorporated {e.incorporation_date}")

print()
print("Control relationships (effective_from / effective_to):")
for c in bundle.controls[:6]:
    ends = c.effective_to.isoformat() if c.effective_to else "(open)"
    print(f"  {c.controller_id:>22} --[{c.control_type.value}]--> {c.controlled_id:<22}  {c.effective_from} → {ends}")

print()
print("Sanctions (listed_date):")
for s in bundle.sanctions:
    if "ATLAS" in s.name:
        print(f"  {s.name} listed {s.listed_date}")

print()
print("Adverse media (published_date):")
for a in bundle.adverse_media:
    print(f"  '{a.headline[:50]}' published {a.published_date}")
"""),
    ("md", """\
The temporal fields exist. The tutorial just didn't query through them. We will now.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. The five canonical snapshot dates

The Lotus story plays out over five temporally distinct moments. Memorize these — every audit query in this hour points to one of them.
"""),
    ("code", """\
for label, d in LOTUS_SNAPSHOT_DATES:
    print(f"  {d.isoformat()}   {label}")
"""),
    ("md", """\
**Why these dates matter:**

- **Q1 2020** — pre-Atlas. The chain John→ACME→AlphaBeta exists but Gamma Operations is not yet incorporated (2021).
- **Q1 2022** — Gamma now incorporated; the Lotus ownership chain is complete.
- **Q1 2024** — Atlas Wirecorp exists but is **not yet on the OFAC list**. The adverse media article on John has been published in late 2023? No — published 2024-10. Pre-adverse media too.
- **Q3 2024** — OFAC has listed Atlas (2024-07-15). Adverse media has been published (2024-10-08). The picture starts to look concerning.
- **Q2 2026** — now. The deposit has landed (2026-06-03); the application is being decided.

A control manager asking *"what did we know about this customer when we approved them in 2022?"* is asking for the Q1 2022 view of the graph. Whatever they conclude must be defensible against *what was known then* — not what is known now.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Snapshot the graph — Q1 2022 vs Q3 2024 vs now

Run the bundle-filter at three of the canonical dates and compare. The right column is what an audit replay would see.
"""),
    ("code", """\
from kg_tutorial.temporal import bundle_at

dates_to_compare = [
    ("Q1 2022", date(2022, 3, 31)),
    ("Q3 2024", date(2024, 9, 30)),
    ("Q2 2026", date(2026, 6, 30)),
]
for label, d in dates_to_compare:
    b = bundle_at(bundle, d)
    print(f"{label} ({d}):")
    print(f"   persons: {len(b.persons):<3}  entities: {len(b.entities):<3}  controls: {len(b.controls):<3}")
    print(f"   sanctions: {len(b.sanctions):<3}  adverse_media: {len(b.adverse_media):<3}  deposits: {len(b.deposits):<3}")
    print()
"""),
    ("md", """\
**The numbers tell the story.** The number of *facts* the platform would have had access to grows over time. In particular:

- Sanctions records on Atlas only exist from Q3 2024 onward.
- The adverse-media item on John only exists from Q3 2024 onward.
- The Lotus deposit only exists in 2026.

If you re-ran the Hour 11 agent against the Q1 2022 bundle, the answer would be *different* — Atlas would not appear as sanctioned because OFAC had not listed it. The agent would correctly conclude "clear" on sanctions. That conclusion would have been *right at the time*, even though it is wrong now.

This is what point-in-time reconstruction looks like. It is the answer to the regulator's question *"why did you approve this customer in 2022?"*
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. The diff between snapshots — the audit replay

The most interesting query in temporal KGs is not the point-in-time snapshot itself; it is **the diff between two snapshots**. The diff is what informs incremental review:

> *"Between when we last reviewed this customer (Q1 2024) and now (Q2 2026), what changed?"*

That is the natural shape of ongoing-monitoring queries in compliance.
"""),
    ("code", """\
d = diff(date(2024, 3, 31), date(2026, 6, 30), bundle=bundle)
print(f"Diff Q1 2024 → Q2 2026:")
print(f"  added controls: {d.added_controls}")
print(f"  removed controls: {d.removed_controls}")
print(f"  new sanctions records: {d.added_sanctions}")
print(f"  new adverse media: {d.added_adverse_media}")
print(f"  new deposits: {len(d.added_deposits)}")
"""),
    ("md", """\
**Read the output.** Three findings between the last review and now:

1. A new sanctions record on Atlas Wirecorp (`s_atlas`) appeared.
2. A new adverse-media item naming John Q. Public (`am_offshore_clipping_2024`) appeared.
3. The Lotus deposit landed (along with noise deposits).

A diff-driven monitoring system would have triggered re-review of every customer that touched any of these — including Gamma Operations GmbH. **This is what *event-driven KYC* looks like, and it is what the tutorial's main 12 hours could not express.**
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. Re-running the agent at a historical date

Now the demonstration. We rebuild the *tools* the agent uses to honour the temporal filter, then ask the same Lotus question at Q1 2024 and at Q2 2026.

(The tools in `kg_tutorial.tools` operate on the present-tense bundle. For this lab we patch them to use a temporal bundle — the production version would be a `as_of` argument on every tool.)
"""),
    ("code", """\
# A temporally-filtered sanctions_check
def temporal_sanctions_check(name: str, as_of: date) -> str:
    b = bundle_at(bundle, as_of)
    from difflib import SequenceMatcher
    best_score = 0.0
    best_name = None
    for s in b.sanctions:
        for n in [s.name] + s.aliases:
            score = SequenceMatcher(None, name.upper(), n.upper()).ratio() * 100
            if score > best_score:
                best_score = score
                best_name = s.name
    if best_score >= 85:
        return f"ESCALATE (best match '{best_name}' at {best_score:.1f}%)"
    if best_score >= 70:
        return f"REVIEW (best match '{best_name}' at {best_score:.1f}%)"
    return f"CLEAR (top score was {best_score:.1f}% against '{best_name}')"


# Same query at three different dates
target = "ATLAS WIRECORP"
for label, d in [("Q1 2024 (pre-OFAC)", date(2024, 3, 31)),
                  ("Q3 2024 (post-OFAC)", date(2024, 9, 30)),
                  ("Q2 2026 (now)", date(2026, 6, 30))]:
    print(f"  As of {label}:")
    print(f"    sanctions_check('{target}') -> {temporal_sanctions_check(target, d)}")
    print()
"""),
    ("md", """\
**This is the point-in-time correctness story.** A deposit from `ATLAS WIRECORP` arriving in Q1 2024 was clear; the same name arriving in Q3 2024 onward must escalate. Without the temporal filter, the platform can only say "currently, this would escalate" — which is not the same as "at the time, this was clear."

A regulator auditing why a 2024 deposit was approved will accept "we made the right call given the information available at that point." They will not accept "we don't know what we knew."
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. Where the schema layer stops being enough

Everything above is the **schema layer**. We added queries that filter through `effective_from` / `effective_to` properties. Production platforms run on roughly this pattern: bi-temporal properties on every edge, hand-written date arithmetic in every query.

The schema-layer approximation is genuinely sufficient for the majority of regulatory audit queries. Where it falls short:

1. **Continuous learning.** Suppose we want a model that improves its risk classification as new adverse-media items arrive. Naive nightly retraining loses old knowledge (catastrophic forgetting). The schema layer doesn't help — the *model* doesn't track time, only the *data* does.
2. **Embeddings drift.** If we use vector embeddings to find similar customers, those embeddings reflect their training-time data distribution. Customers' risk profiles shift; the embeddings don't.
3. **Reproducibility at training time, not just inference time.** A regulator asking "rebuild the model's reasoning as of 2024 and show me what it said about this customer" requires the model itself to be reconstructible — not just the data behind it.

The **embedding layer** — what TIE proposes — addresses these.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 8. TIE — what it actually proposes

**TIE: Time-aware Incremental Embedding for temporal KG completion.** Wu et al.

Three mechanisms, none of which we train but all of which are pedagogically reachable:
"""),
    ("md", """\
### 8.1 Time-aware encoding

Every entity and relation embedding is augmented with a *temporal* component. Conceptually:

```
embedding(John, t=2020) ≠ embedding(John, t=2024)
```

— because John's role in the world has changed (he became a PEP-relative when his aunt joined Parliament in 2019; the adverse-media article was published in 2024). The model's representation reflects this.

In practice this is done by either (a) adding a time vector to every embedding before scoring, or (b) using a temporal positional encoding (think transformer positional encoding, but the position is time).
"""),
    ("md", """\
### 8.2 Experience replay

When the KG is updated with new facts — a new sanctions listing, a new ownership change — the model is fine-tuned on *the new facts plus a sample of old facts*. This prevents the new training from overwriting old knowledge.

Conceptually:

```
training batch at update step t = (new facts at t)  ∪  (random sample of past facts)
```

The replay sample is what stops catastrophic forgetting. The size of the sample tunes the trade-off between learning new things and preserving old ones.
"""),
    ("md", """\
### 8.3 Temporal regularization

A penalty on representations that drift faster than their underlying facts have changed. If John's set of facts hasn't changed between t=2024 and t=2025, John's embedding shouldn't drift much either. Implemented as an L2 penalty on `‖embedding(John, t+1) - embedding(John, t)‖` weighted by how much John's facts have actually changed.
"""),
    ("md", """\
### 8.4 The intransigence metric

TIE introduces a metric to make the trade-off explicit:

- **Forgetting**: accuracy on old facts after the model is updated with new ones.
- **Intransigence**: how much the model resists updating to the new facts.

A production platform tunes its experience-replay parameters and regularization strength to balance these. TIE's contribution is making both legible.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 9. What you would build on top of this hour

The schema-layer approximation in §3-§6 is what your platform should adopt now. The embedding-layer mechanism in §8 is what makes sense to revisit when one of these conditions holds:

- You have a learned model in the loop (vector retrieval, learned link prediction, agent fine-tuning) that needs to retain old behaviour while incorporating new facts.
- You face regulator questions that require *training-time* reproducibility, not just inference-time replay.
- The cost of nightly retraining-from-scratch is becoming material.

If none of those holds, the schema-layer approximation is sufficient. Most teams stay there for years.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 10. Where this still strains

Three honest limits of even the TIE-class approach:

1. **Schema evolution.** Time-aware embeddings handle facts changing over time; they don't naturally handle *new entity types or relation types* introduced by regulation. ULTRA-class methods (Hour 13a) address that axis.
2. **Cross-system temporal joining.** Your KG is bi-temporal. The external sanctions feed is bi-temporal. Joining them at audit time requires consistent time semantics across systems — a data-quality problem, not a model problem.
3. **The agent doesn't know it's reasoning historically.** Even if every tool is time-filtered, the LLM's training data is fixed and modern. Asking Claude in 2026 about a 2022 view of the world will leak modern reasoning patterns into the answer. Production replay requires the agent's *prompts* (not just its data) to be time-anchored — a discipline rather than a mechanism.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 13c

Three questions:

1. **What is the latest date in your platform's data, and what is the latest date in your platform's *model*?** The gap is your point-in-time-reasoning risk surface.
2. **Of the three TIE mechanisms (time-aware encoding, experience replay, temporal regularization), which would your platform benefit from first?** Most platforms find experience replay the cheapest to retrofit.
3. **What is one regulatory audit question your platform cannot answer today that it could answer with a bi-temporal schema?** That question is the cost-benefit case for the schema-level work.

Next: [Hour 13c — Relational FMs and the triage-layer pattern](./hour13c_relational_fm.ipynb).
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour13b_temporal_kg.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
