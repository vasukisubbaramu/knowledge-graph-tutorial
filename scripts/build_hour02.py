"""Build notebooks/hour02_vector_rag.ipynb — Gen 1 hands-on."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    # ------------------------------------------------------------------
    ("md", """\
# Hour 2 — Gen 1: Vector RAG, hands-on

> *60 minutes dense, 2–3 hours to absorb. By the end you will have built four retrievers (fixed-chunk vector, paragraph vector, BM25 lexical, hybrid + LLM-rerank), measured them against each other on the Lotus corpus, and seen — with concrete numbers — where Gen 1 succeeds and where it strains.*

**Reading companion:** [`docs/hour02.md`](../docs/hour02.md). **Domain primer if you need it:** [`docs/kyc_ubo_primer.html`](../docs/kyc_ubo_primer.html).

The next hour (Hour 3) takes the strained cases and breaks them properly. The two hours are designed to be read together.
"""),
    # Bootstrap is auto-added; setup cell next
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
print(f"Documents loaded: {len(bundle.documents)}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. The first decision: chunking

Before any retriever runs, the documents must be split into chunks. **This is the single most consequential design decision in Gen 1**, and the one most often skipped over.

Why it matters: the chunk is the unit of retrieval. The model sees whole chunks. If the chunk is too small, it lacks context. If it is too large, retrieval becomes coarse and irrelevant. If chunks split across paragraph boundaries, they may have only a fragment of the relevant fact.

We will compare three strategies on the Lotus documents:

- **Fixed-character windows** (800 chars, 100 overlap). Cheap, robust, splits mid-sentence.
- **Paragraph-aware**. Respects document structure. Default for most production Gen 1 systems.
- **Sentence-window** (3 sentences sliding). Many more chunks, better when the answer is one passage.
"""),
    ("code", """\
fixed_chunks = chunk_documents(bundle.documents, strategy="fixed", max_chars=800, overlap=100)
para_chunks = chunk_documents(bundle.documents, strategy="paragraph", max_chars=800)
sent_chunks = chunk_documents(bundle.documents, strategy="sentence_window", window=3)

for label, chunks in [("fixed", fixed_chunks), ("paragraph", para_chunks), ("sentence_window", sent_chunks)]:
    lengths = [len(c.text) for c in chunks]
    print(f"{label:>18}: {len(chunks):>3} chunks, avg {sum(lengths)//len(lengths)} chars, max {max(lengths)} chars")
"""),
    ("md", """\
**Stop and look.** The same 7 documents yield 7 different chunks under paragraph, 12 under fixed, ~80 under sentence-window. Each strategy creates a different retrieval surface — a different *set of things the retriever can ever return*. A chunk that doesn't exist cannot be retrieved.

For the rest of this hour we use **paragraph chunking** as the default. It produces the smallest, most semantically-coherent set, and it's the production default. Hour 3 revisits this when paragraph chunking masks a connection we needed.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Embed the chunks and build a vector index

ChromaDB persists to `data/chroma_db/`. The first run downloads the BGE-small model if Hour 0 hasn't already; subsequent runs are instant.
"""),
    ("code", """\
vec = VectorIndex(name="lotus_paragraph")
vec.reset()  # start clean each time we re-run this hour
vec.add(para_chunks)
print(f"Vector index contains {vec.count()} chunks.")
print(f"Embedding dimension: {embed.dimension()}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. An easy question — Gen 1 should win

A control manager asks: *"What does our policy say about politically exposed persons who are nephews of MPs?"*

This is the **right shape of question for Gen 1**: the answer is contained in one passage of one document, retrievable by surface similarity to the question. Watch it work.
"""),
    ("code", """\
q1 = "What does our policy say about politically exposed persons who are nephews of MPs?"

hits = vec.search(q1, k=5)
for h in hits:
    print(f"  rank {h.rank}  sim={h.score:.3f}  doc={h.chunk.doc_title[:50]}")
    print(f"    └─ {h.chunk.short(140)}")
    print()
"""),
    ("md", """\
The top hit should be the relevant paragraph from the PEP policy document. Now let Claude answer using just the top-3.
"""),
    ("code", """\
top3 = vec.search(q1, k=3)
context = "\\n\\n---\\n\\n".join(f"From: {h.chunk.doc_title}\\n\\n{h.chunk.text}" for h in top3)

answer = llm.ask(
    f\"\"\"Context:
{context}

Question: {q1}

Answer in 3-4 sentences. Cite which document each claim is from.\"\"\",
    max_tokens=400,
)
display.md(answer)
"""),
    ("md", """\
Gen 1 should answer this cleanly. **The question is similarity-shaped, the answer is in one chunk, and the chunk is retrievable.** This is the floor of what RAG architectures must deliver, and Gen 1 delivers it for ~$0.001 of LLM time. Don't dismiss the floor.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. A medium question — surface similarity vs intent

Now a slightly harder one: *"Is John Q. Public a politically exposed person?"*

The word "PEP" appears in our policy. John's name appears in the CDD form. The *connection* — that he is a PEP-relative under the nephew clause — exists only when both are read together. Watch how vector search ranks the chunks.
"""),
    ("code", """\
q2 = "Is John Q. Public a politically exposed person?"

hits = vec.search(q2, k=6)
for h in hits:
    print(f"  rank {h.rank}  sim={h.score:.3f}  doc={h.chunk.doc_title[:50]}")
    print(f"    └─ {h.chunk.short(160)}")
    print()
"""),
    ("md", """\
Look at the top hits. The CDD form chunks (mentioning John) score high. The policy chunk (defining PEP-relative) may or may not be in the top-k. The relevant *combination* requires both. Now ask the model:
"""),
    ("code", """\
top5 = vec.search(q2, k=5)
context = "\\n\\n---\\n\\n".join(f"From: {h.chunk.doc_title}\\n\\n{h.chunk.text}" for h in top5)

answer = llm.ask(
    f\"\"\"Context:
{context}

Question: {q2}

Answer in 3-5 sentences. Cite the documents you use. If the answer requires combining facts from multiple documents, say so explicitly.\"\"\",
    max_tokens=400,
)
display.md(answer)
"""),
    ("md", """\
**This is the first interesting failure mode.** If the policy chunk was retrieved, the model probably composed the answer correctly. If it wasn't — because surface similarity didn't favour the policy paragraph for this query — the model produced a partial or wrong answer.

The issue isn't the LLM. It's that *similarity didn't surface the chunk the answer needed*. Hour 3 makes this systematic.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 5. BM25 — the lexical baseline you should always have

Vector retrievers reason about *meaning*. BM25 reasons about *words*. When the query contains a proper noun, an account number, an ID — anything where the *exact token* is the signal — BM25 will reliably outperform a dense retriever. Production Gen 1 systems use both.

Try the same medium question with BM25.
"""),
    ("code", """\
bm25 = BM25Index(para_chunks)
bm25_hits = bm25.search(q2, k=5)
for h in bm25_hits:
    print(f"  rank {h.rank}  bm25={h.score:.3f}  doc={h.chunk.doc_title[:50]}")
    print(f"    └─ {h.chunk.short(160)}")
    print()
"""),
    ("md", """\
Different ranking. BM25 favours chunks that contain the literal tokens "John", "Public", "politically" — vector favours chunks whose embedding is close to the query's embedding. Neither is right; they're complementary.

The right move in production is to **combine them**.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 6. Hybrid retrieval — Reciprocal Rank Fusion (RRF)

RRF takes multiple ranked lists and combines them by rank, not by raw score:

$$ \\text{score}(d) = \\sum_{r \\in \\text{retrievers}} \\frac{1}{k + \\text{rank}_r(d)} $$

with `k=60`. Documents that rank highly in multiple retrievers float to the top; documents that rank highly in only one retriever are still surfaced.

The reason this works is that raw vector cosines and BM25 scores aren't comparable — RRF ignores them and uses only rank, which is *always* comparable.
"""),
    ("code", """\
vec_hits = vec.search(q2, k=8)
bm25_hits = bm25.search(q2, k=8)
hybrid = rrf_combine([vec_hits, bm25_hits], top_k=5)

print("HYBRID (RRF) TOP-5:")
for h in hybrid:
    print(f"  rank {h.rank}  rrf={h.score:.4f}  doc={h.chunk.doc_title[:50]}")
    print(f"    └─ {h.chunk.short(160)}")
    print()
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 7. LLM-as-judge reranking

The final step that distinguishes a serious Gen 1 system from a toy one: have the LLM rerank the top-N. The LLM understands *intent*, where the retrievers only understand *surface*. The cost is one extra LLM call per query — cheap on Sonnet, worth it.
"""),
    ("code", """\
reranked = rerank_with_claude(q2, hybrid, top_n=3)
print("LLM-RERANKED TOP-3:")
for h in reranked:
    print(f"  rank {h.rank}  llm_score={h.score:.1f}  doc={h.chunk.doc_title[:50]}")
    print(f"    └─ {h.chunk.short(160)}")
    print()
"""),
    ("code", """\
context = "\\n\\n---\\n\\n".join(f"From: {h.chunk.doc_title}\\n\\n{h.chunk.text}" for h in reranked)

final_answer = llm.ask(
    f\"\"\"Context:
{context}

Question: {q2}

Answer in 3-5 sentences. Cite the documents. If the answer requires combining facts from multiple documents, state the chain of reasoning explicitly.\"\"\",
    max_tokens=400,
)
display.md(final_answer)
"""),
    ("md", """\
The hybrid + reranked answer should be cleaner and better-cited than the pure-vector answer in §4. **This is the asymptotic ceiling of Gen 1**: retrieve broadly (vector + BM25), narrow with the LLM-as-judge, answer over a clean top-3.

Anything Gen 1 can do, it does best like this.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 8. The Lotus question — Gen 1's first try

The big one. *"Should we approve the account-opening application for Gamma Operations GmbH?"*

This question is the joint composition of about ten separate facts spread across all 7 documents — UBO chain, PEP classification, sanctions alias, RM pressure, missing source-of-funds evidence, adverse media, policy mappings. Gen 1 will produce *some* answer. The question this hour is: how good is it?
"""),
    ("code", """\
q_lotus = "Should we approve the account-opening application for Gamma Operations GmbH?"

vec_hits = vec.search(q_lotus, k=10)
bm25_hits = bm25.search(q_lotus, k=10)
hybrid = rrf_combine([vec_hits, bm25_hits], top_k=8)
reranked = rerank_with_claude(q_lotus, hybrid, top_n=5)

print("FINAL TOP-5 FOR THE LOTUS QUESTION:")
for h in reranked:
    print(f"  rank {h.rank}  llm_score={h.score:.1f}  doc={h.chunk.doc_title[:50]}")
"""),
    ("code", """\
context = "\\n\\n---\\n\\n".join(f"From: {h.chunk.doc_title}\\n\\n{h.chunk.text}" for h in reranked)

lotus_answer = llm.ask(
    f\"\"\"You are a senior bank control manager.

Context:
{context}

Question: {q_lotus}

Write a one-paragraph recommendation. Cite specific document titles for each claim. End with APPROVE, DECLINE, or ESCALATE.\"\"\",
    max_tokens=600,
)
display.md(lotus_answer)
"""),
    ("md", """\
**Stop and grade the answer against your control-manager hat.**

Use this checklist (write your answers on paper before scrolling):

1. Did the answer identify the full ownership chain (KY → PA → LI)?
2. Did it identify John Q. Public as PEP-relative under the nephew clause?
3. Did it notice the cross-link — that John is *also* a director of the deposit's originator?
4. Did it spot the alias mismatch between "ATLAS WIRECORP" and "ATLAS WIRE CORPORATION"?
5. Did it cite the RM memo's pressure-to-expedite as a control concern in its own right?
6. Did it cite the source-of-funds questionnaire's lack of supporting invoices?
7. Did the citations point to specific documents — or were they vague?

Most likely: Gen 1 caught 3-4 of these. The others were either not retrieved (the chunk wasn't in the top-k) or were retrieved but not composed (the model didn't relate them).

**Gen 1's failure is not stupidity. It's structural.** The next hour proves this with three diagnostic queries.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 9. Where this breaks (preview of Hour 3)

Three things that Gen 1, as implemented in this hour, cannot do well:

1. **Multi-hop relational queries.** "Who is the UBO of Gamma?" requires traversing three ownership edges. Vector similarity doesn't traverse.
2. **Aggregation across documents.** "What entities does John control directly or indirectly?" requires a set-union over documents. Retrievers return chunks, not sets.
3. **Inference under name mismatch.** "Is the deposit's originator on a sanctions list?" requires *fuzzy* string matching between a deposit narrative and a list entry. Embedding similarity is too noisy at this scale.

Hour 3 runs these three queries and dissects the failure modes. The dissection motivates everything that comes after.
"""),
    # ------------------------------------------------------------------
    ("md", """\
---

## Stop and think

Before Hour 3, write down:

1. **In the Lotus answer above, what is the single most consequential fact the model missed?** That fact will surface a specific Gen 1 limitation in Hour 3.
2. **What would you have to add to Gen 1 to fix this — without changing the LLM?** Bigger context window? More chunks in top-k? Different chunking? Different reranker? Hour 3 demonstrates which of these moves the needle and which don't.

Next: [Hour 3 — Where Gen 1 breaks](./hour03_gen1_limits.ipynb).
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour02_vector_rag.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
