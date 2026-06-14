"""Retrieval primitives for Gen 1 (vector + BM25 + hybrid + LLM rerank).

This module is deliberately small. Every function is meant to be readable
end-to-end by a senior practitioner reviewing the tutorial — no surprising
abstractions, no hidden state beyond the ChromaDB client.

What's here:
- chunk_documents()    — three chunking strategies
- VectorIndex          — ChromaDB-backed dense retriever
- BM25Index            — rank-bm25 lexical baseline
- rrf_combine()        — Reciprocal Rank Fusion
- rerank_with_claude() — LLM-as-judge reranking

Used in Hours 2, 3, 7, 11.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi

from kg_tutorial import config, embed, llm
from kg_tutorial.data.schema import KYCDocument


# ---------------------------------------------------------------------------
# Chunk representation
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A piece of text plus the provenance the control manager will need."""

    chunk_id: str            # e.g. "d_cdd_gamma_ops:003"
    doc_id: str              # e.g. "d_cdd_gamma_ops"
    doc_title: str
    text: str
    metadata: dict = field(default_factory=dict)

    def short(self, n: int = 80) -> str:
        t = self.text.replace("\n", " ").strip()
        return (t[:n] + "…") if len(t) > n else t


@dataclass
class Hit:
    """A retrieved chunk with a score and a rank.

    `score` semantics depends on the retriever — vector scores are cosine
    similarity in [0, 1]; BM25 scores are unbounded positive; RRF scores
    are fractions. Always pair Hit with the retriever it came from.
    """

    chunk: Chunk
    score: float
    rank: int  # 1-indexed position in the retriever's result list


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

ChunkStrategy = Literal["fixed", "paragraph", "sentence_window"]


def chunk_documents(
    documents: Iterable[KYCDocument],
    *,
    strategy: ChunkStrategy = "paragraph",
    max_chars: int = 800,
    overlap: int = 100,
    window: int = 3,
) -> list[Chunk]:
    """Split documents into Chunks.

    Strategies:
      - "fixed": character-window with overlap. Cheapest. Splits across
        sentences and ignores structure. Surprisingly competitive baseline.
      - "paragraph": split on blank lines, then merge very short paragraphs
        with their neighbours. Respects document structure. Default.
      - "sentence_window": each chunk is a sliding window of N consecutive
        sentences. Good when the question is about a *passage* not a
        paragraph. More chunks, more memory.
    """
    out: list[Chunk] = []
    for doc in documents:
        if strategy == "fixed":
            parts = _chunk_fixed(doc.body, max_chars, overlap)
        elif strategy == "paragraph":
            parts = _chunk_paragraphs(doc.body, max_chars)
        elif strategy == "sentence_window":
            parts = _chunk_sentence_window(doc.body, window)
        else:
            raise ValueError(f"Unknown chunking strategy: {strategy}")

        for i, text in enumerate(parts):
            out.append(
                Chunk(
                    chunk_id=f"{doc.id}:{i:03d}",
                    doc_id=doc.id,
                    doc_title=doc.title,
                    text=text,
                    metadata={
                        "doc_type": doc.doc_type,
                        "created_date": doc.created_date.isoformat(),
                    },
                )
            )
    return out


