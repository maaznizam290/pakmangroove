# RAGFlow Deployment — PakMang AI Scientific/Context Layer

RAGFlow (`infiniflow/ragflow`) is the production RAG engine for the
`Mangrove_AI_Knowledge` knowledge base: scientific papers, PDFs, dataset
documentation, methodology, and local Karachi studies. It runs as an
**independent Docker service**, not modified, not merged into our app code.

Raw satellite pixels and geospatial polygons never go into RAGFlow — those
live in PostGIS (`db/migrations/`) and are served by the FastAPI backend.

## Why this can't run inside the Claude Code cloud sandbox

This deployment was assembled in a sandboxed dev environment whose egress
policy permits `git clone` from GitHub (used to vendor `vendor/` below) but
returns `403` on every Docker Hub blob pull — `docker pull infiniflow/ragflow`
and its dependency images (MySQL, MinIO/Redis, Elasticsearch or Infinity) all
fail there. It is written to be run on your own machine or server, where
Docker Hub is reachable. Until then, `apps/api` talks to a local **pgvector
fallback** RAG service instead (`mangrove_ai.rag.fallback`) so the MVP stays
demoable — see `docs/architecture/RAG_LAYER.md`.

## Deploy (on a machine with normal internet access)

```bash
cd infra/ragflow
cp .env.pakmang.example .env.pakmang   # fill in real passwords + API key later
cd vendor
docker compose --env-file ../.env.pakmang -f .env -f docker-compose.yml --profile cpu up -d
```

This brings up: `ragflow` server (web UI + REST API on port 9380), MySQL,
Redis, MinIO, and the configured doc engine (Elasticsearch or Infinity —
`DOC_ENGINE` in `.env.pakmang`). First boot takes a few minutes while doc
engine indices initialize.

## One-time knowledge base setup

1. Open `http://localhost:<SVR_WEB_HTTP_PORT>`, complete the admin signup.
2. Create a knowledge base named exactly `Mangrove_AI_Knowledge`.
3. Inside it, create the eight category folders specified in the build spec
   (`01_Global_Mangrove_Research` … `08_Dataset_Documentation`) — see
   `data/knowledge_base/` in this repo for the exact taxonomy and the
   per-source metadata each upload must carry (title, authors, year, DOI,
   source, page, section, dataset, location, license).
4. Generate an API key under user settings and put it in `.env.pakmang` as
   `RAGFLOW_API_KEY`, and set `RAGFLOW_BASE_URL` to the server's reachable
   address.
5. Upload documents through the RAGFlow UI or via `apps/api`'s ingestion CLI
   (`python -m mangrove_ai.rag.ingest --source <file> --category 03_Karachi_Indus_Delta --metadata <json>`),
   which calls RAGFlow's document-upload REST API and attaches the required
   metadata fields as document tags.

## Vendor policy

`vendor/` is an unmodified copy of RAGFlow's own `docker/` deployment
folder — see `vendor/VENDOR_SOURCE.md` for the exact commit. Do not hand-edit
it; put overrides in `.env.pakmang` (env vars the vendored compose already
reads) or a `docker-compose.override.yml` placed alongside `vendor/` if a
structural change is ever needed.
