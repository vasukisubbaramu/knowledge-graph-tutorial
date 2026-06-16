"""A tiny hypergraph implementation for Hour 10.

A hypergraph generalizes a graph: an edge (hyperedge) can connect *any
number* of nodes, not just two. The financial-transaction motivating
example: a deposit has at least seven participants — origin entity,
beneficiary account, amount, currency, jurisdiction, value date,
purpose — and modeling them as binary edges loses the joint structure.

Implementation choices:
  - A hyperedge is a typed set of participant ids, each with a role.
  - Hyperedges have properties (amount, date, etc.) like LPG edges.
  - We don't try to implement a hypergraph database; we represent and
    query the structure in pure Python and visualize it with NetworkX's
    bipartite layout (which renders hyperedges as nodes).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Hyperedge:
    """One n-ary relation instance.

    Example:
        Hyperedge(
            id="dep_001",
            type="Deposit",
            roles={
                "originator": "e_atlas_wirecorp",
                "beneficiary_account": "a_gamma_001",
                "jurisdiction_origin": "AE",
                "jurisdiction_destination": "LI",
            },
            properties={"amount_eur": 500_000.0, "value_date": "2026-06-03"},
        )
    """

    id: str
    type: str
    roles: dict[str, str]            # role-name -> participant id
    properties: dict = field(default_factory=dict)

    def participants(self) -> set[str]:
        return set(self.roles.values())


# ---------------------------------------------------------------------------
# Hypergraph container
# ---------------------------------------------------------------------------

@dataclass
class Hypergraph:
    """A set of hyperedges plus a registry of nodes for convenience."""

    nodes: dict[str, dict] = field(default_factory=dict)   # node_id -> attrs
    hyperedges: list[Hyperedge] = field(default_factory=list)

    def add_node(self, node_id: str, **attrs) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = {}
        self.nodes[node_id].update(attrs)

    def add_hyperedge(self, he: Hyperedge) -> None:
        for p in he.participants():
            if p not in self.nodes:
                self.add_node(p, label="(implicit)")
        self.hyperedges.append(he)

    # ----- queries -----

    def hyperedges_involving(self, node_id: str, role: str | None = None) -> list[Hyperedge]:
        """All hyperedges that have this node as a participant.

        If `role` is given, restrict to hyperedges where the node is in
        that specific role (e.g. role='originator' for deposits).
        """
        out = []
        for he in self.hyperedges:
            if role is not None:
                if he.roles.get(role) == node_id:
                    out.append(he)
            elif node_id in he.participants():
                out.append(he)
        return out

    def co_participants(self, node_id: str) -> dict[str, int]:
        """Other nodes that share at least one hyperedge with this one.

        Returns a count map: each co-participant -> number of hyperedges
        in common. Useful for "who is connected to this account through
        transactions?" type questions.
        """
        out: dict[str, int] = defaultdict(int)
        for he in self.hyperedges_involving(node_id):
            for p in he.participants():
                if p != node_id:
                    out[p] += 1
        return dict(out)

    def stats(self) -> dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "hyperedges": len(self.hyperedges),
            "avg_arity": round(
                sum(len(he.participants()) for he in self.hyperedges) / max(len(self.hyperedges), 1),
                2,
            ),
        }


# ---------------------------------------------------------------------------
# Convert Deposits into Hyperedges (the Hour 10 worked example)
# ---------------------------------------------------------------------------

def deposit_to_hyperedge(deposit) -> Hyperedge:
    """Map a Deposit (Pydantic schema) to a single hyperedge.

    Roles capture *who participates in what capacity* — exactly the
    distinction a binary edge cannot make.
    """
    # Synthesize a counterparty node id from the counterparty string,
    # since deposits don't link to canonical entities by id.
    cp_node = f"cp:{deposit.counterparty_name.lower().replace(' ', '_')}"
    return Hyperedge(
        id=deposit.id,
        type="Deposit",
        roles={
            "originator_name": cp_node,
            "beneficiary_account": deposit.account_id,
            "jurisdiction_origin": f"juris:{deposit.counterparty_country}",
            "currency": f"ccy:{deposit.original_currency}",
            "purpose": f"purpose:{deposit.purpose_code}",
        },
        properties={
            "amount_eur": deposit.amount_eur,
            "original_amount": deposit.original_amount,
            "value_date": deposit.value_date.isoformat(),
            "narrative": deposit.narrative,
        },
    )


def build_lotus_hypergraph(bundle) -> Hypergraph:
    """Build the Lotus hypergraph: deposits as hyperedges, plus the structural KG nodes."""
    hg = Hypergraph()
    for p in bundle.persons:
        hg.add_node(p.id, label="Person", name=p.full_name)
    for e in bundle.entities:
        hg.add_node(e.id, label="LegalEntity", name=e.legal_name)
    for a in bundle.accounts:
        hg.add_node(a.id, label="Account", number=a.account_number)
    for d in bundle.deposits:
        hg.add_hyperedge(deposit_to_hyperedge(d))
    return hg


# ---------------------------------------------------------------------------
# Visualization (bipartite via NetworkX)
# ---------------------------------------------------------------------------

def draw_hypergraph(hg: Hypergraph, *, hyperedge_filter=None, title: str = "Hypergraph"):
    """Render a hypergraph as a bipartite graph.

    Real nodes are circles; hyperedges are squares. An edge in the
    bipartite rendering means "this node participates in this hyperedge."
    """
    import matplotlib.pyplot as plt
    import networkx as nx

    G = nx.Graph()
    for nid in hg.nodes:
        G.add_node(nid, bipartite=0)
    selected = hg.hyperedges if hyperedge_filter is None else [h for h in hg.hyperedges if hyperedge_filter(h)]
    for he in selected:
        he_label = f"[{he.type}]\n{he.id}"
        G.add_node(he_label, bipartite=1)
        for participant in he.participants():
            G.add_edge(participant, he_label)

    # Bipartite layout
    real_nodes = [n for n, a in G.nodes(data=True) if a.get("bipartite") == 0]
    he_nodes = [n for n, a in G.nodes(data=True) if a.get("bipartite") == 1]
    pos = nx.bipartite_layout(G, real_nodes)

    fig, ax = plt.subplots(figsize=(13, 9))
    nx.draw_networkx_nodes(G, pos, nodelist=real_nodes, node_color="#a3c9f1", node_shape="o", node_size=1300, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=he_nodes, node_color="#f7c685", node_shape="s", node_size=1800, ax=ax)
    nx.draw_networkx_edges(G, pos, alpha=0.4, ax=ax)
    labels = {n: (hg.nodes.get(n, {}).get("name") or n)[:18] for n in real_nodes}
    labels.update({n: n for n in he_nodes})
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7, ax=ax)
    ax.set_title(title)
    ax.axis("off")
    plt.tight_layout()
    plt.show()
