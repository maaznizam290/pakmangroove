"""Ingestion CLI: python -m mangrove_ai.rag.ingest --id <manifest-id> --file <path>

Validates the file against SOURCES_MANIFEST.yaml, chunks it (page-anchored
for PDFs), and writes it through the configured RAG backend. Refuses to
ingest anything not already registered in the manifest — this is the
enforcement point that keeps every citation traceable to a real,
declared source (see data/knowledge_base/README.md).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from mangrove_ai.config import settings
from mangrove_ai.rag import fallback
from mangrove_ai.rag.manifest import KB_ROOT, get_entry
from mangrove_ai.rag.pdf_chunker import chunk_pdf
from mangrove_ai.rag.ragflow_client import ragflow_client


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def ingest(doc_id: str, file_path: str) -> None:
    entry = get_entry(doc_id)
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"{file_path} does not exist")

    dest_dir = KB_ROOT / entry.category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy(src, dest)

    checksum = _sha256(dest)
    location_tag = entry.location or ("Bundal Island" if "bundal" in doc_id else None)

    if settings.rag_backend == "ragflow":
        ragflow_doc_id = ragflow_client.upload_document(str(dest), display_name=entry.title)
        print(f"Uploaded to RAGFlow as document {ragflow_doc_id}. Parsing runs async server-side.")
        return

    if dest.suffix.lower() == ".pdf":
        chunks = chunk_pdf(str(dest), location_tag=location_tag, dataset_tag=doc_id)
    else:
        text = dest.read_text(errors="ignore")
        chunks = [{"section": None, "page": None, "text": p.strip(), "location_tag": location_tag, "dataset_tag": doc_id}
                  for p in text.split("\n\n") if p.strip()]

    if not chunks:
        raise ValueError(f"No extractable text found in {dest} — refusing to register an empty document.")

    n = fallback.ingest_chunks(doc_id, chunks)
    print(f"Ingested {n} chunks for '{doc_id}' into the pgvector fallback store. Checksum: {checksum}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="manifest id from SOURCES_MANIFEST.yaml")
    parser.add_argument("--file", required=True, help="path to the source file to ingest")
    args = parser.parse_args()
    ingest(args.id, args.file)
