# PakMang AI — MVP Engineering Specification
### Geospatial Data Pipeline, API, and Dashboard — Minimum Viable Product
**Document Owner:** Geospatial Engineering / Full-Stack
**Companion Document:** [`PAKMANG_AI_ARCHITECTURE.md`](./PAKMANG_AI_ARCHITECTURE.md) (Hermes Agent + RAG product architecture)
**Status:** MVP Build Spec
**Version:** 1.0

---

## 1. Purpose & Scope

This document specifies the concrete engineering build for the PakMang AI MVP: the data ingestion pipeline, API layer, and dashboard that serve two flagship visualizations over an arbitrary user-drawn bounding box (BBOX) in the Gulf of Kutch / Indus Delta:

1. **Temporal Extent Line Graph** — annual mangrove gain vs. loss (km²), 1984–2023, from CGMD-Extent30.
2. **Ecotoxicological Stress Bar Graph** — Igeo per heavy metal vs. safe threshold, retrieved live via the RAG pipeline (per the companion architecture doc).

It also fixes the four canonical data sources, the FastAPI contract, and the PostGIS + Vector DB schema. Everything here is additive to, and must stay consistent with, the Hermes Agent / RAG design already specified in `PAKMANG_AI_ARCHITECTURE.md` — this document does not redefine RAG internals, it only specifies the API surface that exposes RAG output to the frontend.

---

## 2. Canonical Data Sources

