-- RAG document registry + the pgvector-backed sandbox fallback retrieval
-- store. In production, RAGFlow owns retrieval and this table only mirrors
-- its document metadata for joins (e.g. bbox_location_lookup); in the
-- sandbox fallback (mangrove_ai.rag.fallback), rag_chunks IS the retrieval
-- store. Schema matches data/knowledge_base/SOURCES_MANIFEST.yaml 1:1.

CREATE TABLE rag_documents (
    doc_id          TEXT PRIMARY KEY,             -- matches manifest 'id'
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    authors         TEXT,
    year            INTEGER,
    doi             TEXT,
    source_url      TEXT,
    license         TEXT,
    status          TEXT NOT NULL DEFAULT 'not_yet_uploaded' CHECK (status IN ('not_yet_uploaded', 'needs_validation', 'ingested')),
    ragflow_doc_id  TEXT,                          -- id assigned by RAGFlow after upload, once deployed
    checksum        TEXT,                          -- sha256 of the ingested file, to detect drift from the manifest
    ingested_at     TIMESTAMPTZ
);

CREATE TABLE rag_chunks (
    chunk_id        BIGSERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES rag_documents(doc_id),
    section         TEXT,
    page            INTEGER,
    location_tag    TEXT,                          -- e.g. 'Bundal Island' — drives bbox_location_lookup joins
    dataset_tag     TEXT,
    chunk_text      TEXT NOT NULL,
    embedding       vector(384),                   -- populated only in pgvector-fallback mode; null under RAGFlow-only deployments
    tsv             TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rag_chunks_doc ON rag_chunks (doc_id);
CREATE INDEX idx_rag_chunks_tsv ON rag_chunks USING GIN (tsv);
CREATE INDEX idx_rag_chunks_location ON rag_chunks (location_tag);
-- IVFFlat needs rows to build well; created lazily by the ingestion CLI
-- once a meaningful corpus exists (see mangrove_ai/rag/fallback.py).

-- Resolves a bbox/AOI to the named locations used to scope RAG queries
-- (e.g. so calculate_restoration_suitability over a Bundal-area AOI scopes
-- search_ragflow to 'Bundal Island' rather than the whole corpus).
CREATE TABLE aoi_location_lookup (
    aoi_id          UUID NOT NULL REFERENCES aois(aoi_id),
    location_name   TEXT NOT NULL,
    PRIMARY KEY (aoi_id, location_name)
);

-- Fixed scientific reference constants (Müller Igeo class 0/1 boundary per
-- metal) — the safe baseline the Ecotoxicological Stress chart compares
-- retrieved Igeo values against. A constant, not a RAG-retrieved value.
CREATE TABLE igeo_safe_thresholds (
    metal           TEXT PRIMARY KEY CHECK (metal IN ('Fe', 'Cr', 'Mn', 'Zn', 'Pb')),
    safe_threshold  DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    notes           TEXT
);
INSERT INTO igeo_safe_thresholds (metal, notes) VALUES
    ('Fe', 'Müller Igeo class 0/1 boundary (practically unpolluted).'),
    ('Cr', 'Müller Igeo class 0/1 boundary (practically unpolluted).'),
    ('Mn', 'Müller Igeo class 0/1 boundary (practically unpolluted).'),
    ('Zn', 'Müller Igeo class 0/1 boundary (practically unpolluted).'),
    ('Pb', 'Müller Igeo class 0/1 boundary (practically unpolluted).');
