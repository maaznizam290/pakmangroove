# Mangrove AI Intelligence

A geospatial AI system for the Karachi coast / Bundal Island / Indus Delta:
Sentinel-2 ingestion, mangrove detection, health/change analysis, a
Restoration Suitability model, a scientific RAG layer, and Hermes — the
autonomous orchestrator that ties them together through 15 MCP tools.

**Every restoration candidate is labeled "Candidate only — field
validation required." This system never says where to plant mangroves —
only where restoration may be worth investigating on the ground.**

See `docs/architecture/PAKMANG_AI_ARCHITECTURE.md` and
`PAKMANG_AI_MVP_ENGINEERING_SPEC.md` for the original product/engineering
specs this build follows.

## Repository layout

```
apps/api/            FastAPI backend + the mangrove_ai Python package
  mangrove_ai/
    indices.py         Spectral index library (NDVI, EVI, MSAVI, NDWI, ...)
    gee_client.py       Sentinel-2/GEE pipeline (credential-gated)
    health.py             Canopy condition indicator
    change.py               Change detection (OBSERVED/DERIVED/MODELLED)
    suitability.py            Restoration suitability scoring engine
    risk_evidence.py            Bundal point-only ecological risk lookup
    models/                      RF/GBM baseline classifier + UNet++ gate
    labels.py                      Zenodo/GMW label ingestion (spatial split)
    rag/                             RAGFlow client + pgvector fallback + ingest CLI
    tools.py                          All 15 MCP tool implementations
    hermes/                             Tool specs + the Hermes orchestrator
    mcp_server.py                        Stdio MCP server
    active_learning.py                    Review queue + human-gated promotion
  app/                                    FastAPI app + REST routers
  tests/                                    63 tests, incl. the required e2e test
apps/web/             Next.js + TypeScript + Tailwind frontend (10 pages)
db/migrations/        PostGIS + pgvector schema (27 tables)
infra/ragflow/        Vendored RAGFlow deploy (infiniflow/ragflow, unmodified)
data/knowledge_base/  RAG source registry + 8-category taxonomy
```

## Local setup

```bash
# 1. Database
sudo pg_ctlcluster 16 main start   # or your platform's postgres start
createdb mangrove_ai
psql -d mangrove_ai -c "CREATE EXTENSION postgis; CREATE EXTENSION vector; CREATE EXTENSION pgcrypto;"
for f in db/migrations/*.sql; do psql -d mangrove_ai -f "$f"; done

# 2. Backend
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values — see "What's not wired up" below
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev   # http://localhost:3000
```

Run the test suite: `cd apps/api && source .venv/bin/activate && pytest tests/ -v`
(runs against the real local Postgres instance above; every test cleans up after itself).

## What's real vs. what's pending real data

This build was authored inside a sandboxed cloud dev environment whose
egress policy blocks `arxiv.org`, `zenodo.org`, `doi.org`, most journal
publishers, Kaggle, and Docker Hub's image CDN — so it could not download
the cited papers/datasets, query Earth Engine live, or run RAGFlow's own
Docker stack from inside that sandbox. Every code path is real, not a
stub, and was verified end-to-end (unit tests, live HTTP calls, a
Playwright browser session against the actual frontend) — but the tables
that depend on those external sources are honestly empty until someone
with normal network access completes these:

| Needed | What to do |
|---|---|
| Google Earth Engine access | Set `GEE_SERVICE_ACCOUNT_EMAIL` / `GEE_SERVICE_ACCOUNT_KEY_PATH` in `apps/api/.env`. Confirm the real CGMD-AFCC30 Earth Engine asset id before setting `CGMD_AFCC_ASSET_ID` — do not assume `CGMD-AFCC305` exists (see `mangrove_ai/config.py`). |
| Scientific sources (arXiv, Zenodo, 4 journal DOIs, GMW, 2 Kaggle datasets, Bundal PDF) | Upload each file, then `python -m mangrove_ai.rag.ingest --id <manifest-id> --file <path>` — see `data/knowledge_base/SOURCES_MANIFEST.yaml` for every registered source and its current status. |
| RAGFlow (production RAG backend) | Deploy on a machine with normal internet access per `infra/ragflow/README.md`, then set `RAG_BACKEND=ragflow` + `RAGFLOW_BASE_URL`/`RAGFLOW_API_KEY`. Until then the app runs on the pgvector/BM25 fallback (`RAG_BACKEND=pgvector_fallback`, the default). |
| Pakistan mangrove training labels | `python -m mangrove_ai.labels --file <zenodo-shapefile> --source zenodo-10.5281-zenodo.10732690 --default-label-class mangrove` (Indus Delta / Sandspit / MangroveSitesShapefile per the build spec's priority order). |
| Hermes LLM-driven planning | Set `ANTHROPIC_API_KEY`. Without it, Hermes runs its deterministic rule-based planner — same tools, same sequence, no LLM reasoning over ambiguous cases. |

Once GEE credentials + labels are in place, run the RF/GBM baseline
(`python -m mangrove_ai.models.baseline`) against real materialized
Sentinel-2 composites, register it via
`mangrove_ai.active_learning.register_candidate_model`, and promote it
with a real human identifier — never `system` or `hermes_retrain_job`,
which `promote_model` refuses by design.
