"""Evidence/Sources page backing: manifest entries merged with their live
ingestion status from rag_documents (falls back to the manifest's own
`status` field for anything never written to the DB)."""

from __future__ import annotations

from sqlalchemy import text

from mangrove_ai.db import get_session
from mangrove_ai.rag.manifest import load_manifest


def list_sources() -> list[dict]:
    manifest = load_manifest()
    with get_session() as session:
        db_status = {r["doc_id"]: r["status"] for r in session.execute(text("SELECT doc_id, status FROM rag_documents")).mappings()}

    return [
        {**entry.model_dump(), "status": db_status.get(entry.id, entry.status)}
        for entry in manifest.values()
    ]
