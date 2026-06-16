"""Tools an agent can call — each is a small, focused capability.

The point of this module: take the things the agent might need to *do* —
fuzzy match a name, look up sanctions, query the graph, search documents —
and expose each as a pure function with a documented signature. The agent
in Hour 8/11 picks among them based on the question.

Two conventions:
  - Every tool returns a `ToolResult` so the agent can inspect what came
    back without knowing the call internals.
  - Every tool is callable by hand, with no agent. The Hour 7 notebook
    exercises them directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from kg_tutorial import config, llm
from kg_tutorial.data import load


# ---------------------------------------------------------------------------
# Common return type
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Standard envelope for everything a tool returns.

    Why a wrapper: the agent in Hour 11 inspects `confidence` and `evidence`
    to decide whether the tool's answer is good enough or whether it should
    call another tool. A raw return value is harder to reason over.
    """

    tool: str
    summary: str                # one-line human-readable answer
    confidence: float = 1.0     # 0..1; 1.0 = the tool is deterministic
    evidence: dict = field(default_factory=dict)  # raw payload for citation
    notes: str = ""             # caveats the tool surfaced


# ---------------------------------------------------------------------------
# Fuzzy name match
# ---------------------------------------------------------------------------

def fuzzy_name_match(query_name: str, *, list_kind: str = "sanctions") -> ToolResult:
    """Score a name against every entry on a list. Return any hits >= 70.

    `list_kind` selects the corpus: "sanctions" (the OFAC/UN/EU list) or
    "internal_entities" (our own LegalEntity table).

    The score is SequenceMatcher.ratio() * 100 — a simple, deterministic
    baseline. Production would use Jaro-Winkler or a learned matcher; the
    *shape* of the answer is the same.
    """
    q = query_name.upper().strip()
    bundle = load.load()

    candidates: list[tuple[str, str, list[str]]] = []  # (id, primary_name, all_names)
    if list_kind == "sanctions":
        for s in bundle.sanctions:
            candidates.append((s.id, s.name, [s.name] + s.aliases))
    elif list_kind == "internal_entities":
        for e in bundle.entities:
            candidates.append((e.id, e.legal_name, [e.legal_name] + e.aliases))
    else:
        raise ValueError(f"Unknown list_kind: {list_kind}")

    hits = []
    for cid, primary, names in candidates:
        best = max(
            SequenceMatcher(None, q, n.upper().strip()).ratio() * 100 for n in names
        )
        if best >= 70:
            hits.append({"id": cid, "name": primary, "score": round(best, 1)})

    hits.sort(key=lambda h: -h["score"])
    if not hits:
        return ToolResult(
            tool="fuzzy_name_match",
            summary=f"No matches for '{query_name}' on {list_kind} list above 70% similarity.",
            confidence=1.0,
            evidence={"hits": []},
        )

    top = hits[0]
    flag = "ESCALATE" if top["score"] >= 85 else "REVIEW"
    return ToolResult(
        tool="fuzzy_name_match",
        summary=f"{flag}: best match '{top['name']}' at {top['score']}% (policy threshold: 85%).",
        confidence=1.0,
        evidence={"hits": hits},
    )


# ---------------------------------------------------------------------------
# Sanctions check (the policy wrapper around fuzzy_name_match)
# ---------------------------------------------------------------------------

def sanctions_check(name: str) -> ToolResult:
    """Apply the bank's sanctions policy to a name.

    Returns explicit ESCALATE / REVIEW / CLEAR + the matched list entries.
    The threshold is 85 (per the bank's policy doc) — encoded here so the
    policy is a constant, not a magic number.
    """
    POLICY_ESCALATE_THRESHOLD = 85.0
    POLICY_REVIEW_THRESHOLD = 70.0

    fm = fuzzy_name_match(name, list_kind="sanctions")
    hits = fm.evidence.get("hits", [])
    top = hits[0] if hits else None

    if top and top["score"] >= POLICY_ESCALATE_THRESHOLD:
        decision = "ESCALATE"
    elif top and top["score"] >= POLICY_REVIEW_THRESHOLD:
        decision = "REVIEW"
    else:
        decision = "CLEAR"

    summary = f"{decision}: '{name}'"
    if top:
        summary += f" — best match '{top['name']}' ({top['score']}%)"
    return ToolResult(
        tool="sanctions_check",
        summary=summary,
        confidence=1.0,
        evidence={"decision": decision, "hits": hits, "thresholds": {
            "escalate": POLICY_ESCALATE_THRESHOLD,
            "review": POLICY_REVIEW_THRESHOLD,
        }},
    )


# ---------------------------------------------------------------------------
# Adverse media check
# ---------------------------------------------------------------------------

