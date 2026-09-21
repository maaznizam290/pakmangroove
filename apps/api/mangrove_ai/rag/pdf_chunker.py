"""Page-anchored PDF chunking. Deliberately page-level (not fixed-token-
window) so every chunk keeps its `page` citation exact — the build spec
requires every RAG document to preserve page/section, and a sliding token
window that crosses page boundaries loses that."""

from __future__ import annotations

from pypdf import PdfReader


def chunk_pdf(path: str, location_tag: str | None = None, dataset_tag: str | None = None) -> list[dict]:
    reader = PdfReader(path)
    chunks = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        # split long pages into paragraph-sized pieces, still tagged with the same page number
        for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
            chunks.append({
                "section": None,   # section headers aren't reliably extractable from raw PDF text; left null rather than guessed
                "page": page_num,
                "text": para,
                "location_tag": location_tag,
                "dataset_tag": dataset_tag,
            })
    return chunks
