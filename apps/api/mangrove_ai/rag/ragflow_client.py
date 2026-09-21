"""Thin wrapper around the official `ragflow_sdk` (PyPI: ragflow-sdk,
vendored deployment in infra/ragflow/vendor — see that folder's README).

Used when settings.rag_backend == "ragflow". Requires RAGFLOW_BASE_URL and
RAGFLOW_API_KEY to be set (post-deployment, on a machine that can actually
run RAGFlow's Docker stack — not this sandbox). Raises RAGFlowNotConfiguredError
rather than silently falling back, so callers decide explicitly whether to
route to the pgvector fallback (see mangrove_ai.rag.router).
"""

from __future__ import annotations

from mangrove_ai.config import settings


class RAGFlowNotConfiguredError(RuntimeError):
    pass


class RAGFlowClient:
    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not (settings.ragflow_base_url and settings.ragflow_api_key):
            raise RAGFlowNotConfiguredError(
                "RAGFLOW_BASE_URL / RAGFLOW_API_KEY are not set. Deploy RAGFlow per "
                "infra/ragflow/README.md and configure these before using the 'ragflow' backend."
            )
        from ragflow_sdk import RAGFlow

        self._client = RAGFlow(api_key=settings.ragflow_api_key, base_url=settings.ragflow_base_url)
        return self._client

    def _get_or_create_kb(self):
        client = self._ensure_client()
        existing = client.list_datasets(name=settings.ragflow_kb_name)
        if existing:
            return existing[0]
        return client.create_dataset(name=settings.ragflow_kb_name)

    def upload_document(self, file_path: str, display_name: str) -> str:
        kb = self._get_or_create_kb()
        with open(file_path, "rb") as f:
            blob = f.read()
        docs = kb.upload_documents([{"display_name": display_name, "blob": blob}])
        doc = docs[0]
        kb.async_parse_documents([doc.id])
        return doc.id

    def search(self, query: str, top_k: int = 5) -> dict:
        client = self._ensure_client()
        kb = self._get_or_create_kb()
        chunks = client.retrieve(
            question=query,
            dataset_ids=[kb.id],
            top_k=top_k,
        )
        if not chunks:
            return {"insufficient_evidence": True, "message": "Insufficient evidence in the indexed scientific sources.", "results": []}
        return {
            "insufficient_evidence": False,
            "message": None,
            "results": [
                {
                    "doc_id": c.document_id,
                    "title": getattr(c, "document_name", c.document_id),
                    "section": None,
                    "page": None,
                    "quote": c.content,
                    "score": getattr(c, "similarity", None),
                }
                for c in chunks
            ],
        }


ragflow_client = RAGFlowClient()
