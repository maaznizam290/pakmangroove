"""Loads data/knowledge_base/SOURCES_MANIFEST.yaml — the single allow-list
of documents the RAG layer may ever chunk, embed, or cite. Ingestion
refuses anything not listed here (see ingest.py)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = REPO_ROOT / "data" / "knowledge_base" / "SOURCES_MANIFEST.yaml"
KB_ROOT = REPO_ROOT / "data" / "knowledge_base"


class ManifestEntry(BaseModel):
    id: str
    category: str
    title: str
    authors: str | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    source_url: str | None = None
    usage: str | None = None
    license: str | None = None
    status: str = "not_yet_uploaded"
    location: str | None = None
    dataset_priority: list[str] | None = None
    precedence: str | None = None


def load_manifest() -> dict[str, ManifestEntry]:
    with open(MANIFEST_PATH) as f:
        raw = yaml.safe_load(f)
    return {entry["id"]: ManifestEntry(**entry) for entry in raw}


def get_entry(doc_id: str) -> ManifestEntry:
    entries = load_manifest()
    if doc_id not in entries:
        raise KeyError(f"'{doc_id}' is not in {MANIFEST_PATH} — refusing to treat an unregistered document as a source.")
    return entries[doc_id]
