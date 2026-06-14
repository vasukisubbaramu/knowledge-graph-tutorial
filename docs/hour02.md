# Hour 2 — Gen 1: Vector RAG, hands-on

A reading companion to `notebooks/hour02_vector_rag.ipynb`.

> **One-line frame for the hour.** *Production Gen 1 is not "embed and retrieve" — it is **chunking + dense retrieval + lexical retrieval + rank fusion + LLM rerank**, and every layer matters.*

## 1. Why we go deeper than "vector RAG"

The vast majority of public RAG tutorials show the minimum-viable path: chunk the documents, embed them, query, get top-k, prompt the LLM. That works for a demo. It does not work for a control manager whose missed-match becomes a regulatory finding.

What separates a serious Gen 1 system from a toy one is not the choice of vector store or embedding model — those choices matter less than people think. It is the *quality of the retrieval stack*: how chunks are produced, how multiple retrievers' results are fused, and how the final passages are reranked by something that understands intent. The 4-layer stack in this hour — *paragraph chunking + dense vectors + BM25 + RRF + LLM rerank* — is, with minor variations, what most production Gen 1 systems converge on.

## 2. Chunking: the single most consequential decision

Chunks are the unit of retrieval. The retriever cannot return what doesn't exist as a chunk. The model receives whole chunks. Everything downstream is bounded by chunk quality.

Three strategies, in increasing order of structure-respect:

- **Fixed-character windows** are cheap, predictable, and robust. They split mid-sentence and ignore paragraph boundaries. They are surprisingly competitive — embeddings are quite tolerant of mid-sentence breaks. Use as a baseline.

- **Paragraph-aware** chunks respect the document's own structure. They produce fewer, longer, more coherent chunks. They are the production default. The risk is that a long paragraph (a CDD form's Section 4 narrative, say) becomes one chunk and the retriever cannot distinguish within it.

- **Sentence-window** chunks are sliding windows of N consecutive sentences. They produce many small chunks; retrieval is fine-grained; memory footprint is larger. Use when the answers are short passages, not paragraphs.

A serious Gen 1 system often indexes the corpus *multiple ways* and queries all indices in parallel. You can think of it as querying the same content at multiple granularities. The cost is index size; the benefit is that whatever granularity the answer lives at, it is retrievable.

## 3. Dense retrieval: what embeddings buy you

Dense (vector) retrieval embeds the query and finds the chunks whose embeddings are closest by cosine similarity. The embedding model has been trained to produce vectors such that *semantically similar* texts are close in the vector space — and crucially, "semantically similar" includes paraphrases, synonyms, and translations.

This is the power and the limit of dense retrieval. It will find a chunk about "PEPs" when the query asks about "politically exposed persons" — BM25 will not. It will fail when the query depends on a *specific token* (an account number, an entity ID, a precise jurisdiction code) — BM25 will succeed there.

Embedding models in 2026 sit roughly in three tiers for this domain:

- **Tiny** (e.g. all-MiniLM-L6-v2, 22M params). Fast, weak. Useful for prototypes.
- **Small** (BGE-small, GTE-small, ~30-130M params). What we use. Real quality.
- **Hosted** (Voyage, OpenAI text-embedding-3-large, Cohere). Best quality. Cost a third or fourth API key.

For tutorial scale BGE-small is fine. For production at a bank, get the quality bump from a hosted embedding model — the marginal cost is trivial relative to the lift in retrieval precision.

## 4. BM25: the lexical baseline you should always have

BM25 is twenty years old. It outperforms dense retrieval whenever the query contains a rare token whose *exact form* is the signal: account numbers, account types, regulatory citation codes, FATF Recommendation numbers, ISO country codes, SWIFT BIC codes. All of these are the kinds of tokens control-manager queries are full of.

The smart move is not "choose vector or BM25" — it is "run both, in parallel, on the same chunk set, and fuse." That requires a method to combine ranked lists from incommensurable scorers. Reciprocal Rank Fusion is the standard answer.

## 5. Reciprocal Rank Fusion (RRF)

RRF was introduced by Cormack et al. in 2009. The formula:

$$\text{score}(d) = \sum_{r \in \text{retrievers}} \frac{1}{k + \text{rank}_r(d)}$$

with $k = 60$. The reason it works is that it throws away *raw scores* — which are not comparable across retrievers — and uses only *rank*, which is always comparable.

It is a strong default. It tends to retrieve documents that *any* retriever liked, while penalizing documents that *only* one retriever liked. The behaviour is robust: changing the embedding model, or the BM25 implementation, rarely degrades RRF results.

There are more sophisticated fusion methods — learned-to-rank, cross-encoder reranking — but RRF is the right floor.

## 6. LLM-as-judge reranking

The final layer. Retrieval returns the top-N by similarity or lexical match. None of those signals tell you whether a chunk *actually answers* the question. The LLM does.

The pattern: send the top-N chunks (8 to 15 is typical) to a small-but-capable model with a prompt that says "score each passage by relevance to the question, 0 to 10." Sort by the model's score. Use the top-3 to actually answer the question.

The cost is one extra LLM call per query. On Sonnet, this is around $0.002 per query — small compared to the quality lift. The reranker call is also a *natural caching boundary* — same query, same retrieved set, you can skip the rerank.

The reranker is where Gen 1 becomes interesting. The reranker reads the query and the chunks together; it understands intent; it can punish a chunk that *looks* similar but doesn't actually answer the question; it can promote a chunk that is buried in the top-15.

## 7. What Gen 1 looks like, all-up

A serious Gen 1 system, after this hour's choices:

```
Documents
  ├── paragraph-chunked
  ├── (optionally) also fixed-chunked
  └── added to ChromaDB collection(s)

Query
  ├── vector_search(query, k=20)        ──┐
  ├── bm25_search(query, k=20)          ──┤
  │                                       ▼
  │                              rrf_combine([vec, bm25], top_k=15)
  │                                       │
  │                                       ▼
  │                            rerank_with_claude(query, hits=15, top_n=3)
  │                                       │
  │                                       ▼
  └─────────────────────────  prompt(top_3, query) → LLM answer
```

This is the asymptotic ceiling of Vector RAG. Anything that improves further requires either changing the model (frontier embeddings, frontier reranker) or moving beyond Gen 1's architectural assumption that *retrieval is similarity*.

The next hour, Hour 3, runs three queries that hit that assumption head-on.

## 8. What to take away from Hour 2

- Chunking is not configuration; it is design.
- Hybrid retrieval (dense + lexical) routinely outperforms either alone on real-world queries.
- RRF is the right default for fusion; don't over-engineer.
- LLM reranking is cheap and high-impact; treat it as a default layer, not a luxury.
- Gen 1 done seriously is *very good* at similarity-shaped questions and a reliable workhorse — until the question isn't similarity-shaped. Then Hour 3 starts to matter.