| # | Source | Role | Access Method | Native Format |
|---|---|---|---|---|
| 1 | **Global Mangrove Watch v4** ([globalmangrovewatch.org](https://globalmangrovewatch.org)) | Baseline mangrove extent vectors (reference/reconciliation layer) | Bulk download (shapefile/GeoJSON) → one-time ETL into PostGIS | Vector polygons |
| 2 | **Zenodo Mangrove Change Layers** ([zenodo.org](https://zenodo.org)) | Historical change detection (gain/loss polygons, pre-1984 context where available) | Bulk download (versioned DOI archive) → one-time/periodic ETL into PostGIS | Vector polygons / raster change maps |
| 3 | **CGMD-Extent30** — EE asset `projects/mangrovedatahub2_assets/CGMD-Extent30SO` | Annual mangrove extent, 1984–2023, 30 m resolution — **primary source for Chart 1** | Google Earth Engine Python API (`ee.ImageCollection`) | Raster (annual binary extent mask per year) |
| 4 | **CGMD-AFCC30** — EE asset `projects/mangrovedatahub2_assets/CGMD-AFCC305` | Annual canopy dynamics (foliar cover / canopy condition), 30 m resolution | Google Earth Engine Python API (`ee.ImageCollection`) | Raster (annual continuous canopy metric) |

**Design implication:** sources 1–2 are **slow-changing reference/validation layers** ingested via scheduled batch ETL into PostGIS. Sources 3–4 are **Earth Engine–hosted rasters** queried on demand via `reduceRegion`/`reduceRegionToImage` scoped to the user's BBOX — they are never bulk-downloaded, only queried and the *results* (zonal statistics) are cached in PostGIS.

---

## 3. End-to-End Data Pipeline

```
 ┌──────────────────────────────┐   ┌──────────────────────────────┐
 │   GMW v4 (bulk vector)        │   │  Zenodo Change Layers (bulk)  │
 └───────────────┬───────────────┘   └───────────────┬───────────────┘
                 │  scheduled ETL (weekly/on-release)  │
                 ▼                                      ▼
         ┌────────────────────────────────────────────────────┐
         │         BATCH ETL WORKER  (Airflow / Prefect)         │
         │  download → reproject (EPSG:4326) → validate geom     │
         │  → upsert into PostGIS reference tables                │
         └────────────────────────────────────────────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────┐
                     │   PostGIS (reference)     │
                     │  gmw_baseline_vectors      │
                     │  zenodo_change_layers      │
                     └─────────────────────────┘


 ┌──────────────────────────────┐   ┌──────────────────────────────┐
 │  CGMD-Extent30 (EE asset)     │   │  CGMD-AFCC30 (EE asset)       │
 └───────────────┬───────────────┘   └───────────────┬───────────────┘
                 │             on-demand, BBOX-scoped   │
                 └───────────────────┬───────────────────┘
                                     ▼
                     ┌─────────────────────────────────┐
                     │   EARTH ENGINE QUERY SERVICE       │
                     │   (Python, ee.Initialize via         │
                     │    service account)                  │
                     │                                       │
                     │  per BBOX + year range:               │
                     │  ee.ImageCollection(...)              │
                     │    .filterBounds(bbox)                │
                     │    .filterDate(y0, y1)                │
                     │    .map(reduceRegion → gain/loss px)  │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌─────────────────────────────────┐
                     │   ZONAL STATS CACHE (PostGIS)      │
                     │   mangrove_extent_timeseries        │
                     │   canopy_dynamics_timeseries        │
                     │   keyed by bbox_hash + year          │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌─────────────────────────────────┐         ┌───────────────────────────┐
                     │        FASTAPI SERVICE LAYER       │ ◀────▶ │   RAG PIPELINE (Vector DB)  │
                     │  /extent-timeseries                │         │   Igeo / BCF / TF per metal  │
                     │  /canopy-dynamics                   │         │   (see architecture doc)     │
                     │  /baseline, /change-layers          │         └───────────────────────────┘
                     │  /toxicology/igeo                   │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌─────────────────────────────────┐
                     │     FRONTEND DASHBOARD              │
                     │  Streamlit + streamlit-folium       │
                     │  (Leaflet.js under the hood)         │
                     │  Chart 1: Plotly line (extent)       │
                     │  Chart 2: Plotly bar (Igeo stress)   │
                     └─────────────────────────────────┘
```

### 3.1 Why a Cache Layer Is Required ("serve instantly")

Google Earth Engine `reduceRegion` calls over a multi-decade `ImageCollection` are **not** sub-second, especially for larger BBOXes. To meet the "instant" serving requirement:

- **First request for a given BBOX + year range:** synchronous EE query if the BBOX area is below a fast-path threshold (e.g., <50 km²); otherwise the request is queued as an async job (Celery + Redis broker) and the API returns `202 Accepted` with a `job_id`, with the frontend polling `/jobs/{job_id}`.
- **Result caching:** every computed (bbox_hash, year) zonal-stat row is upserted into `mangrove_extent_timeseries` / `canopy_dynamics_timeseries`. `bbox_hash` is a deterministic hash (geohash-truncated or PostGIS `ST_SnapToGrid` on the BBOX to a fixed tile grid) so that overlapping/repeated user queries hit cache instead of re-invoking EE.
- **Tile pre-warming (recommended for MVP demo reliability):** for the Gulf of Kutch / Indus Delta AOI, pre-compute the full 1984–2023 time series on a fixed 10 km × 10 km tile grid ahead of user traffic (a one-time backfill job), so any BBOX composed of pre-warmed tiles resolves from PostGIS only — true instant response, no live EE call on the request path.

---

## 4. FastAPI Service Layer

### 4.1 Routing Overview

```
/api/v1
├── /mangrove
│   ├── GET  /baseline                 → GMW v4 vectors for BBOX
│   ├── GET  /change-layers            → Zenodo historical change polygons for BBOX
│   ├── GET  /extent-timeseries        → Chart 1 data source (CGMD-Extent30)
│   └── GET  /canopy-dynamics          → Canopy condition series (CGMD-AFCC30)
├── /toxicology
│   └── GET  /igeo                     → Chart 2 data source (RAG-derived, via Vector DB)
├── /sites
│   ├── GET  /                         → list scored AOIs (Site Registry, from Hermes Agent)
│   ├── GET  /{site_id}                → single site detail + evidence trace
│   └── POST /{site_id}/rescore        → trigger Hermes re-evaluation
├── /jobs
│   └── GET  /{job_id}                 → poll async EE computation status
└── /health
    └── GET  /                         → liveness/readiness
```

### 4.2 Endpoint Contracts

#### `GET /api/v1/mangrove/extent-timeseries`
Drives **Chart 1 (Temporal Extent Line Graph)**.

**Query params:**
| Param | Type | Required | Notes |
|---|---|---|---|
| `bbox` | `string` (`minLon,minLat,maxLon,maxLat`) | yes | User-drawn map bounds |
| `start_year` | `int` | no, default `1984` | |
| `end_year` | `int` | no, default `2023` | |

**Response `200`:**
```json
{
  "bbox": [69.02, 22.35, 69.55, 22.78],
  "bbox_hash": "gk-tile-a14f2c",
  "unit": "km2",
  "source": "CGMD-Extent30",
  "series": [
    {"year": 1984, "gain_km2": 0.0, "loss_km2": 0.0, "net_km2": 12.4},
    {"year": 1985, "gain_km2": 0.3, "loss_km2": 0.1, "net_km2": 12.6},
    "...",
    {"year": 2023, "gain_km2": 1.1, "loss_km2": 2.4, "net_km2": 9.8}
  ],
  "cache_status": "hit" | "computed" | "queued",
  "job_id": null
}
```
If BBOX exceeds the sync fast-path threshold and is not fully pre-warmed → `202` with `cache_status: "queued"` and a populated `job_id`; client polls `/jobs/{job_id}`.

#### `GET /api/v1/mangrove/canopy-dynamics`
**Query params:** same as above (`bbox`, `start_year`, `end_year`).
**Response:** analogous series shape with `afcc_index` per year (CGMD-AFCC30), used for secondary canopy-condition overlays on the dashboard map (not one of the two flagship charts, but exposed for Phase 1.5).

#### `GET /api/v1/mangrove/baseline`
**Query params:** `bbox`.
**Response:** GeoJSON `FeatureCollection` of GMW v4 polygons intersecting BBOX — rendered as the reference layer under the Leaflet/folium map.

#### `GET /api/v1/mangrove/change-layers`
**Query params:** `bbox`, optional `since` (ISO date or Zenodo version tag).
**Response:** GeoJSON `FeatureCollection` of historical change polygons (gain/loss/stable classes) from the Zenodo archive, for map overlay and cross-validation against CGMD-Extent30-derived series.

#### `GET /api/v1/toxicology/igeo`
Drives **Chart 2 (Ecotoxicological Stress Bar Graph)**. This endpoint is a thin API wrapper around the RAG pipeline's grounded-extraction output (§5.1.5 of the architecture doc) — it does not itself run retrieval logic, it calls the RAG query service and reshapes the response for the chart.

**Query params:**
| Param | Type | Required | Notes |
|---|---|---|---|
| `bbox` | `string` | yes | Resolved server-side to the nearest named location tag(s) in the Vector DB metadata (e.g., `Bundal Island`) via a BBOX→location lookup table |
| `species` | `string` | no, default `Avicennia marina` | |
| `metals` | `string` (CSV) | no, default `Fe,Cr,Mn,Zn,Pb` | |

**Response `200`:**
```json
{
  "bbox": [69.02, 22.35, 69.55, 22.78],
  "resolved_location": "Bundal Island",
  "species": "Avicennia marina",
  "bars": [
    {"metal": "Fe", "igeo": 0.6, "safe_threshold": 1.0, "status": "within_safe_range", "citation": "bundal-island-ecotox-2024, p.11, Table 3"},
    {"metal": "Cr", "igeo": 2.8, "safe_threshold": 1.0, "status": "exceeds_threshold", "citation": "bundal-island-ecotox-2024, p.12, Table 4"},
    {"metal": "Mn", "igeo": 0.9, "safe_threshold": 1.0, "status": "within_safe_range", "citation": "bundal-island-ecotox-2024, p.12, Table 4"},
    {"metal": "Zn", "igeo": 1.4, "safe_threshold": 1.0, "status": "exceeds_threshold", "citation": "bundal-island-ecotox-2024, p.13, Table 5"},
    {"metal": "Pb", "igeo": 1.1, "safe_threshold": 1.0, "status": "exceeds_threshold", "citation": "bundal-island-ecotox-2024, p.13, Table 5"}
  ],
  "coverage": "complete_for_scope" | "partial_coverage" | "no_coverage"
}
```
`safe_threshold` is pulled from the reference table `igeo_safe_thresholds` (§5.2), not from the RAG pipeline — the RAG pipeline supplies the *measured* Igeo value and citation; the safe baseline is a fixed scientific constant (Müller's Igeo class boundary, class 0/1 = "practically unpolluted," used here as `1.0`). If `coverage` is `no_coverage`, `bars` is returned empty and the frontend renders an explicit "no literature coverage for this area" state rather than a misleading empty chart.

#### `GET /api/v1/jobs/{job_id}`
```json
{"job_id": "…", "status": "pending" | "running" | "done" | "failed", "result_url": "/api/v1/mangrove/extent-timeseries?bbox=…&cache_key=…"}
```

---

## 5. Database Schema

### 5.1 PostGIS — Reference & Cache Layer

```sql
-- Extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. GMW v4 baseline vectors (bulk-loaded reference layer)
CREATE TABLE gmw_baseline_vectors (
    id              BIGSERIAL PRIMARY KEY,
    gmw_feature_id  TEXT NOT NULL,
    source_version  TEXT NOT NULL,             -- e.g. 'GMW_v4_2023'
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
    area_km2        DOUBLE PRECISION,
    ingested_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_gmw_geom ON gmw_baseline_vectors USING GIST (geom);

-- 2. Zenodo historical change layers
CREATE TABLE zenodo_change_layers (
    id              BIGSERIAL PRIMARY KEY,
    zenodo_doi      TEXT NOT NULL,
    change_class    TEXT NOT NULL CHECK (change_class IN ('gain','loss','stable')),
    period_start    DATE,
    period_end      DATE,
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_zenodo_geom ON zenodo_change_layers USING GIST (geom);

-- 3. BBOX registry — canonical grid tiles used for caching + pre-warming
CREATE TABLE bbox_tiles (
    bbox_hash       TEXT PRIMARY KEY,           -- deterministic hash of snapped BBOX
    geom            GEOMETRY(Polygon, 4326) NOT NULL,
    tile_size_km    DOUBLE PRECISION NOT NULL,  -- e.g. 10.0 for pre-warmed grid
    prewarmed       BOOLEAN DEFAULT false,
    last_computed   TIMESTAMPTZ
);
CREATE INDEX idx_bbox_tiles_geom ON bbox_tiles USING GIST (geom);

-- 4. Chart 1 data — annual extent gain/loss per BBOX tile (CGMD-Extent30 derived)
CREATE TABLE mangrove_extent_timeseries (
    id              BIGSERIAL PRIMARY KEY,
    bbox_hash       TEXT NOT NULL REFERENCES bbox_tiles(bbox_hash),
    year            INTEGER NOT NULL CHECK (year BETWEEN 1984 AND 2023),
    gain_km2        DOUBLE PRECISION NOT NULL DEFAULT 0,
    loss_km2        DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_km2         DOUBLE PRECISION NOT NULL,
    source_asset    TEXT NOT NULL DEFAULT 'projects/mangrovedatahub2_assets/CGMD-Extent30SO',
    computed_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (bbox_hash, year)
);
CREATE INDEX idx_extent_bbox_year ON mangrove_extent_timeseries (bbox_hash, year);

-- 5. Canopy dynamics series (CGMD-AFCC30 derived)
CREATE TABLE canopy_dynamics_timeseries (
    id              BIGSERIAL PRIMARY KEY,
    bbox_hash       TEXT NOT NULL REFERENCES bbox_tiles(bbox_hash),
    year            INTEGER NOT NULL CHECK (year BETWEEN 1984 AND 2023),
    afcc_index      DOUBLE PRECISION NOT NULL,   -- mean canopy metric over BBOX
    source_asset    TEXT NOT NULL DEFAULT 'projects/mangrovedatahub2_assets/CGMD-AFCC305',
    computed_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (bbox_hash, year)
);

-- 6. Fixed scientific reference constants (Igeo safe baseline per metal)
CREATE TABLE igeo_safe_thresholds (
    metal           TEXT PRIMARY KEY,   -- 'Fe','Cr','Mn','Zn','Pb'
    safe_threshold  DOUBLE PRECISION NOT NULL DEFAULT 1.0,  -- Müller class 0/1 boundary
    notes           TEXT
);

-- 7. BBOX → named-location resolution (for scoping RAG queries)
CREATE TABLE bbox_location_lookup (
    bbox_hash       TEXT NOT NULL REFERENCES bbox_tiles(bbox_hash),
    location_name   TEXT NOT NULL,      -- e.g. 'Bundal Island' — matches Vector DB metadata.location
    PRIMARY KEY (bbox_hash, location_name)
);

-- 8. Async job tracking
CREATE TABLE ee_compute_jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bbox_hash       TEXT NOT NULL,
    job_type        TEXT NOT NULL CHECK (job_type IN ('extent_timeseries','canopy_dynamics')),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','done','failed')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);
```

**Note:** the Site Registry / Evidence Ledger tables (`sites`, `site_scores`, `evidence_ledger`) that back `/api/v1/sites` are defined in the companion architecture document's Hermes Agent memory model (§4.2) — this spec assumes those tables already exist in the same PostGIS instance and does not redefine them.

### 5.2 Vector DB — RAG Corpus (summary; full spec in companion doc §5)

The Vector DB schema is unchanged from `PAKMANG_AI_ARCHITECTURE.md` §5.1.3–5.1.4. This MVP spec adds one consumption-side contract: the `/toxicology/igeo` endpoint queries the Vector DB with a **metadata-filtered hybrid search** —

```
filter: location IN (bbox_location_lookup results) AND species = 'Avicennia marina' AND metric_type = 'Igeo'
rank_by: semantic similarity to "heavy metal geo-accumulation index penalty coefficients"
```

— and joins the returned `{metal, metric_value, citation}` tuples against `igeo_safe_thresholds` in PostGIS to compute `status` (`within_safe_range` / `exceeds_threshold`) before returning the chart payload. This join is the only point where PostGIS and the Vector DB are combined in a single request path.

---

## 6. Frontend Dashboard Spec

**Stack decision for MVP:** **Streamlit** as the host application, with **`streamlit-folium`** (Leaflet.js under the hood) for the interactive BBOX-drawing map. This gives a single-language (Python) MVP that talks directly to the FastAPI service, avoids a separate JS build pipeline, and still delivers a real Leaflet map with draw/edit controls — satisfying the "Streamlit or Leaflet.js" requirement without forcing a second frontend stack for Phase 1.

### 6.1 Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  PakMang AI — Coastal Risk & Restoration Dashboard                 │
├───────────────────────────────┬───────────────────────────────────┤
│                                 │  Chart 1: Temporal Extent (1984–2023)│
│   Leaflet Map (streamlit-folium)│  ── line: cumulative gain (km²)      │
│   - GMW v4 baseline layer       │  ── line: cumulative loss (km²)      │
│   - Zenodo change overlay       │                                       │
│   - Draw-BBOX control           ├───────────────────────────────────┤
│   - Site markers (Hermes scores)│  Chart 2: Ecotoxicological Stress     │
│                                 │  ── bar per metal (Fe/Cr/Mn/Zn/Pb)    │
│                                 │  ── reference line: safe threshold    │
└───────────────────────────────┴───────────────────────────────────┘
   [Selected BBOX summary]   [Composite Site Viability Score badge]
```

### 6.2 Interaction Flow

1. User draws/edits a BBOX on the Leaflet map (`streamlit-folium` draw plugin).
2. On draw-complete, the app calls:
   - `GET /api/v1/mangrove/extent-timeseries?bbox=…` → renders **Chart 1** (Plotly dual-line chart, gain vs. loss, x-axis year 1984–2023).
   - `GET /api/v1/toxicology/igeo?bbox=…` → renders **Chart 2** (Plotly grouped bar chart, one bar per metal, a horizontal reference line at each metal's `safe_threshold`, bars colored by `status`).
3. If either call returns `cache_status: "queued"` / a `job_id`, the dashboard shows a lightweight progress state and polls `/api/v1/jobs/{job_id}` until `done`, then fetches the result.
4. GMW v4 and Zenodo layers are fetched once per BBOX change and rendered as map overlays (`/mangrove/baseline`, `/mangrove/change-layers`) for visual cross-validation against the chart data.
5. If the Hermes Agent has already scored the BBOX (`/api/v1/sites`), the composite viability score and its evidence trace are shown alongside the charts.

### 6.3 Chart Implementation Notes

- Both charts render via **Plotly** (`st.plotly_chart`) for interactivity (hover tooltips showing exact km² / Igeo values and citations) rather than static images.
- Chart 1: x-axis = year (1984–2023, integer ticks), y-axis = km², two series (gain, loss) plus an optional net-change series; a "no data" state is shown for BBOXes outside CGMD-Extent30 coverage rather than a zeroed chart.
- Chart 2: x-axis = metal symbol, y-axis = Igeo value; each bar annotated with its citation on hover; a horizontal dashed reference line at the safe threshold; bars exceeding threshold visually distinguished (not by red/green alone — pattern or label is also used, since this is a risk-communication chart and must remain legible without relying on color perception alone).
- When `/toxicology/igeo` returns `coverage: "no_coverage"`, Chart 2 renders an explicit empty-state message ("No ecotoxicological literature indexed for this area yet") rather than an empty/misleading bar chart.

---

## 7. Non-Functional Requirements (MVP)

| Requirement | Target |
|---|---|
| Chart 1 response time (pre-warmed tile) | < 300 ms |
| Chart 1 response time (cold BBOX, sync fast-path) | < 5 s |
| Chart 1 response time (cold BBOX, async path) | job completes < 60 s, progress polled every 2 s |
| Chart 2 response time (RAG query) | < 2 s (single hybrid vector query + PostGIS join) |
| BBOX size limit for MVP demo AOI (Gulf of Kutch pre-warmed grid) | up to full GMW v4 extent for the region; larger BBOXes always route async |
| Data freshness | GMW v4 / Zenodo: re-synced on new source release; CGMD-Extent30 / AFCC30: queried live against current EE asset, cached per BBOX+year (immutable once computed, since historical years don't change) |

---

*End of MVP Engineering Specification.*
