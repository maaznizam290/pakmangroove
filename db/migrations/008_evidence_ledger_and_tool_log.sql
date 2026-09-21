-- Full audit trail: every Hermes tool call and every citation used in an
-- answer, so any suitability score or RAG-grounded claim traces back to
-- its exact inputs. This is what makes the anti-hallucination rules
-- enforceable after the fact, not just aspirational.

CREATE TABLE hermes_runs (
    hermes_run_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_question   TEXT NOT NULL,
    aoi_id          UUID REFERENCES aois(aoi_id),
    planner_mode    TEXT NOT NULL CHECK (planner_mode IN ('llm', 'rule_based')),
    status          TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed')),
    final_answer    JSONB,                         -- the OBSERVED/DERIVED/SCIENTIFIC EVIDENCE/MODEL OUTPUT/LIMITATIONS envelope
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

CREATE TABLE hermes_tool_calls (
    call_id         BIGSERIAL PRIMARY KEY,
    hermes_run_id   UUID NOT NULL REFERENCES hermes_runs(hermes_run_id),
    tool_name       TEXT NOT NULL,                 -- e.g. 'query_sentinel', 'calculate_restoration_suitability'
    parameters      JSONB NOT NULL,
    result_summary  JSONB NOT NULL,                -- the tool's {data, source, timestamp, parameters, model_version, confidence, limitations} envelope, trimmed
    called_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms     INTEGER
);
CREATE INDEX idx_hermes_tool_calls_run ON hermes_tool_calls (hermes_run_id);

CREATE TABLE evidence_ledger (
    evidence_id     BIGSERIAL PRIMARY KEY,
    hermes_run_id   UUID REFERENCES hermes_runs(hermes_run_id),
    suitability_cell_id BIGINT REFERENCES suitability_cells(id),
    evidence_type   TEXT NOT NULL CHECK (evidence_type IN ('rag_citation', 'satellite_scene', 'dataset_row', 'model_output')),
    doc_id          TEXT REFERENCES rag_documents(doc_id),
    chunk_id        BIGINT REFERENCES rag_chunks(chunk_id),
    ref_description TEXT NOT NULL,                 -- human-readable pointer, e.g. 'CGMD-Extent30 cell 41821, year 2023'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evidence_ledger_run ON evidence_ledger (hermes_run_id);
CREATE INDEX idx_evidence_ledger_cell ON evidence_ledger (suitability_cell_id);
