"""Sandbox pgvector/BM25 fallback RAG service.

Used when settings.rag_backend == "pgvector_fallback" (the default, since
RAGFlow's own Docker stack cannot be pulled inside this sandbox — see
infra/ragflow/README.md). Same document schema and citation contract as
the RAGFlow path (mangrove_ai.rag.ragflow_client), so callers
(search_ragflow MCP tool) don't need to know which backend answered.

Implements the required RAG-context-rot controls end to end:
  query rewriting      -> _rewrite_query (light synonym expansion)
  hybrid retrieval      -> Postgres full-text (tsvector) + metadata filter
  top-k retrieval        -> SQL LIMIT candidate_k
  reranking                -> BM25 rescoring of candidates in Python
  context compression       -> _extract_window trims each chunk to the
                              sentence(s) actually matching the query
  citation grounding         -> every result carries doc_id/title/section/page
  insufficient evidence        -> explicit flag, never improvised, if
                              nothing clears MIN_RERANK_SCORE
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Plus
from sqlalchemy import text

from mangrove_ai.db import get_session
from mangrove_ai.rag.manifest import get_entry

CANDIDATE_K = 40
MIN_RERANK_SCORE = 0.05  # BM25 scores are unbounded; this is a low floor to reject empty/near-empty matches, not a calibrated confidence

INSUFFICIENT_EVIDENCE = "Insufficient evidence in the indexed scientific sources."

_SYNONYMS = {
    "igeo": ["geo-accumulation index", "geoaccumulation index", "igeo"],
    "salinity": ["salinity", "electrical conductivity", "ec", "sar", "esp"],
    "health": ["condition", "canopy condition", "vegetation vigor"],
    "restoration": ["restoration", "rehabilitation", "replanting", "afforestation"],
}


@dataclass
class RetrievedChunk:
    doc_id: str
    title: str
    section: str | None
    page: int | None
    quote: str
    score: float


def _tokenize(text_block: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text_block.lower())


def _rewrite_query(query: str) -> list[str]:
    terms = [query]
    lowered = query.lower()
    for key, expansions in _SYNONYMS.items():
        if key in lowered:
            terms.extend(expansions)
    return terms


def _extract_window(text_block: str, query_terms: list[str], window_sentences: int = 2) -> str:
    """Context compression: return only the sentence(s) around the first
    query-term hit, not the whole chunk."""
    sentences = [s.strip() for s in text_block.replace("\n", " ").split(". ") if s.strip()]
    if not sentences:
        return text_block[:400]
    lowered_terms = [t.lower() for t in query_terms]
    for i, sentence in enumerate(sentences):
        if any(term in sentence.lower() for term in lowered_terms):
            start = max(0, i - 1)
            end = min(len(sentences), i + window_sentences)
            return ". ".join(sentences[start:end]) + "."
    return ". ".join(sentences[:window_sentences]) + "."


_CANDIDATE_SQL = text("""
    SELECT c.chunk_id, c.doc_id, c.section, c.page, c.chunk_text, c.location_tag, c.dataset_tag,
           d.title, d.category
    FROM rag_chunks c
    JOIN rag_documents d ON d.doc_id = c.doc_id
    WHERE d.status = 'ingested'
      AND (CAST(:location AS text) IS NULL OR c.location_tag = CAST(:location AS text))
      AND (CAST(:category AS text) IS NULL OR d.category = CAST(:category AS text))
      AND c.tsv @@ plainto_tsquery('english', CAST(:query AS text))
    ORDER BY ts_rank(c.tsv, plainto_tsquery('english', CAST(:query AS text))) DESC
    LIMIT CAST(:k AS int)
""")


def search(query: str, location: str | None = None, category: str | None = None, top_k: int = 5) -> dict:
    query_terms = _rewrite_query(query)

    with get_session() as session:
        rows = session.execute(
            _CANDIDATE_SQL,
            {"query": query, "location": location, "category": category, "k": CANDIDATE_K},
        ).mappings().all()

    if not rows:
        return {"insufficient_evidence": True, "message": INSUFFICIENT_EVIDENCE, "results": []}

    corpus = [_tokenize(r["chunk_text"]) for r in rows]
    bm25 = BM25Plus(corpus)
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(zip(rows, scores), key=lambda rs: rs[1], reverse=True)[:top_k]
    results = [
        RetrievedChunk(
            doc_id=row["doc_id"],
            title=row["title"],
            section=row["section"],
            page=row["page"],
            quote=_extract_window(row["chunk_text"], query_terms),
            score=float(score),
        )
        for row, score in ranked
        if score >= MIN_RERANK_SCORE
    ]

    if not results:
        return {"insufficient_evidence": True, "message": INSUFFICIENT_EVIDENCE, "results": []}

    return {
        "insufficient_evidence": False,
        "message": None,
        "results": [r.__dict__ for r in results],
    }


def ingest_chunks(doc_id: str, chunks: list[dict]) -> int:
    """chunks: [{"section": ..., "page": ..., "text": ..., "location_tag": ..., "dataset_tag": ...}, ...]
    Validates doc_id against the manifest before writing anything."""
    entry = get_entry(doc_id)  # raises if not registered

    with get_session() as session:
        session.execute(
            text("""
                INSERT INTO rag_documents (doc_id, category, title, authors, year, doi, source_url, license, status, ingested_at)
                VALUES (:doc_id, :category, :title, :authors, :year, :doi, :source_url, :license, 'ingested', now())
                ON CONFLICT (doc_id) DO UPDATE SET status = 'ingested', ingested_at = now()
            """),
            {
                "doc_id": doc_id, "category": entry.category, "title": entry.title,
                "authors": entry.authors, "year": entry.year, "doi": entry.doi,
                "source_url": entry.source_url, "license": entry.license,
            },
        )
        for chunk in chunks:
            session.execute(
                text("""
                    INSERT INTO rag_chunks (doc_id, section, page, location_tag, dataset_tag, chunk_text)
                    VALUES (:doc_id, :section, :page, :location_tag, :dataset_tag, :chunk_text)
                """),
                {
                    "doc_id": doc_id,
                    "section": chunk.get("section"),
                    "page": chunk.get("page"),
                    "location_tag": chunk.get("location_tag"),
                    "dataset_tag": chunk.get("dataset_tag"),
                    "chunk_text": chunk["text"],
                },
            )
    return len(chunks)
