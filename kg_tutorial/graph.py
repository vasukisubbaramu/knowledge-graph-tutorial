"""Graph helpers — NetworkX for visualization, Neo4j for the real KG.

Importing this module is cheap. The Neo4j driver is loaded only when
`GraphDB()` is instantiated, so notebooks that only need the NetworkX
side (Hour 4) work without Neo4j installed.

What's here:
- bundle_to_networkx()  — Pydantic data → NetworkX graph for inspection
- draw_lotus()          — quick matplotlib visualization
- GraphDB               — thin Neo4j wrapper
- networkx_to_text()    — serialize a subgraph as text for an LLM prompt
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from kg_tutorial import config
from kg_tutorial.data.schema import DatasetBundle


# ---------------------------------------------------------------------------
# Pydantic → NetworkX
# ---------------------------------------------------------------------------

def bundle_to_networkx(bundle: DatasetBundle) -> nx.MultiDiGraph:
    """Build a directed multigraph from the synthetic dataset.

    Node labels (.nodes[id]['label']):
      - "Person", "LegalEntity", "Account", "SanctionsRecord", "AdverseMediaItem"

    Edge attributes:
      - 'type' = the relationship name (e.g. "UBO", "PARENT", "DIRECTOR", "HOLDS", "DEPOSITS_TO")
      - other attributes depend on the relationship (ownership_pct, value_date, ...)

    A MultiDiGraph because the same pair of nodes can have multiple edges of
    different types (e.g. Person → Entity can be both UBO and DIRECTOR).
    """
    g = nx.MultiDiGraph()

    for p in bundle.persons:
        g.add_node(
            p.id,
            label="Person",
            name=p.full_name,
            is_pep=p.is_pep,
            residence_country=p.residence_country,
        )

    for e in bundle.entities:
        g.add_node(
            e.id,
            label="LegalEntity",
            name=e.legal_name,
            jurisdiction=e.jurisdiction,
            entity_type=e.entity_type.value,
        )

    for a in bundle.accounts:
        g.add_node(
            a.id,
            label="Account",
            account_number=a.account_number,
            status=a.status,
        )
        g.add_edge(a.holder_entity_id, a.id, type="HOLDS")

    for c in bundle.controls:
        g.add_edge(
            c.controller_id,
            c.controlled_id,
            type=c.control_type.value,
            ownership_pct=c.ownership_pct,
            source=c.source,
        )

    for d in bundle.deposits:
        # Deposits aren't first-class nodes by default in Hour 4 — Hour 10
        # promotes them to hyperedges. For now we materialize the
        # counterparty as an edge attribute.
        g.add_edge(
            d.id,  # synthetic deposit node ID
            d.account_id,
            type="DEPOSITS_TO",
            amount_eur=d.amount_eur,
            counterparty_name=d.counterparty_name,
            counterparty_country=d.counterparty_country,
            value_date=str(d.value_date),
        )
        g.add_node(
            d.id,
            label="Deposit",
            amount_eur=d.amount_eur,
            counterparty_name=d.counterparty_name,
        )

    for s in bundle.sanctions:
        g.add_node(
            s.id,
            label="SanctionsRecord",
            name=s.name,
            list_source=s.list_source.value,
            country=s.country,
        )

    for am in bundle.adverse_media:
        g.add_node(
            am.id,
            label="AdverseMediaItem",
            headline=am.headline,
            source=am.source_outlet,
            sentiment=am.sentiment,
        )
        for mid in am.mentioned_ids:
            g.add_edge(am.id, mid, type="MENTIONS")

    return g


def lotus_subgraph(g: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Return only the Lotus-case nodes — the four persons, four entities,
    one account, the Atlas sanctions record, plus relevant edges between
    them. Useful for visualization without noise.
    """
    keep = {
        "p_john_q_public", "p_alice_public", "p_maria_rossi", "p_tomas_velasco",
        "e_gamma_ops", "e_alphabeta_trading", "e_acme_holdings", "e_atlas_wirecorp",
        "a_gamma_001",
        "dep_001",
        "s_atlas",
        "am_offshore_clipping_2024",
    }
    return g.subgraph(keep).copy()


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

