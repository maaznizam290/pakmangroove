"""Picks the RAG backend per settings.rag_backend. This is the only place
search_ragflow (the MCP tool) needs to know about — callers never branch
on backend themselves."""

from __future__ import annotations

from mangrove_ai.config import settings
from mangrove_ai.rag import fallback
from mangrove_ai.rag.ragflow_client import ragflow_client


def search(query: str, location: str | None = None, category: str | None = None, top_k: int = 5) -> dict:
    if settings.rag_backend == "ragflow":
        return ragflow_client.search(query, top_k=top_k)
    return fallback.search(query, location=location, category=category, top_k=top_k)