def adverse_media_check(entity_id: str) -> ToolResult:
    """Look up known adverse-media items mentioning a person or entity.

    In production this would call an external API (LexisNexis, World-Check,
    Refinitiv). For the tutorial it queries the local synthetic store.
    """
    items = load.adverse_media_for(entity_id)
    if not items:
        return ToolResult(
            tool="adverse_media_check",
            summary=f"No adverse media for {entity_id}.",
            confidence=0.9,  # not 1.0 — absence of evidence isn't evidence of absence
            evidence={"items": []},
            notes="Local store only; production would consult external feeds.",
        )

    summaries = [
        {
            "headline": i.headline,
            "source": i.source_outlet,
            "date": i.published_date.isoformat(),
            "topics": i.topics,
            "snippet": i.snippet[:200],
        }
        for i in items
    ]
    return ToolResult(
        tool="adverse_media_check",
        summary=f"{len(items)} adverse media item(s) found for {entity_id}.",
        confidence=1.0,
        evidence={"items": summaries},
    )


# ---------------------------------------------------------------------------
# KG lookups (thin wrappers so the agent has clean tool boundaries)
# ---------------------------------------------------------------------------

def get_entity_details(entity_id: str) -> ToolResult:
    """Fetch one entity's full record. Works on Persons OR LegalEntities."""
    try:
        if entity_id.startswith("p_"):
            p = load.person(entity_id)
            return ToolResult(
                tool="get_entity_details",
                summary=f"{p.full_name} (Person, {p.residence_country}, PEP={p.is_pep})",
                confidence=1.0,
                evidence={
                    "id": p.id,
                    "kind": "Person",
                    "full_name": p.full_name,
                    "aliases": p.aliases,
                    "nationalities": p.nationalities,
                    "residence_country": p.residence_country,
                    "is_pep": p.is_pep,
                    "pep_reason": p.pep_reason,
                    "notes": p.notes,
                },
            )
        elif entity_id.startswith("e_"):
            e = load.entity(entity_id)
            return ToolResult(
                tool="get_entity_details",
                summary=f"{e.legal_name} ({e.entity_type.value}, {e.jurisdiction})",
                confidence=1.0,
                evidence={
                    "id": e.id,
                    "kind": "LegalEntity",
                    "legal_name": e.legal_name,
                    "aliases": e.aliases,
                    "entity_type": e.entity_type.value,
                    "jurisdiction": e.jurisdiction,
                    "notes": e.notes,
                },
            )
        else:
            return ToolResult(
                tool="get_entity_details",
                summary=f"Unknown id prefix for '{entity_id}'.",
                confidence=1.0,
                evidence={},
                notes="Expected p_* (Person) or e_* (LegalEntity).",
            )
    except StopIteration:
        return ToolResult(
            tool="get_entity_details",
            summary=f"No entity with id '{entity_id}'.",
            confidence=1.0,
            evidence={},
        )


def controls_chain(entity_id: str, max_depth: int = 5) -> ToolResult:
    """Walk *up* the control chain from an entity to its terminating UBOs.

    Returns the full set of (controller, control_type, percent) paths.
    Uses the in-memory bundle — no Neo4j dependency — so this tool works
    even if the user hasn't installed Neo4j yet.
    """
    bundle = load.load()
    # Build a reverse index: child -> list of (parent, control_type, pct)
    parents: dict[str, list[tuple[str, str, float | None]]] = {}
    for c in bundle.controls:
        parents.setdefault(c.controlled_id, []).append(
            (c.controller_id, c.control_type.value, c.ownership_pct)
        )

    paths: list[list[tuple[str, str, float | None]]] = []

    def walk(node: str, current: list[tuple[str, str, float | None]], depth: int):
        if depth > max_depth:
            return
        next_steps = parents.get(node, [])
        if not next_steps:
            if current:
                paths.append(list(current))
            return
        for parent, ctype, pct in next_steps:
            current.append((parent, ctype, pct))
            walk(parent, current, depth + 1)
            current.pop()

    walk(entity_id, [], 0)

    if not paths:
        return ToolResult(
            tool="controls_chain",
            summary=f"No upstream controllers found for {entity_id}.",
            confidence=1.0,
            evidence={"paths": []},
        )

    paths_text: list[dict] = []
    for path in paths:
        readable = []
        for parent, ctype, pct in path:
            pct_str = f" ({pct:.0f}%)" if pct is not None else ""
            readable.append(f"{parent} --{ctype}{pct_str}-->")
        paths_text.append({"path": " ".join(readable) + f" {entity_id}", "depth": len(path)})

    return ToolResult(
        tool="controls_chain",
        summary=f"{len(paths)} upstream path(s) for {entity_id}, max depth {max(p['depth'] for p in paths_text)}.",
        confidence=1.0,
        evidence={"paths": paths_text},
    )