NODE_COLORS = {
    "Person": "#a3c9f1",
    "LegalEntity": "#f7c685",
    "Account": "#c5e1a5",
    "Deposit": "#e1bee7",
    "SanctionsRecord": "#ef9a9a",
    "AdverseMediaItem": "#fff59d",
}


def draw_graph(
    g: nx.MultiDiGraph,
    title: str = "",
    *,
    figsize: tuple[int, int] = (12, 8),
    layout: str = "spring",
    show_edge_labels: bool = True,
):
    """Draw a NetworkX graph with sensible defaults for the Lotus case.

    `layout`: "spring" (default), "circular", or "kamada_kawai". Spring is
    a force-directed layout; it tends to put structurally-similar nodes
    near each other. Kamada-Kawai is steadier across runs.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize)

    if layout == "spring":
        pos = nx.spring_layout(g, seed=7, k=1.5)
    elif layout == "kamada_kawai":
        pos = nx.kamada_kawai_layout(g)
    elif layout == "circular":
        pos = nx.circular_layout(g)
    else:
        raise ValueError(f"Unknown layout: {layout}")

    # Nodes, coloured by label
    for label, colour in NODE_COLORS.items():
        nodes = [n for n, attrs in g.nodes(data=True) if attrs.get("label") == label]
        if nodes:
            nx.draw_networkx_nodes(g, pos, nodelist=nodes, node_color=colour, node_size=1500, ax=ax, label=label)

    # Node labels — show name if present, else id
    labels = {n: (a.get("name") or a.get("headline") or n)[:24] for n, a in g.nodes(data=True)}
    nx.draw_networkx_labels(g, pos, labels=labels, font_size=8, ax=ax)

    # Edges with arrows
    nx.draw_networkx_edges(g, pos, ax=ax, arrows=True, arrowsize=18, edge_color="#888", width=1.2, connectionstyle="arc3,rad=0.08")

    # Edge labels = relationship type
    if show_edge_labels:
        edge_labels: dict[tuple[str, str], str] = {}
        for u, v, data in g.edges(data=True):
            t = data.get("type", "")
            pct = data.get("ownership_pct")
            label = f"{t}({pct:.0f}%)" if pct is not None else t
            edge_labels[(u, v)] = label
        nx.draw_networkx_edge_labels(g, pos, edge_labels=edge_labels, font_size=7, ax=ax)

    ax.set_title(title)
    ax.legend(loc="lower left", fontsize=8)
    ax.axis("off")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# Subgraph → text (for LLM context)
# ---------------------------------------------------------------------------

def networkx_to_text(g: nx.MultiDiGraph) -> str:
    """Serialize a graph as a human/LLM-readable list of triples.

    The format is deliberately simple — one fact per line — because LLMs
    parse it cleanly and a control manager reviewing the prompt can spot
    errors at a glance.
    """
    lines: list[str] = ["NODES:"]
    for n, attrs in g.nodes(data=True):
        label = attrs.get("label", "?")
        name = attrs.get("name") or attrs.get("headline") or n
        extras = {k: v for k, v in attrs.items() if k not in {"label", "name", "headline"} and v is not None}
        extra_str = ", ".join(f"{k}={v}" for k, v in extras.items())
        lines.append(f"  ({n}) [{label}] {name}" + (f" — {extra_str}" if extra_str else ""))

    lines.append("")
    lines.append("EDGES:")
    for u, v, attrs in g.edges(data=True):
        t = attrs.get("type", "?")
        extras = {k: val for k, val in attrs.items() if k != "type" and val is not None}
        extra_str = ", ".join(f"{k}={val}" for k, val in extras.items())
        lines.append(f"  ({u}) --[{t}]--> ({v})" + (f"   {{{extra_str}}}" if extra_str else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------

@dataclass
class GraphDB:
    """Thin Neo4j wrapper.

    Connection is opened lazily on first use. Re-instantiating is cheap;
    don't worry about pooling at tutorial scale.

    Usage:
        db = GraphDB()
        db.reset()                      # wipe everything
        db.load_bundle(bundle)          # write the Lotus graph
        results = db.query("MATCH (n:Person) RETURN n.name AS name")
        db.close()
    """

    uri: str = config.NEO4J_URI
    user: str = config.NEO4J_USER
    password: str = config.NEO4J_PASSWORD
    _driver: Any = None

    def __post_init__(self):
        # Defer the import so this module is usable without neo4j installed
        try:
            from neo4j import GraphDatabase
        except ImportError as e:
            raise RuntimeError(
                "Neo4j driver not installed. Run: pip install neo4j"
            ) from e
        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def reset(self) -> None:
        with self._driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        with self._driver.session() as s:
            return [r.data() for r in s.run(cypher, params or {})]

    def count_by_label(self) -> dict[str, int]:
        rows = self.query("MATCH (n) RETURN labels(n) AS labels, count(*) AS n")
        out: dict[str, int] = {}
        for r in rows:
            for label in r["labels"] or ["(none)"]:
                out[label] = out.get(label, 0) + r["n"]
        return out

    # ----- bulk load from the canonical Pydantic data -----

    def load_bundle(self, bundle: DatasetBundle) -> None:
        """Write the Lotus + noise graph to Neo4j.

        Persons and LegalEntities get their own labels for fast traversal.
        Control relationships become typed edges using `apoc.create.relationship`
        if APOC is available, falling back to per-type Cypher otherwise. We
        use the latter here so this works on a plain Neo4j Community DB.
        """
        with self._driver.session() as s:
            # Persons
            for p in bundle.persons:
                s.run(
                    "MERGE (p:Person {id: $id}) "
                    "SET p.full_name = $name, p.is_pep = $is_pep, "
                    "    p.residence_country = $rc, p.pep_reason = $pep_reason",
                    {
                        "id": p.id, "name": p.full_name, "is_pep": p.is_pep,
                        "rc": p.residence_country, "pep_reason": p.pep_reason,
                    },
                )

            # Legal entities
            for e in bundle.entities:
                s.run(
                    "MERGE (e:LegalEntity {id: $id}) "
                    "SET e.legal_name = $name, e.jurisdiction = $juris, "
                    "    e.entity_type = $etype, e.notes = $notes",
                    {
                        "id": e.id, "name": e.legal_name, "juris": e.jurisdiction,
                        "etype": e.entity_type.value, "notes": e.notes,
                    },
                )

            # Accounts
            for a in bundle.accounts:
                s.run(
                    "MERGE (a:Account {id: $id}) "
                    "SET a.account_number = $num, a.status = $status, a.currency = $curr",
                    {"id": a.id, "num": a.account_number, "status": a.status, "curr": a.currency},
                )
                s.run(
                    "MATCH (e:LegalEntity {id: $eid}), (a:Account {id: $aid}) "
                    "MERGE (e)-[:HOLDS]->(a)",
                    {"eid": a.holder_entity_id, "aid": a.id},
                )

            # Control edges — plain MERGE works on Neo4j 4.x and 5.x.
            # The (a)-[r:CONTROLS {control_type: $ctype}]->(b) pattern in
            # MERGE looks for an existing edge with that exact control_type
            # and creates one if not found.
            for c in bundle.controls:
                ctrl_label = "Person" if c.controller_id.startswith("p_") else "LegalEntity"
                s.run(
                    f"MATCH (a:{ctrl_label} {{id: $ctrl}}), (b:LegalEntity {{id: $ctrld}}) "
                    "MERGE (a)-[r:CONTROLS {control_type: $ctype}]->(b) "
                    "SET r.ownership_pct = $pct, r.source = $src",
                    {
                        "ctrl": c.controller_id, "ctrld": c.controlled_id,
                        "ctype": c.control_type.value,
                        "pct": c.ownership_pct, "src": c.source,
                    },
                )

            # Sanctions records
            for sanc in bundle.sanctions:
                s.run(
                    "MERGE (s:SanctionsRecord {id: $id}) "
                    "SET s.name = $name, s.aliases = $aliases, "
                    "    s.list_source = $list, s.country = $country, s.reason = $reason",
                    {
                        "id": sanc.id, "name": sanc.name, "aliases": sanc.aliases,
                        "list": sanc.list_source.value, "country": sanc.country, "reason": sanc.reason,
                    },
                )

            # Adverse media + MENTIONS edges
            for am in bundle.adverse_media:
                s.run(
                    "MERGE (m:AdverseMediaItem {id: $id}) "
                    "SET m.headline = $h, m.snippet = $snip, m.source_outlet = $src, "
                    "    m.sentiment = $sent, m.topics = $topics",
                    {
                        "id": am.id, "h": am.headline, "snip": am.snippet,
                        "src": am.source_outlet, "sent": am.sentiment, "topics": am.topics,
                    },
                )
                for mid in am.mentioned_ids:
                    s.run(
                        "MATCH (m:AdverseMediaItem {id: $mid}) "
                        "MATCH (t {id: $tid}) "  # Person OR LegalEntity
                        "MERGE (m)-[:MENTIONS]->(t)",
                        {"mid": am.id, "tid": mid},
                    )

            # Deposits — model as nodes (Hour 10 will revisit as hyperedges)
            for d in bundle.deposits:
                s.run(
                    "MERGE (d:Deposit {id: $id}) "
                    "SET d.amount_eur = $amt, d.original_amount = $oamt, "
                    "    d.original_currency = $curr, d.value_date = date($date), "
                    "    d.counterparty_name = $cp, d.counterparty_country = $ctry, "
                    "    d.narrative = $narr, d.purpose_code = $code",
                    {
                        "id": d.id, "amt": d.amount_eur, "oamt": d.original_amount,
                        "curr": d.original_currency, "date": str(d.value_date),
                        "cp": d.counterparty_name, "ctry": d.counterparty_country,
                        "narr": d.narrative, "code": d.purpose_code,
                    },
                )
                s.run(
                    "MATCH (d:Deposit {id: $did}), (a:Account {id: $aid}) "
                    "MERGE (d)-[:DEPOSITS_TO]->(a)",
                    {"did": d.id, "aid": d.account_id},
                )

    # ----- subgraph utilities -----

    def subgraph_around(
        self,
        node_id: str,
        depth: int = 2,
    ) -> list[dict]:
        """Return the subgraph within `depth` hops of a node, as a list of rows.

        Used by Hour 6 to package a relevant slice of the KG as LLM context.
        """
        cypher = """
        MATCH path = (n {id: $nid})-[*1..$depth]-(m)
        WITH path
        UNWIND relationships(path) AS r
        WITH DISTINCT r, startNode(r) AS a, endNode(r) AS b
        RETURN labels(a) AS a_labels, a.id AS a_id,
               coalesce(a.full_name, a.legal_name, a.name, a.headline, a.id) AS a_name,
               type(r) AS rel,
               properties(r) AS rel_props,
               labels(b) AS b_labels, b.id AS b_id,
               coalesce(b.full_name, b.legal_name, b.name, b.headline, b.id) AS b_name
        """
        return self.query(cypher.replace("$depth", str(depth)), {"nid": node_id})


def neo4j_subgraph_to_text(rows: list[dict]) -> str:
    """Convert the output of GraphDB.subgraph_around() into LLM-prompt text."""
    lines: list[str] = []
    seen_nodes: set[str] = set()
    for r in rows:
        for prefix in ("a", "b"):
            nid = r[f"{prefix}_id"]
            if nid in seen_nodes:
                continue
            seen_nodes.add(nid)
            labels = ":".join(r[f"{prefix}_labels"])
            lines.append(f"  ({nid}) [{labels}] {r[f'{prefix}_name']}")
    text = "NODES:\n" + "\n".join(lines) + "\n\nEDGES:"
    edge_lines = []
    for r in rows:
        props = ", ".join(f"{k}={v}" for k, v in (r["rel_props"] or {}).items() if v is not None)
        edge = f"  ({r['a_id']}) --[{r['rel']}]--> ({r['b_id']})"
        if props:
            edge += f"   {{{props}}}"
        edge_lines.append(edge)
    return text + "\n" + "\n".join(edge_lines)
