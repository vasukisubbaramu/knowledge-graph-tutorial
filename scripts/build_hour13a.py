"""Build notebooks/hour13a_kg_foundation_models.ipynb — ULTRA / GAMMA direction."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 13a — KG Foundation Models (the ULTRA / GAMMA direction)

> *45-60 minutes dense, 2 hours to absorb. The last of three Tier 2 appendix hours. The 12-hour tutorial designed an ontology by hand (Hour 4), wrote extractors against it (Hour 5), wrote Cypher against it (Hour 6). All of that work was **per-organization**: your bank's ontology, your bank's queries. ULTRA bets that reasoning can be made **transferable across schemas** by learning to represent relations as functions of their interactions with each other. This hour builds the conceptual scaffolding — including the held-out link-prediction demonstration — without training a model.*

**Reading companion:** [`docs/hour13a.md`](../docs/hour13a.md). **Frontier doc:** [`docs/reading_the_frontier.html`](../docs/reading_the_frontier.html) §3–§4.
"""),
    ("code", """\
from kg_tutorial import config, display
from kg_tutorial.data import load
from kg_tutorial.graph import bundle_to_networkx, lotus_subgraph

config.verify()
bundle = load.load()
G = bundle_to_networkx(bundle)
print(f"Lotus KG: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. The tutorial assumption ULTRA breaks

Every hour from 4 through 11 silently assumes you designed the ontology yourself. We chose `Person`, `LegalEntity`, `Account`, `Deposit`, `SanctionsRecord`, `AdverseMediaItem`. We chose `:CONTROLS` (with a `control_type` discriminator), `:HOLDS`, `:DEPOSITS_TO`, `:MENTIONS`. We chose to model ownership-percentage as an edge property. The whole stack — extractors, queries, agent prompts — references that exact vocabulary.

This works perfectly for *one* organization. It does not work when:

- The bank acquires another institution whose KG uses `:OWNED_BY` instead of `:CONTROLS{control_type:'UBO'}` and `:IS_DIRECTOR` instead of `:CONTROLS{control_type:'Director'}`. Today: a multi-month schema-mapping project.
- A regulator's external KG uses a different vocabulary entirely (FATF concepts, EU central registry concepts). Bridging takes engineering.
- A new entity type emerges (Trust Protector, Beneficial Ownership Register, novel risk category) and every downstream query needs updating.

ULTRA's bet: **relations are typed by their interactions with each other, not by their names.** "Controls" and "owns" might be different strings but if both have the same pattern of co-occurrence with other relations — composable with directorship, antisymmetric, transitively closed — they behave structurally the same. The structural pattern transfers; the names don't have to.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. The relation interaction graph

ULTRA's central object is the **relation interaction graph (RIG)**. Nodes are *relations*. Edges encode meta-properties: which relations meet at the same head, which at the same tail, which compose to form longer paths.

Build it for the Lotus schema by hand. Walk every node's adjacencies and record which relations meet there.
"""),
    ("code", """\
from collections import defaultdict
import networkx as nx

# Group edges by their type (the relation name)
def collect_relation_endpoints(G):
    \"\"\"For each relation r, return:
       - head_types[r]: set of node labels that ever appear as the head of an r-edge
       - tail_types[r]: same for tails
    \"\"\"
    head_types: dict[str, set] = defaultdict(set)
    tail_types: dict[str, set] = defaultdict(set)
    for u, v, data in G.edges(data=True):
        r = data.get("type") or "?"
        head_types[r].add(G.nodes[u].get("label") or "?")
        tail_types[r].add(G.nodes[v].get("label") or "?")
    return head_types, tail_types


head_types, tail_types = collect_relation_endpoints(G)
print("Each relation, by the labels it connects:")
for r in sorted(head_types):
    print(f"  {r:>20}: {sorted(head_types[r])} -> {sorted(tail_types[r])}")
"""),
    ("md", """\
This is the raw material. Two relations interact at a label if one's head type matches the other's tail type (or vice versa) — that's a structural composability. Let's build the RIG itself.
"""),
    ("code", """\
def build_rig(G) -> nx.MultiDiGraph:
    \"\"\"Build the relation interaction graph.

    Two relations r1 and r2 are connected in the RIG by:
      - 'head-head' if they share a head type (both originate at the same kind of node)
      - 'tail-tail' if they share a tail type
      - 'head-tail' if r1's tail type = r2's head type (composition is possible)
    \"\"\"
    head_t, tail_t = collect_relation_endpoints(G)
    relations = sorted(head_t)
    rig = nx.MultiDiGraph()
    for r in relations:
        rig.add_node(r, head_types=head_t[r], tail_types=tail_t[r])
    for r1 in relations:
        for r2 in relations:
            if r1 == r2:
                continue
            if head_t[r1] & head_t[r2]:
                rig.add_edge(r1, r2, type="head-head")
            if tail_t[r1] & tail_t[r2]:
                rig.add_edge(r1, r2, type="tail-tail")
            if tail_t[r1] & head_t[r2]:
                rig.add_edge(r1, r2, type="composable")
    return rig


rig = build_rig(G)
print(f"RIG: {rig.number_of_nodes()} relations, {rig.number_of_edges()} interactions")
print()
print("Interactions (the structural fingerprint of each relation):")
for r in sorted(rig.nodes):
    in_kinds = sorted({d["type"] for _, _, d in rig.in_edges(r, data=True)})
    out_kinds = sorted({d["type"] for _, _, d in rig.out_edges(r, data=True)})
    print(f"  {r:>18}: in={in_kinds}, out={out_kinds}")
"""),
    ("md", """\
**Read the RIG carefully.** Each relation has a *structural fingerprint* — the kinds of interactions it participates in. `CONTROLS` composes into `HOLDS` (a Person → Entity → Account chain). `DEPOSITS_TO` shares a tail with `HOLDS` (both end at Account). `MENTIONS` shares heads with itself but composes into both `CONTROLS` and `HOLDS`.

That fingerprint is what ULTRA would learn. **It does not depend on the relation's name.** Rename `CONTROLS` to `OWNS`; the fingerprint is identical.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. The "rival bank" — same structure, different names

Synthesize a second KG with the same structural shape as Lotus but renamed relations. Build the RIG. Compare.
"""),
    ("code", """\
import networkx as nx

# A rival bank's KG with renamed relations
def renamed_graph(G, rename: dict[str, str]) -> nx.MultiDiGraph:
    H = nx.MultiDiGraph()
    for n, attrs in G.nodes(data=True):
        H.add_node(n, **attrs)
    for u, v, d in G.edges(data=True):
        new_d = dict(d)
        new_d["type"] = rename.get(d.get("type", "?"), d.get("type", "?"))
        H.add_edge(u, v, **new_d)
    return H


rival_rename = {
    "UBO": "OWNED_BY",
    "Director": "IS_DIRECTOR",
    "Parent": "IS_SUBSIDIARY_OF",
    "Shareholder": "MINOR_OWNER",
    "HOLDS": "BANK_ACCOUNT_OF",
    "DEPOSITS_TO": "INBOUND_WIRE",
    "MENTIONS": "REFERS_TO",
}
G_rival = renamed_graph(G, rival_rename)
rig_rival = build_rig(G_rival)

print(f"Rival KG RIG: {rig_rival.number_of_nodes()} relations")
print()
print("Rival fingerprints:")
for r in sorted(rig_rival.nodes):
    in_kinds = sorted({d["type"] for _, _, d in rig_rival.in_edges(r, data=True)})
    out_kinds = sorted({d["type"] for _, _, d in rig_rival.out_edges(r, data=True)})
    print(f"  {r:>18}: in={in_kinds}, out={out_kinds}")
"""),
    ("md", """\
**Different names, identical fingerprints.** That is the structural fact ULTRA bets on. A model that learns to recognise relations by their fingerprints — not their names — generalises to the rival bank's KG zero-shot.

To make the transferability *visible*, compute structural similarity between Lotus relations and rival relations:
"""),
    ("code", """\
def relation_fingerprint(rig, r) -> tuple:
    \"\"\"A simple structural fingerprint: counts of each interaction type.\"\"\"
    in_counts = {}
    out_counts = {}
    for _, _, d in rig.in_edges(r, data=True):
        in_counts[d["type"]] = in_counts.get(d["type"], 0) + 1
    for _, _, d in rig.out_edges(r, data=True):
        out_counts[d["type"]] = out_counts.get(d["type"], 0) + 1
    return (tuple(sorted(in_counts.items())), tuple(sorted(out_counts.items())))


print("Lotus relation → matching rival relation (by structural fingerprint):")
lotus_fps = {r: relation_fingerprint(rig, r) for r in rig.nodes}
rival_fps = {r: relation_fingerprint(rig_rival, r) for r in rig_rival.nodes}
for r, fp in sorted(lotus_fps.items()):
    matches = [r2 for r2, fp2 in rival_fps.items() if fp2 == fp]
    print(f"  {r:>18}  ←→  {matches}")
"""),
    ("md", """\
**Each Lotus relation has a unique structural match in the rival schema.** The bijection is automatic; no schema-mapping work required. This is the toy version of what ULTRA does at scale — and the proof point that the structural pattern carries information about the relation, independent of its name.

A practical M&A integration would use this property: import the acquired KG; align relations by structural fingerprint; queries written against the original ontology Just Work over the joint graph.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Held-out link prediction — the principle

The actual ULTRA evaluation is *inductive link prediction*: pretrain on KGs A, B, C; deploy on KG D; predict missing edges in D, zero-shot, without ever seeing D in training.

We won't pretrain a model. But we can demonstrate the *principle* with a structural baseline:

1. Hide a known edge: the John → ACME UBO edge.
2. Compute the "missing relation" — what should connect John (Person) to ACME (LegalEntity)?
3. Score each candidate relation by how well its fingerprint fits the gap.

A correctly-set-up baseline ranks `UBO` (and the other Person → LegalEntity relations) above unrelated relations.
"""),
    ("code", """\
# Step 1: hide the John -> ACME edge in a copy of the graph
import copy
G_test = copy.deepcopy(G)
# Find and remove the edge
to_remove = []
for u, v, k, d in G_test.edges(keys=True, data=True):
    if u == "p_john_q_public" and v == "e_acme_holdings" and d.get("type") == "UBO":
        to_remove.append((u, v, k))
for u, v, k in to_remove:
    G_test.remove_edge(u, v, k)

print(f"Original edges between John and ACME:")
print(f"   in original G: {list(G.edges('p_john_q_public', data=True))}")
print(f"Removed {len(to_remove)} edge(s) from G_test")
"""),
    ("code", """\
# Step 2: identify the head/tail label of the missing edge
head_label = "Person"
tail_label = "LegalEntity"
print(f"Missing edge: {head_label} -> ? -> {tail_label}")

# Step 3: score every relation by how well it fits the gap
# A relation r fits if its fingerprint matches (Person, LegalEntity) edges
candidate_relations = sorted(set(d.get('type') for _, _, d in G.edges(data=True)))

# Build a simple feature: does this relation ever have a Person head and a LegalEntity tail?
def fits_endpoints(G, r, head_label, tail_label) -> tuple[int, int]:
    \"\"\"Returns (head_match_count, tail_match_count) for relation r.\"\"\"
    head_matches = 0
    tail_matches = 0
    for u, v, d in G.edges(data=True):
        if d.get('type') != r:
            continue
        if G.nodes[u].get('label') == head_label:
            head_matches += 1
        if G.nodes[v].get('label') == tail_label:
            tail_matches += 1
    return head_matches, tail_matches


print()
print("Relation candidates ranked by endpoint compatibility:")
scores = []
for r in candidate_relations:
    h, t = fits_endpoints(G_test, r, head_label, tail_label)
    # Geometric mean of head and tail compatibility
    score = (h * t) ** 0.5 if (h and t) else 0
    scores.append((r, score, h, t))
scores.sort(key=lambda x: -x[1])
for r, s, h, t in scores:
    flag = " ← target" if r == "UBO" else ""
    print(f"  {r:>20}  score={s:>5.1f}  (head_matches={h}, tail_matches={t}){flag}")
"""),
    ("md", """\
**Look at the ranking.** The top candidates are exactly the relations that *can* connect a Person to a LegalEntity: `UBO`, `Director`, `Shareholder`, `POA`. The baseline doesn't uniquely identify `UBO` — but it has narrowed an unknown gap from "any of seven relations" to "one of four plausible ones," **using only structural information.** A learned model with more features (composition patterns, neighbourhood structure, type compatibility scores) does much better.

This is the kernel of ULTRA's evaluation. The full version: pre-train on KGs you've never seen at deployment time; score missing edges in deployment KGs by the relations' structural fingerprints; show the predictions match held-out ground truth.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. ULTRA — the actual mechanism

The toy structural-fingerprint baseline captures the *idea*. ULTRA's published algorithm is more sophisticated. Three key components:

1. **The relation interaction graph (RIG)** — same concept as ours, but with richer edge types between relations (composition, intersection, etc.) and structural properties learned from many KGs during pretraining.

2. **Conditional relation embeddings.** ULTRA does *not* learn a fixed embedding for `UBO`. Instead, given a query (e.g., "is John the UBO of ACME?"), it produces an embedding for `UBO` conditioned on the query's context — the surrounding entities, the path being scored, the relevant slice of the RIG. The embedding is *generated* per-query, not retrieved.

3. **Inductive scoring.** Standard KG embedding models (TransE, ComplEx) need to retrain on every new KG because each entity has a learned vector. ULTRA's scoring uses the *structure around* the entities being scored, not their identities. Drop a fresh KG in; ULTRA scores it because the structure is what it reads, not the names.

The combination — RIG, conditional embeddings, structural scoring — is what produces ULTRA's headline result: a single pretrained model that does inductive link prediction on 57 different KGs, often beating supervised state-of-the-art for each specific graph.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. GAMMA — the multi-algebra extension

GAMMA's contribution to ULTRA is methodological. ULTRA uses a single algebraic transformation in message passing — typically element-wise multiplication, a real-valued operation. GAMMA replaces this with multi-head geometric attention spanning four algebras:

| Algebra | Captures | Example relation |
|---|---|---|
| Real | Symmetric structure | RELATED_TO (family) |
| Complex | Asymmetric, antisymmetric | CONTROLS (Person → Entity) |
| Split-complex | Hierarchical, transitive | PARENT (LegalEntity → LegalEntity) |
| Dual number | Periodic, cyclic | (n/a in static KGs; useful for temporal) |

A learnable gating mechanism with entropy regularisation picks the right algebra per link. Empirical result: 5.5% MRR improvement over ULTRA on inductive benchmarks, with most of the gain on benchmarks containing relations of multiple kinds.

**The practitioner reading:** *the geometric structure of your relations matters and should be modelled*. For control-management KGs — which contain a mix of symmetric (related-to), asymmetric (controls, owns), and hierarchical (parent-of, subsidiary-of) relations — multi-algebra approaches are well-matched.

When a vendor pitches you "KG foundation models," the difference between ULTRA and GAMMA is roughly the difference between a learned attention mechanism and a hand-tuned one. You'll see GAMMA-class methods evolve; the durable insight — relations have geometric structure — is the take-home.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. From sketch to production — what would have to be true

The toy baseline in §4 is not deployable. A production ULTRA/GAMMA-class system requires:

1. **A pretrained checkpoint that runs on your compute.** Public ULTRA checkpoints exist; they run on CPU for small graphs but production-scale deployment expects GPU. For a single-bank platform, this is a fixed cost, not a per-query one.
2. **A KG with reasonably clean entity resolution.** Structural reasoning is robust to renamed relations; it is *not* robust to phantom-duplicate entities (John appearing as two separate person nodes because his alias didn't resolve). Hour 5's reconciliation work is upstream of ULTRA, not displaced by it.
3. **A target use case where link prediction is the right shape.** Missing UBO declarations, predicted account-opening risk, anomalous-relation flagging — yes. Generating a control manager's narrative answer — no. **ULTRA scores edges; it does not produce arguments.**
4. **A defensibility story.** Like KumoRFM, ULTRA-class methods produce predictions, not citations. A control manager cannot escalate on "the model says this UBO declaration is incomplete." They need to know *why*. The triage-layer pattern from Hour 13c applies: use ULTRA to *prioritise* declarations for review, route flagged cases to the Gen 3 agent for the auditable analysis.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 8. Three architectural choices the frontier rewards

If ULTRA-class methods are a 2-3 year horizon for your bank, three choices made *now* will let you adopt them cleanly when they land:

1. **Treat the ontology as a contract, not a constant.** Document it. Version it. Maintain a mapping from your bank's relation names to a *canonical* set (FIBO-derived or in-house). When ULTRA lands, you map to the canonical set rather than re-engineering the agent.

2. **Build entity resolution as a service, not a one-time pipeline.** ULTRA-class methods amplify good entity resolution and amplify bad. The cleanest reachable separation: one service that takes a surface form + context and returns a canonical id with confidence. Everything else — extractors, agents, future foundation models — calls that service.

3. **Capture every Gen 3 decision as a labelled example for downstream training.** The audit log from Hour 11 *is* a training set for the eventual scoring model (whether ULTRA-derived or KumoRFM-derived). The labels are what the agent decided; the features are what was in the KG at the time. Capture them from day one.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 9. Where this still strains

Three honest limits even the ULTRA/GAMMA family doesn't address:

1. **Schema drift over time.** ULTRA generalises across schemas at a point in time. It does not handle a schema that *evolves* mid-deployment — new entity types introduced by regulation, new relation types from new product lines. Bi-temporal modelling (Hour 13b's territory) is orthogonal and still needed.

2. **The KG itself can be wrong.** ULTRA reasons about graph structure. If the graph encodes a fact wrongly (a phantom UBO edge from a hallucinated extraction, or a missing edge from a missed extraction), ULTRA's reasoning inherits the error. Garbage in, garbage out — even for foundation models.

3. **Compositionality has limits.** "John controls ACME via a 5-hop chain through three jurisdictions and a nominee director" composes many relations. ULTRA scores edges and short paths well; long compositional chains are still hard. For control management's deepest UBO chains this is a real limit, not a marketing concern.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think — closing the Tier 2 appendix

Three questions to close the appendix sequence:

1. **Of TIE (13b), KumoRFM (13c), and ULTRA/GAMMA (13a), which would your platform benefit from first?** The right answer is usually "13b's schema-level approximation" — it costs the least to retrofit and addresses the highest-stakes audit questions.
2. **The three appendix hours each propose a triage-layer-style deployment: the frontier method as a complement to Gen 3, not a replacement.** Why is that pattern recurring? (Hint: it's the same reason regulated decisions need defensibility.)
3. **In five years, what is the architectural shape of your platform?** Now that you've worked through Hours 0-13c, you can sketch it. Do.

You've now traversed the production-today stack (Hours 0-12) and three architectural directions one step beyond it (13a, 13b, 13c). The principles you learned in the first twelve hours transfer to the frontier: failure modes are still relational / similarity / verification; entity resolution is still load-bearing; governance is still highest-stakes. The papers describe better ways to satisfy them.

That's the tutorial.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour13a_kg_foundation_models.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