def controlled_by(person_id: str, max_depth: int = 5) -> ToolResult:
    """The opposite direction: what entities does this person control directly or indirectly?"""
    bundle = load.load()
    children: dict[str, list[tuple[str, str, float | None]]] = {}
    for c in bundle.controls:
        children.setdefault(c.controller_id, []).append(
            (c.controlled_id, c.control_type.value, c.ownership_pct)
        )

    reached: set[str] = set()
    edges: list[dict] = []

    def walk(node: str, depth: int):
        if depth > max_depth:
            return
        for child, ctype, pct in children.get(node, []):
            edges.append({"from": node, "to": child, "type": ctype, "pct": pct, "depth": depth})
            if child not in reached:
                reached.add(child)
                walk(child, depth + 1)

    walk(person_id, 1)

    return ToolResult(
        tool="controlled_by",
        summary=f"{person_id} controls {len(reached)} entities (direct + indirect).",
        confidence=1.0,
        evidence={"reached": sorted(reached), "edges": edges},
    )


# ---------------------------------------------------------------------------
# Vector / document search (re-exposed as a tool)
# ---------------------------------------------------------------------------

_VECTOR_INDEX: Any = None
_BM25_INDEX: Any = None


def _ensure_doc_indices():
    global _VECTOR_INDEX, _BM25_INDEX
    if _VECTOR_INDEX is None:
        from kg_tutorial.retrieval import chunk_documents, VectorIndex, BM25Index
        bundle = load.load()
        chunks = chunk_documents(bundle.documents, strategy="paragraph", max_chars=800)
        _VECTOR_INDEX = VectorIndex(name="lotus_paragraph")
        if _VECTOR_INDEX.count() == 0:
            _VECTOR_INDEX.add(chunks)
        _BM25_INDEX = BM25Index(chunks)
    return _VECTOR_INDEX, _BM25_INDEX


def document_search(query: str, k: int = 5) -> ToolResult:
    """Search the unstructured documents (Gen 1 stack as a tool)."""
    from kg_tutorial.retrieval import rrf_combine

    vec, bm25 = _ensure_doc_indices()
    hyb = rrf_combine([vec.search(query, k=k * 2), bm25.search(query, k=k * 2)], top_k=k)
    hits = [
        {"doc_title": h.chunk.doc_title, "doc_id": h.chunk.doc_id, "text": h.chunk.text}
        for h in hyb
    ]
    summary = f"{len(hits)} chunks returned for '{query[:60]}'."
    return ToolResult(
        tool="document_search",
        summary=summary,
        confidence=0.8,  # similarity is noisy; not as crisp as KG
        evidence={"hits": hits},
    )


# ---------------------------------------------------------------------------
# Registry of tools by name (used by Hour 8/11 agents)
# ---------------------------------------------------------------------------

REGISTRY: dict[str, dict] = {
    "fuzzy_name_match": {
        "fn": fuzzy_name_match,
        "description": "Score a name string against a list (sanctions or internal_entities). Use when a name might match an entry despite spelling differences.",
        "args_hint": "{'query_name': str, 'list_kind': 'sanctions' | 'internal_entities'}",
    },
    "sanctions_check": {
        "fn": sanctions_check,
        "description": "Apply the bank's policy (escalate at 85%, review at 70%) to determine if a name appears on a sanctions list.",
        "args_hint": "{'name': str}",
    },
    "adverse_media_check": {
        "fn": adverse_media_check,
        "description": "Look up adverse media items mentioning a known entity id.",
        "args_hint": "{'entity_id': str}",
    },
    "get_entity_details": {
        "fn": get_entity_details,
        "description": "Fetch the full record of one Person or LegalEntity by id.",
        "args_hint": "{'entity_id': str}",
    },
    "controls_chain": {
        "fn": controls_chain,
        "description": "Walk up the control chain from an entity to find all UBOs and intermediate controllers.",
        "args_hint": "{'entity_id': str, 'max_depth': int}",
    },
    "controlled_by": {
        "fn": controlled_by,
        "description": "List all entities a person controls directly or indirectly.",
        "args_hint": "{'person_id': str, 'max_depth': int}",
    },
    "document_search": {
        "fn": document_search,
        "description": "Search unstructured documents (policies, memos, forms). Use for similarity-shaped questions.",
        "args_hint": "{'query': str, 'k': int}",
    },
}


def describe_tools() -> str:
    """Render a tool catalogue for inclusion in an LLM prompt."""
    lines: list[str] = ["AVAILABLE TOOLS:"]
    for name, meta in REGISTRY.items():
        lines.append(f"  - {name}({meta['args_hint']})")
        lines.append(f"      {meta['description']}")
    return "\n".join(lines)


def call(name: str, **kwargs) -> ToolResult:
    """Dispatch a named tool call. Raises if the tool is unknown."""
    if name not in REGISTRY:
        raise KeyError(f"Unknown tool: {name}. Available: {list(REGISTRY)}")
    return REGISTRY[name]["fn"](**kwargs)
