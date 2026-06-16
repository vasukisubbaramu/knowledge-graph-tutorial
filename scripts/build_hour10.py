"""Build notebooks/hour10_hypergraphs.ipynb — Gen 3 hypergraphs hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 10 — Gen 3: Hypergraphs

> *60 minutes dense, 2–3 hours to absorb. We re-model the Lotus deposit as a single hyperedge that connects every participant at once — and watch what becomes expressible that was contorted in the binary-edge model. By the end you'll know when to reach for hypergraphs in production.*

**Reading companion:** [`docs/hour10.md`](../docs/hour10.md).
"""),
    ("code", """\
from kg_tutorial import config, llm, display
from kg_tutorial.data import load
from kg_tutorial.hyper import Hyperedge, Hypergraph, build_lotus_hypergraph, draw_hypergraph

config.verify()
bundle = load.load()
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. Why binary edges aren't enough

A binary edge connects two nodes. That works perfectly for "John controls ACME": one edge, two participants, done.

It does not work cleanly for a *deposit*. A real deposit is the joint occurrence of *all* of:

- An originating entity
- A beneficiary account
- An amount (in a currency)
- A jurisdiction of origin
- A jurisdiction of destination
- A value date
- A purpose code
- A source-of-funds narrative
- An originating bank

The relationship is "all these things happened together." Modeling it as binary edges fragments the joint structure. You end up with:

```
(Deposit_node) --[has_originator]--> (Counterparty)
(Deposit_node) --[has_account]--> (Account)
(Deposit_node) --[has_amount]--> (Amount_node)
(Deposit_node) --[has_currency]--> (Currency_node)
... and so on
```

Each edge is binary, but the deposit-node is a *promoted relationship* — a node that exists only to hold the joint structure. This is the **reification** problem. It works, but every query over "the deposit's participants" requires multiple joins.

A **hyperedge** is the direct fix: a single typed relation that connects all participants at once.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. A hyperedge in code

The data type is in `kg_tutorial.hyper.Hyperedge`. The Lotus deposit:
"""),
    ("code", """\
import inspect
print(inspect.getsource(Hyperedge))
"""),
    ("code", """\
# The Lotus deposit as a hyperedge
dep = bundle.deposits[0]
he = Hyperedge(
    id=dep.id,
    type="Deposit",
    roles={
        "originator": "e_atlas_wirecorp",        # entity, not just the string name
        "beneficiary_account": dep.account_id,
        "jurisdiction_origin": "AE",
        "jurisdiction_destination": "LI",
        "currency": dep.original_currency,
        "purpose_code": dep.purpose_code,
    },
    properties={"amount_eur": dep.amount_eur, "value_date": str(dep.value_date)},
)
print("Hyperedge:", he)
print(f"Participants: {sorted(he.participants())}")
print(f"Arity: {len(he.participants())}")
"""),
    ("md", """\
**Six participants, one relation, one identity.** The deposit's joint identity is preserved.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. The Lotus hypergraph

Build a hypergraph from the full bundle and inspect it.
"""),
    ("code", """\
hg = build_lotus_hypergraph(bundle)
print(f"Stats: {hg.stats()}")

# Every hyperedge in the system
print()
print(f"First 3 hyperedges:")
for he in hg.hyperedges[:3]:
    print(f"  {he.id} [{he.type}]")
    for role, pid in he.roles.items():
        print(f"      {role:>25}: {pid}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. Visualize as bipartite — the canonical hypergraph rendering

A hypergraph is rendered by promoting hyperedges to *square nodes* and connecting them to their participants (which stay as circles). The structure is a bipartite graph where one side is real entities and the other is hyperedges.
"""),
    ("code", """\
# Filter to just the Lotus-relevant nodes and the dep_001 hyperedge
focal_hg = Hypergraph()
focal_he = next(h for h in hg.hyperedges if h.id == "dep_001")
focal_hg.add_hyperedge(focal_he)
# Decorate node labels for display
for nid in focal_he.participants():
    focal_hg.nodes[nid] = hg.nodes.get(nid, {"label": "?", "name": nid})

draw_hypergraph(focal_hg, title="The Lotus deposit as a hyperedge")
"""),
    ("md", """\
**Read the drawing.** One square in the middle — the deposit. Six circles around it — the participants. Every line says "this participant is in this role of this hyperedge." The roles aren't drawn (visual clutter), but they're attached to the edge in the data.

This is **the natural representation of a transaction**. The query "all things involved in deposit dep_001" is now: one lookup.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. Queries the binary model makes hard

Three example queries the hypergraph makes easy and the binary model contorts.

### Q1 — All hyperedges involving Atlas Wirecorp as originator
"""),
    ("code", """\
matches = hg.hyperedges_involving("e_atlas_wirecorp", role="originator")
print(f"Atlas Wirecorp as originator: {len(matches)} hyperedge(s)")
for h in matches:
    print(f"  {h.id} ({h.type}, EUR {h.properties.get('amount_eur', 0):,.0f}) on {h.properties.get('value_date')}")
"""),
    ("md", """\
The query is structurally one lookup. In the binary model, you'd need to: traverse from Atlas to its outbound has_originator edges, then to their Deposit-node, then collect the deposits' properties. The hypergraph collapses the chain.
"""),
    ("md", """\
### Q2 — All accounts that received deposits from Liechtenstein jurisdictions
"""),
    ("code", """\
# Aggregate over all hyperedges where the destination jurisdiction is LI
matches = [
    h for h in hg.hyperedges
    if h.type == "Deposit" and h.roles.get("jurisdiction_destination") == "LI"
]
print(f"Deposits with LI destination: {len(matches)}")
"""),
    ("md", """\
The roles are first-class — querying "all deposits where role X is Y" is direct. In the binary model, you'd reify a jurisdiction-edge and join it back to the deposit-node.
""")
    ,
    ("md", """\
### Q3 — All entities that share at least one hyperedge with the Gamma account
"""),
    ("code", """\
co = hg.co_participants("a_gamma_001")
print(f"Co-participants of a_gamma_001 (top 10):")
for nid, count in sorted(co.items(), key=lambda x: -x[1])[:10]:
    label = hg.nodes.get(nid, {}).get("name", nid)
    print(f"  {nid:>30}  shared edges: {count}")
"""),
    ("md", """\
"Show me everything that ever touched this account" is a single sweep over the hyperedges. The binary model would require traversing every Deposit node and collecting their non-account participants.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. When to actually reach for hypergraphs

Three honest tests for whether your domain wants hypergraphs:

1. **Do your interesting relations have more than 2 participants?** Deposits do (5-9). UBO chains do not (always 2). Sanctions matching does not.
2. **Do you frequently query "everything involved in this event"?** Transaction monitoring yes. Customer details no.
3. **Do role-based queries dominate?** ("All hyperedges where Atlas is originator" — yes for AML; "all hyperedges where ACME is a participant in any role" — also yes.)

If two of three are yes, hypergraphs earn their keep. If you're not sure, **start binary, promote to hyperedge when the joint queries get hard**.

Neo4j and most LPG databases don't have native hyperedge support — they emulate it via reification (the Deposit-node pattern). Native hypergraph stores exist (AllegroGraph for RDF-style; some research databases) but are uncommon. **Most production systems live with reification.** Hypergraphs are first-class in *modelling*; binary edges are first-class in *storage*. The model is the hypergraph; the storage is reified. The translation is mechanical.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. HyperGraphRAG — the retrieval pattern

Recent work (HyperGraphRAG, 2024-25) demonstrates retrieval over hypergraphs for question answering, using hyperedge-level embeddings (an embedding of the whole n-ary fact) rather than node-level embeddings. The retrieval question becomes "which hyperedges are most relevant to the query," not "which nodes are most similar." For transaction-shaped questions this dramatically reduces retrieval noise — you don't get back fragments that need to be re-joined; you get back the whole event.

We don't implement HyperGraphRAG here. The conceptual sketch:

```
Query embedding -> nearest hyperedge embeddings -> retrieved hyperedges -> LLM
```

The implementation work is in the embedding step — how do you embed an n-ary fact? Two common approaches: concatenate the participants' names and embed; or learn a joint embedding from triples. For the tutorial, knowing the *pattern* matters more than implementing the embedding.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 11

Three questions:

1. **For your platform's most common transaction type, list its participants and roles.** If the count is > 4, you have a hyperedge candidate.
2. **In our Lotus dataset, every deposit has 5 participants (originator name, beneficiary account, jurisdiction origin, currency, purpose).** Look at `dep_noise_000` — does the structure still hold? What if some role is missing for a particular deposit?
3. **The reified-binary representation is what Neo4j stores. The hypergraph representation is what you query against.** When you write the *query layer*, do you query the hypergraph or the reified graph? Discuss.

Next: [Hour 11 — End-to-end Control Manager agent](./hour11_control_manager_agent.ipynb). The Lotus question answered the full Gen 3 way, with reasoning trace and citations.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour10_hypergraphs.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
