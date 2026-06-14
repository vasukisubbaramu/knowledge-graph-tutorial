"""Build notebooks/hour03_gen1_limits.ipynb — diagnostic hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 3 — Where Gen 1 breaks

> *60 minutes dense, 2–3 hours to absorb. We take the Gen 1 stack from Hour 2 and run three diagnostic queries against it. Each query corresponds to a structural limitation. The point is not to "prove Gen 1 is bad" — Gen 1 is excellent at what it does. The point is to make precise the gap that Gen 2 fills.*

**Reading companion:** [`docs/hour03.md`](../docs/hour03.md).

By the end of this hour, you will be able to draw — on a whiteboard, in front of a colleague — a labelled diagram of what Vector RAG can and cannot do, and *why* in terms of the architecture, not in terms of "the model didn't know."
"""),
    ("code", """\
from kg_tutorial import config, llm, embed, display
from kg_tutorial.data import load
from kg_tutorial.retrieval import (
    chunk_documents,
    VectorIndex,
    BM25Index,
    rrf_combine,
    rerank_with_claude,
)

config.verify()
bundle = load.load()

# Rebuild the same retrievers as Hour 2 (re-runnable in isolation)
para_chunks = chunk_documents(bundle.documents, strategy="paragraph", max_chars=800)
vec = VectorIndex(name="lotus_paragraph")
if vec.count() == 0:
    vec.add(para_chunks)
bm25 = BM25Index(para_chunks)

def gen1_answer(q: str, k: int = 5, *, system: str = "") -> str:
    \"\"\"The hour-2 stack as a single function — retrieve, fuse, rerank, answer.\"\"\"
    v = vec.search(q, k=k * 2)
    b = bm25.search(q, k=k * 2)
    hyb = rrf_combine([v, b], top_k=k * 2)
    top = rerank_with_claude(q, hyb, top_n=k)
    ctx = "\\n\\n---\\n\\n".join(f"From: {h.chunk.doc_title}\\n\\n{h.chunk.text}" for h in top)
    prompt = (
        (system + "\\n\\n" if system else "")
        + f"Context:\\n{ctx}\\n\\nQuestion: {q}\\n\\n"
        + "Answer concisely. Cite the document each claim comes from."
    )
    return llm.ask(prompt, max_tokens=500), top

print(f"Ready. {vec.count()} chunks in vector index, {len(para_chunks)} in BM25.")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. Diagnostic 1 — multi-hop relational query

**Query:** *"Trace the full ownership chain of Gamma Operations GmbH from the legal entity to the natural-person UBO. List each entity in the chain and its jurisdiction."*

This is the canonical multi-hop question. The answer requires **traversing three ownership edges**, each documented in a different jurisdiction's registry (and partially in the CDD form). No single chunk contains the full chain.
"""),
    ("code", """\
q_chain = (
    "Trace the full ownership chain of Gamma Operations GmbH from the legal entity "
    "to the natural-person UBO. List each entity in the chain and its jurisdiction."
)
answer, top = gen1_answer(q_chain, k=5)
print("TOP-5 CHUNKS RETRIEVED:")
for h in top:
    print(f"  rank {h.rank}  doc={h.chunk.doc_title[:60]}")
print()
print("MODEL ANSWER:")
display.md(answer)
"""),
    ("md", """\
**Stop and grade.** A well-formed answer should list, in order:

1. Gamma Operations GmbH (LI)
2. AlphaBeta Trading SA (PA) — 75% parent
3. ACME Holdings Ltd (KY) — 100% parent
4. John Q. Public — 50% UBO

Did the model produce all four? In the right order? With the percentages?

**Why this may have worked.** All four entities and their relationships are mentioned in *one* document — the CDD form. If your chunking kept the relevant section intact and the retriever returned it, the answer fell out. Lucky.

**Why this is structurally fragile.** Imagine the CDD form did *not* contain the full chain summary, and instead each layer was documented separately — the Cayman registry extract for ACME, the Panama registry extract for AlphaBeta, the Liechtenstein extract for Gamma. **The graph would be three edges in three documents.** A vector retriever asked for "the ownership chain of Gamma" would surface the Liechtenstein extract (closest match). The Panama and Cayman extracts would not be in the top-k. The model would answer *one hop*.

In production, this scenario is the norm, not the exception. Run the modified version:
"""),
    ("code", """\
q_chain_strict = (
    "Who owns ACME Holdings Ltd? Provide the natural-person beneficial owner and the percentage."
)
answer, top = gen1_answer(q_chain_strict, k=5)
print("TOP-5 CHUNKS:")
for h in top:
    print(f"  rank {h.rank}  doc={h.chunk.doc_title[:60]}")
print()
print("MODEL ANSWER:")
display.md(answer)
"""),
    ("md", """\
Notice how *this* version of the question — asking *backwards* up the chain — exposes the limit faster. The model has to find chunks that say "X owns ACME" and the only direct one is in the CDD form's Section 4. If that chunk doesn't make the top-k, the model has nothing to anchor on.

The deeper point: **vector retrieval recalls chunks by similarity, not by relation.** "What owns X" and "what does X own" embed almost identically, and the model has no way to know which direction the user wants. Hour 6 (Cypher) makes direction explicit at the query level.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Diagnostic 2 — aggregation across documents

**Query:** *"List every legal entity that John Q. Public controls directly or indirectly. Specify whether each is through ownership or directorship."*

This question asks for a **set**. Retrieval returns chunks. The model has to derive the set by composing the chunks. If a chunk is missed, an entity is missed silently — the model does not know what it does not know.
"""),
    ("code", """\
q_set = (
    "List every legal entity that John Q. Public controls directly or indirectly. "
    "For each one, specify whether the control is by ownership or by directorship."
)
answer, top = gen1_answer(q_set, k=6)
print("TOP-6 CHUNKS:")
for h in top:
    print(f"  rank {h.rank}  doc={h.chunk.doc_title[:60]}")
print()
print("MODEL ANSWER:")
display.md(answer)
"""),
    ("md", """\
**Ground truth from the dataset** (we built it ourselves, so we know):

| Entity | Relation | Source document |
|--------|----------|-----------------|
| ACME Holdings Ltd (KY) | 50% UBO | CDD form §4 |
| AlphaBeta Trading SA (PA) | indirect (via ACME) | CDD form §4 (chain) |
| Gamma Operations GmbH (LI) | indirect (via AlphaBeta) | CDD form §4 (chain) |
| **Atlas Wirecorp (AE)** | **direct directorship** | **mentioned only in policy/SoF questionnaire context** |

Did the model find Atlas Wirecorp? This is the **cross-link** of the Lotus case. John's directorship of Atlas is critical — it converts the incoming deposit from "anonymous wire from a UAE company" to "self-deal from a sanctioned entity controlled by the UBO." The model can only catch this if it sees both (a) a chunk identifying John as a director of Atlas, and (b) the surrounding context establishing that Atlas is the sanctioned originator.

**Vector similarity will not retrieve the John-directs-Atlas chunk in response to "what does John control?"** because that fact, in our dataset, appears in passing in the source-of-funds questionnaire — surrounded by talk about deposits, not control. The retriever scores it low for "control" queries.

This is *not* fixable by bigger k. Try it:
"""),
    ("code", """\
# Try wider retrieval — does the cross-link surface with k=10?
v_wide = vec.search(q_set, k=10)
b_wide = bm25.search(q_set, k=10)
hyb_wide = rrf_combine([v_wide, b_wide], top_k=10)

print("WIDER RETRIEVAL (top-10):")
for h in hyb_wide:
    contains_atlas = "atlas" in h.chunk.text.lower()
    contains_director = "director" in h.chunk.text.lower()
    flag = "  <-- has both 'atlas' and 'director'" if contains_atlas and contains_director else ""
    print(f"  rank {h.rank}  doc={h.chunk.doc_title[:45]}{flag}")
"""),
    ("md", """\
Even at k=10 — twice what we used — the cross-link chunk may or may not be there, and *if* it is, the model still has to *compose* "John directs Atlas" with "deposit is from Atlas" with "OFAC has near-match for Atlas." Three facts, three documents, three retrievals.

**This is precisely the closed-vs-disconnected-vs-unverified failure taxonomy from Hour 1.** Gen 1 can address *closed-world ignorance*. It cannot address *disconnected facts* — by construction.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Diagnostic 3 — inference under name mismatch

**Query:** *"The applicant's first inbound deposit is from a counterparty named 'ATLAS WIRECORP'. Has this counterparty been sanctioned? Cite the specific list entry."*

The deposit narrative says `ATLAS WIRECORP`. OFAC says `ATLAS WIRE CORPORATION`. Both refer to the same entity (intentionally — we built the case to illustrate the alias problem).
"""),
    ("code", """\
q_sanctions = (
    "The applicant's first inbound deposit is from a counterparty named 'ATLAS WIRECORP'. "
    "Has this counterparty been sanctioned? Cite the specific list entry if so."
)
answer, top = gen1_answer(q_sanctions, k=6)
print("TOP-6 CHUNKS:")
for h in top:
    print(f"  rank {h.rank}  doc={h.chunk.doc_title[:60]}")
print()
print("MODEL ANSWER:")
display.md(answer)
"""),
    ("md", """\
The OFAC entry doesn't live in a document; it lives in the sanctions list (`bundle.sanctions`). Our Gen 1 pipeline only indexed documents — by design. So the model has nothing to retrieve from. Let's fix that by also indexing the sanctions list as text and re-running.
"""),
    ("code", """\
# Make the sanctions list visible to Gen 1 by adding it as chunks
from kg_tutorial.retrieval import Chunk

sanc_chunks = [
    Chunk(
        chunk_id=f"sanc:{s.id}",
        doc_id=f"sanc:{s.id}",
        doc_title=f"Sanctions entry — {s.name}",
        text=(
            f"List: {s.list_source.value}. Listed: {s.listed_date}. "
            f"Country: {s.country}. Primary name: {s.name}. "
            f"Aliases: {', '.join(s.aliases) if s.aliases else 'none'}. "
            f"Reason: {s.reason}"
        ),
        metadata={"kind": "sanctions"},
    )
    for s in bundle.sanctions
]

# Add to a new collection so we can compare fairly
vec_with_sanc = VectorIndex(name="lotus_with_sanctions")
vec_with_sanc.reset()
vec_with_sanc.add(para_chunks + sanc_chunks)
print(f"Combined index: {vec_with_sanc.count()} chunks (docs + sanctions).")

# Re-run sanctions query on combined index
hits = vec_with_sanc.search(q_sanctions, k=6)
print()
print("RETRIEVED (top-6):")
for h in hits:
    print(f"  rank {h.rank}  sim={h.score:.3f}  doc={h.chunk.doc_title[:60]}")
"""),
    ("md", """\
**Look at the top hit.** Did "ATLAS WIRECORP" in the query retrieve "ATLAS WIRE CORPORATION" from the sanctions list?

Possibly yes, possibly no — and the *reason* matters more than the result.

- Embeddings of short strings (just a company name) are noisy. BGE-small was trained on long-form text, not on entity names.
- "ATLAS WIRECORP" and "ATLAS WIRE CORPORATION" embed close because they share tokens, but a dozen of the 24 *noise* sanctions entries might also score close enough to displace the real match.
- BM25 will score them close too, because they share the tokens "atlas" and "wire."

But none of this is what a control manager wants. The control manager wants a **fuzzy name-match score with a deterministic threshold**: "if score ≥ 85, escalate." That's a string-matching tool, not a vector retriever. Try the right tool:
"""),
    ("code", """\
# Show what a proper fuzzy matcher does, for contrast
from difflib import SequenceMatcher

def fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a.upper().strip(), b.upper().strip()).ratio() * 100

target = "ATLAS WIRECORP"
print(f"Fuzzy match scores for '{target}':")
print()
for s in bundle.sanctions:
    names = [s.name] + s.aliases
    best = max(fuzzy_score(target, n) for n in names)
    if best >= 70:
        flag = "  <-- ESCALATE" if best >= 85 else "  <-- review"
        print(f"  {best:5.1f}  vs {s.name}{flag}")
"""),
    ("md", """\
A simple SequenceMatcher (Python's standard-library fuzzy matcher) scores `ATLAS WIRECORP` vs `ATLAS WIRE CORPORATION` somewhere in the high 80s — above the bank's 85% escalation threshold. **That's a clean answer in a single line of code.** Vector retrieval over the same comparison is noisy and gives no defensible threshold.

The lesson: **some retrieval problems are not retrieval problems**. The sanctions-match problem is a string-matching problem with a calibrated threshold. Gen 1 architectures get this wrong by reflex — "we'll just embed the sanctions list" — because their hammer is similarity. Gen 3 gets it right by giving the agent a *tool* called `fuzzy_name_match` and the agent picks it for the right sub-question. Hour 11 builds this.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. A diagnostic summary

|  | Diagnostic 1: multi-hop chain | Diagnostic 2: cross-doc aggregation | Diagnostic 3: alias sanctions match |
|---|---|---|---|
| **Gen 1 success** | Partial — works only when one chunk contains the full chain. | Misses cross-link by construction. | Wrong tool for the job — embed-similarity isn't fuzzy string match. |
| **Why** | Similarity reasons in pairs, not paths. | Retrieval returns chunks, not sets. | Sanctions matching has a calibrated, deterministic answer; similarity doesn't. |
| **What Gen 2 buys you** | Cypher walks the chain in one query. | Set operations natural over the KG. | Still needs a fuzzy operator on edges — Hour 7. |
| **What Gen 3 buys you** | Decomposes "trace the chain" into atomic queries, executes, verifies. | Routes "aggregation" sub-question to graph; routes "fuzzy match" sub-question to a tool. | Agent uses `fuzzy_name_match` tool with a calibrated threshold. |

This table is **the** mental model to leave Hour 3 with. The next nine hours fill in each cell.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. What Gen 1 still owns

Lest this hour read as a hatchet job, the same table from the other direction. **Gen 1 is genuinely better than Gen 2 or Gen 3 at:**

- **Policy lookup** ("what does our policy on PEPs say?") — similarity-shaped, single chunk.
- **Definition search** ("what does FATF Rec 12 require?") — same.
- **Boilerplate** ("show me the template for SoF questionnaire") — same.
- **Discoverability** ("where in the docs is there mention of X?") — vector + BM25 will find it; Cypher requires you to know the schema.
- **Cost and latency at scale** — Gen 1 answers in <1s for <$0.001; Gen 3 answers in 10–60s for $0.10+.

Production architectures keep Gen 1 alive for these patterns and route the relational + verification patterns elsewhere. Hour 12 builds the router.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think before Hour 4

Three questions:

1. **In your current platform, what fraction of queries are "similarity-shaped" vs "relation-shaped" vs "verification-shaped"?** A rough estimate is fine. The answer affects how much of Hour 4-11 you'll lift directly vs adapt.
2. **The cross-link in Diagnostic 2** — John directing Atlas — is the kind of fact that, in real KYC, often surfaces by accident or not at all. What in your current data flow would surface it? What would miss it?
3. **The fuzzy-match problem in Diagnostic 3** — does your current platform have a calibrated fuzzy matcher with a documented threshold? If yes, what's the threshold and how was it calibrated? If no, that's a finding.

Hour 4 designs the knowledge graph. It's the most opinionated hour of the tutorial — there will be choices that *feel* arbitrary but matter operationally. Read [`docs/hour04.md`](../docs/hour04.md) before you start the notebook.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour03_gen1_limits.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