def _chunk_fixed(text: str, max_chars: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    step = max_chars - overlap
    return [text[i : i + max_chars] for i in range(0, len(text), step) if text[i : i + max_chars].strip()]


def _chunk_paragraphs(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    # Merge short paragraphs (< 80 chars) into their neighbours
    merged: list[str] = []
    for p in paragraphs:
        if merged and len(merged[-1]) < 80:
            merged[-1] = merged[-1] + "\n\n" + p
        elif merged and len(p) < 80:
            merged[-1] = merged[-1] + "\n\n" + p
        else:
            merged.append(p)
    # Split any paragraph that is still too big
    final: list[str] = []
    for p in merged:
        if len(p) <= max_chars:
            final.append(p)
        else:
            final.extend(_chunk_fixed(p, max_chars, overlap=100))
    return final


def _chunk_sentence_window(text: str, window: int) -> list[str]:
    # crude but effective sentence splitter
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= window:
        return [" ".join(sentences)]
    return [" ".join(sentences[i : i + window]) for i in range(len(sentences) - window + 1)]


# ---------------------------------------------------------------------------
# Vector index
# ---------------------------------------------------------------------------

class VectorIndex:
    """ChromaDB-backed dense retriever using local BGE embeddings.

    Persists to `config.CHROMA_DIR`. Calling `add()` is idempotent over
    `chunk_id` — re-adding the same chunk overwrites silently.
    """

    def __init__(self, name: str = "lotus_docs"):
        self.client = chromadb.PersistentClient(
            path=str(config.CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        # We embed ourselves so the user sees what's happening. ChromaDB's
        # default embedding function would hide that.
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        vectors = embed.embed([c.text for c in chunks])
        self.collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors.tolist(),
            documents=[c.text for c in chunks],
            metadatas=[
                {"doc_id": c.doc_id, "doc_title": c.doc_title, **c.metadata}
                for c in chunks
            ],
        )

    def search(self, query: str, k: int = 5) -> list[Hit]:
        qvec = embed.embed(query)
        res = self.collection.query(
            query_embeddings=[qvec.tolist()],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[Hit] = []
        for i, (cid, doc, meta, dist) in enumerate(zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
        )):
            # Chroma returns distance; for cosine space, similarity = 1 - distance
            similarity = 1.0 - float(dist)
            chunk = Chunk(
                chunk_id=cid,
                doc_id=meta["doc_id"],
                doc_title=meta["doc_title"],
                text=doc,
                metadata={k: v for k, v in meta.items() if k not in {"doc_id", "doc_title"}},
            )
            hits.append(Hit(chunk=chunk, score=similarity, rank=i + 1))
        return hits

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        """Drop the collection and start over. Useful when re-running labs."""
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"},
        )


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------

class BM25Index:
    """In-memory BM25 over the same chunks the vector index holds.

    BM25 is the classic lexical retriever — it scores on exact word overlap
    with IDF weighting. Despite being twenty years old, BM25 routinely
    outperforms dense retrieval on rare-token queries (proper nouns, IDs,
    codes) — exactly the queries control managers ask.
    """

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        tokenized = [self._tokenize(c.text) for c in chunks]
        self.bm25 = BM25Okapi(tokenized)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        # Lowercase, drop punctuation, keep alphanumerics. Crude on purpose.
        return re.findall(r"[a-z0-9]+", text.lower())

    def search(self, query: str, k: int = 5) -> list[Hit]:
        scores = self.bm25.get_scores(self._tokenize(query))
        # Pair (score, chunk) and take top-k
        ranked = sorted(zip(scores, self.chunks), key=lambda x: -x[0])[:k]
        return [Hit(chunk=c, score=float(s), rank=i + 1) for i, (s, c) in enumerate(ranked)]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def rrf_combine(rank_lists: list[list[Hit]], *, k: int = 60, top_k: int | None = None) -> list[Hit]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion.

    Formula: score(d) = sum over retrievers r of  1 / (k + rank_r(d))
    where k is a smoothing constant (default 60, the value Cormack et al.
    recommend). Higher k means later ranks contribute less.

    RRF works precisely because it ignores raw scores (vector cosines and
    BM25 magnitudes aren't comparable) and just considers RANK. That makes
    it robust to retriever choice.
    """
    score: dict[str, float] = {}
    chunk_by_id: dict[str, Chunk] = {}
    for hits in rank_lists:
        for hit in hits:
            cid = hit.chunk.chunk_id
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + hit.rank)
            chunk_by_id[cid] = hit.chunk
    ranked = sorted(score.items(), key=lambda x: -x[1])
    if top_k is not None:
        ranked = ranked[:top_k]
    return [Hit(chunk=chunk_by_id[cid], score=s, rank=i + 1) for i, (cid, s) in enumerate(ranked)]


# ---------------------------------------------------------------------------
# LLM-as-judge reranking
# ---------------------------------------------------------------------------

def rerank_with_claude(query: str, hits: list[Hit], *, top_n: int = 3) -> list[Hit]:
    """Ask Claude to rerank the top hits by relevance to the query.

    The point of LLM reranking is that the LLM understands the *intent* of
    the query, not just its surface form. A query like "what is our policy
    on nephews of MPs?" should rank the PEP policy chunk above any chunk
    that merely contains the word "nephew." Vector + BM25 cannot tell those
    apart; an LLM can.

    Costs one Claude call per rerank (cheap on Sonnet). Returns the top_n
    hits as the LLM scored them.
    """
    if not hits:
        return []

    numbered = "\n\n".join(
        f"[{i + 1}] (from: {h.chunk.doc_title})\n{h.chunk.text}"
        for i, h in enumerate(hits)
    )
    prompt = f"""You are reranking retrieved passages by relevance to the user's question.

Question: {query}

Passages:
{numbered}

For each passage, output a relevance score from 0 (irrelevant) to 10 (directly answers).
Reply as JSON: a list of objects with `passage_index` (1-based) and `score`.
Return scores for all passages.
"""
    judged = llm.ask_json(prompt, max_tokens=600)
    # Build score map
    score_map: dict[int, float] = {}
    for item in judged:
        try:
            score_map[int(item["passage_index"])] = float(item["score"])
        except (KeyError, ValueError, TypeError):
            continue
    # Sort hits by LLM score (defaulting unscored to 0)
    rescored = sorted(
        enumerate(hits, start=1),
        key=lambda ix_hit: -score_map.get(ix_hit[0], 0.0),
    )
    return [
        Hit(chunk=h.chunk, score=score_map.get(i, 0.0), rank=j + 1)
        for j, (i, h) in enumerate(rescored[:top_n])
    ]
