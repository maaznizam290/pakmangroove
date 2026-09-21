import pytest
from sqlalchemy import text

from mangrove_ai.db import get_session
from mangrove_ai.rag import fallback

TEST_DOC_ID = "bundal-island-ecotoxicology"  # a real manifest entry — see data/knowledge_base/SOURCES_MANIFEST.yaml


@pytest.fixture()
def ingested_test_chunk():
    chunks = [{
        "section": "Results", "page": 12,
        "text": ("TEST FIXTURE SENTENCE. At Bundal Island Sector 3, the Geo-accumulation Index (Igeo) for "
                  "Chromium is a placeholder test value used only to verify retrieval plumbing."),
        "location_tag": "Bundal Island", "dataset_tag": TEST_DOC_ID,
    }]
    fallback.ingest_chunks(TEST_DOC_ID, chunks)
    yield
    with get_session() as session:
        session.execute(text("DELETE FROM rag_chunks WHERE dataset_tag = :d"), {"d": TEST_DOC_ID})
        session.execute(text("UPDATE rag_documents SET status = 'not_yet_uploaded', ingested_at = NULL WHERE doc_id = :d"), {"d": TEST_DOC_ID})


def test_ingest_refuses_unregistered_document_id():
    with pytest.raises(KeyError):
        fallback.ingest_chunks("not-a-real-manifest-id", [{"text": "x"}])


def test_search_finds_relevant_chunk_with_citation(ingested_test_chunk):
    result = fallback.search("Igeo Chromium Bundal Island", location="Bundal Island")
    assert result["insufficient_evidence"] is False
    assert len(result["results"]) == 1
    hit = result["results"][0]
    assert hit["doc_id"] == TEST_DOC_ID
    assert hit["page"] == 12
    assert "Chromium" in hit["quote"]


def test_search_returns_insufficient_evidence_for_unrelated_query(ingested_test_chunk):
    result = fallback.search("quantum computing hardware architecture")
    assert result["insufficient_evidence"] is True
    assert result["message"] == fallback.INSUFFICIENT_EVIDENCE
    assert result["results"] == []


def test_search_with_no_corpus_at_all_is_insufficient_not_an_error():
    result = fallback.search("anything at all, nothing is indexed")
    assert result["insufficient_evidence"] is True
