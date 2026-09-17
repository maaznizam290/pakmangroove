# PakMang AI — Product Architecture Specification
### Predictive Coastal Risk & Restoration Intelligence Tool — Phase 1
**Target Geography:** Gulf of Kutch / Indus Delta
**Document Owner:** Solutions Architecture / AI Product
**Status:** Phase 1 — Architecture Baseline
**Version:** 1.0

---

## 1. Executive Summary

Mangrove restoration programs across the Gulf of Kutch and Indus Delta fail at an estimated rate of **~50%**, driven primarily by a planning blind spot: site-selection decisions are made almost exclusively from macro-scale remote sensing (vegetation indices, tidal inundation models, shoreline change detection) with **no visibility into localized soil and sediment toxicology** — heavy metal loading, bioconcentration behavior, and species-specific tolerance thresholds documented in fragmented, non-machine-readable scientific literature (site surveys, ecotoxicological studies, government assessments).

**PakMang AI** closes this gap by fusing two complementary intelligence systems under a single orchestration layer, the **Hermes AI Agent**:

1. A **geospatial perception pipeline** that continuously evaluates satellite-derived indices (NDVI, NDMI, tidal/inundation frequency, shoreline change) to identify and rank candidate restoration sites at macro scale.
2. A **Retrieval-Augmented Generation (RAG) pipeline** that ingests localized scientific literature (e.g., the *Bundal Island Ecotoxicological Study*) and makes buried toxicological findings — Geo-accumulation Index (Igeo), Bioconcentration Factor (BCF), Translocation Factor (TF), and heavy-metal-specific penalty coefficients for Fe, Cr, Mn, Zn, Pb — queryable in real time.

The Hermes Agent reconciles both signal streams into a single **Site Viability Score**, converting macro-scale "this location looks vegetatively viable" into a ground-truthed "this location is vegetatively viable **and** biochemically safe for *Avicennia marina* plantation." This document specifies the architecture, data flows, and operational workflows for Phase 1.

---

## 2. Problem Statement & Value Proposition

### 2.1 The Failure Mode

| Current Practice | Consequence |
|---|---|
| Site selection driven by NDVI/tidal models only | Site "looks" plantable but has toxic sediment loading |
| Ecotoxicological studies exist as static PDFs | Findings never reach field/planning teams in usable form |
| No species-specific tolerance modeling | *Avicennia marina* planted in Cr/Pb-saturated substrate → root damage, stunted growth, death |
| No feedback loop from failed plantations to site model | Same mistakes repeated across planting cycles |
| ~50% plantation failure rate | Wasted capital, carbon-credit invalidation, community trust erosion |

### 2.2 The PakMang AI Thesis

> **Macro satellite data tells you where mangroves *could* grow. Localized toxicological literature tells you where they *will survive*. Neither is sufficient alone.**

By combining a **quantitative remote-sensing agent** with a **qualitative/semi-quantitative literature-retrieval agent**, PakMang AI produces a composite risk score that macro-only tools structurally cannot produce — because the penalty coefficients for heavy metal stress on *Avicennia marina* exist only in narrative scientific text, not in any structured API or satellite band.

**Value proposition, stated operationally:**
- **Reduce plantation failure rate** by flagging sites with adverse Igeo/BCF/TF profiles *before* capital and labor are committed.
- **Compress expert review time** from days of manual literature review to seconds of semantic query.
- **Create an auditable chain of evidence** — every alert traces back to (a) the satellite index that triggered it and (b) the cited passage/coefficient from source literature that corroborates or overrides it.
- **Institutionalize local scientific knowledge** that would otherwise remain siloed in PDFs held by individual research institutions.

---

## 3. System Overview

```
                         ┌────────────────────────────────────────┐
                         │              HERMES AI AGENT            │
                         │   (Perception → Planning → Action Loop) │
                         └────────────────────────────────────────┘
                                   │                    │
                 ┌─────────────────┘                    └─────────────────┐
                 ▼                                                        ▼
   ┌───────────────────────────┐                          ┌───────────────────────────┐
   │  REMOTE SENSING PIPELINE   │                          │      RAG PIPELINE          │
   │  (Macro / Quantitative)    │                          │  (Local / Toxicological)   │
   │                             │                          │                             │
   │  Sentinel-2 / Landsat feed  │                          │  Scientific PDFs (Bundal    │
   │  → NDVI, NDMI, Inundation   │                          │  Island study, sediment     │
   │  → Shoreline change delta   │                          │  surveys, govt reports)     │
   │  → Candidate site ranking   │                          │  → Chunk → Embed → Vector DB│
   └───────────────────────────┘                          │  → Semantic query for Igeo,  │
                 │                                          │    BCF, TF, metal coeffs   │
                 │                                          └───────────────────────────┘
                 │                                                        │
                 └───────────────────┬────────────────────────────────────┘
                                      ▼
                         ┌────────────────────────────────────┐
                         │   COMPOSITE SITE VIABILITY SCORE     │
                         │   (Vegetative Signal × Toxicological │
                         │           Penalty Coefficient)        │
                         └────────────────────────────────────┘
                                      │
                                      ▼
                         ┌────────────────────────────────────┐
                         │   LOCALIZED ALERTS & RECOMMENDATIONS │
                         │   (Field teams, GIS dashboard, API)  │
                         └────────────────────────────────────┘
```

---

## 4. The Hermes AI Agent Layer

The Hermes Agent is the orchestration brain of PakMang AI. It does not itself run models — it **coordinates** the remote sensing pipeline, the RAG pipeline, and downstream alerting through a continuous **Perception → Planning → Action** loop, with a persistent memory store that lets each loop iteration build on prior state (previously scored sites, previously retrieved literature findings, prior alert history).

### 4.1 Loop Architecture

```
        ┌──────────────────────────────────────────────────────────────┐
        │                                                                │
        ▼                                                                │
┌───────────────┐      ┌───────────────┐      ┌───────────────┐         │
│  PERCEPTION    │ ───▶ │   PLANNING     │ ───▶ │    ACTION      │ ───────┘
│                │      │                │      │                │
│ Ingest new     │      │ Reconcile      │      │ Fire alerts /  │
│ satellite pass │      │ macro + micro  │      │ update scores /│
│ + check RAG    │      │ signals; decide│      │ trigger new    │
│ index freshness│      │ next queries   │      │ RAG retrieval  │
└───────────────┘      └───────────────┘      └───────────────┘
```

#### 4.1.1 Perception Phase

**Objective:** Sense state changes across both data domains.

| Input Source | Signal Captured | Trigger Cadence |
|---|---|---|
| Sentinel-2 / Landsat-8/9 (via STAC catalog) | New scene availability over AOI (Area of Interest) polygons | Per revisit (5–16 days, cloud-filtered) |
| Derived index rasters | NDVI, NDMI (moisture), NDWI, tidal inundation frequency | Recomputed per new scene |
| Shoreline change models | Erosion/accretion delta vs. historical baseline | Rolling 90-day window |
| Vector DB (RAG corpus) | New or updated scientific documents ingested | Event-driven (on document upload) |
| Field reports (Phase 2 hook) | Ground-truth plantation survival data | Manual/batch upload |

**Perception outputs a structured `PerceptionEvent`:**
```json
{
  "event_type": "new_satellite_pass" | "new_literature_ingested" | "field_report_update",
  "aoi_id": "gulf-kutch-tile-042",
  "timestamp": "2026-09-17T00:00:00Z",
  "payload_ref": "s3://pakmang-raw/scenes/..."
}
```

#### 4.1.2 Planning Phase

**Objective:** Decide what computation and retrieval is needed, and reconcile signals from both pipelines into a single score.

The Planning phase runs a decision procedure per AOI candidate site:

1. **Index Calculation** — compute/update NDVI, NDMI, inundation frequency, shoreline stability for the AOI.
2. **Threshold Check** — does the AOI clear the macro-scale plantability bar (e.g., NDVI trend positive, inundation frequency within *Avicennia marina* tolerance range, no active erosion)?
3. **Toxicological Query Dispatch** — if the AOI clears step 2, the Planner constructs a semantic query against the RAG pipeline scoped to the AOI's region/island (e.g., "Bundal Island heavy metal Igeo Cr Pb sediment") to retrieve applicable penalty coefficients.
4. **Score Reconciliation** — combine the macro viability signal with the retrieved toxicological penalty (see §6) into a **Composite Site Viability Score**.
5. **Action Selection** — decide whether the outcome warrants: (a) no action (site remains provisionally viable, re-check next cycle), (b) a **localized alert** (site flagged high-risk or newly viable), or (c) an **escalation** (conflicting/insufficient evidence, route to human ecotoxicologist review).

The Planner is implemented as a rules-augmented LLM reasoning step: deterministic thresholds (index cutoffs) are enforced in code, while the *reconciliation* of qualitative literature findings (e.g., "Igeo class 3 = moderately to strongly polluted") against quantitative index scores uses the LLM's reasoning over the retrieved RAG context, grounded strictly in returned citations (no free-generation of coefficients).

#### 4.1.3 Action Phase

**Objective:** Execute the decision — persist state, notify, or trigger further investigation.

| Action Type | Mechanism |
|---|---|
| **Localized Alert** | Push to GIS dashboard + notification channel (email/Slack/webhook) with AOI polygon, composite score, and evidence trace (index values + cited literature passage) |
| **Score Update** | Write composite score + component scores to the Site Registry (persistent store) |
| **Escalation** | Create a review task assigned to a human domain expert with the conflicting evidence surfaced side-by-side |
| **RAG Re-query** | If confidence is below threshold, Planner loops back and issues a refined query (e.g., broaden from island-specific to regional-estuary literature) before finalizing |

**Alert payload example:**
```json
{
  "alert_id": "pkm-alert-2026-0917-042",
  "aoi_id": "bundal-island-sector-3",
  "composite_score": 0.34,
  "classification": "HIGH_RISK — not recommended for planting",
  "macro_signal": {
    "ndvi_trend": "positive",
    "inundation_frequency": "within_tolerance"
  },
  "toxicological_signal": {
    "igeo_class": 3,
    "dominant_metal": "Cr",
    "bcf": 1.42,
    "tf": 0.38,
    "source_citation": "Bundal Island Ecotoxicological Study, Table 4, p.12"
  },
  "recommendation": "Defer planting pending sediment remediation or species substitution."
}
```

### 4.2 Memory & State

The Hermes Agent maintains three persistent stores across loop iterations:
- **Site Registry** — one record per AOI polygon with current composite score, historical score trajectory, and last-evaluated timestamp.
- **Evidence Ledger** — append-only log linking every alert to its exact source inputs (satellite scene ID + RAG document chunk IDs), enabling full auditability.
- **Query Cache** — recently issued RAG queries and their results, to avoid redundant retrieval calls within a planning cycle and to detect when newly ingested literature should trigger re-evaluation of previously scored sites.

---

## 5. The RAG Pipeline Architecture

The RAG pipeline's purpose is narrow and precise: convert unstructured, locally-produced ecotoxicological literature into a **queryable source of ground-truth penalty coefficients** that the Hermes Agent can cite, not paraphrase from memory.

### 5.1 Pipeline Stages

```
[1] INGESTION           [2] PARSING             [3] CHUNKING
Raw PDFs (scientific  → Extract text, tables,  → Semantic + structural
studies, govt surveys)  figures/captions          chunking (section-aware)
                         via layout-aware parser
        │                                                │
        ▼                                                ▼
[4] EMBEDDING                                    [5] METADATA TAGGING
Chunk → embedding vector                          Tag each chunk: species,
(domain-tuned model)                              location, metal type,
                                                   metric type (Igeo/BCF/TF)
        │                                                │
        └───────────────────┬────────────────────────────┘
                             ▼
                    [6] VECTOR DB STORAGE
              (embedding + metadata + source span)
                             │
                             ▼
                [7] SEMANTIC QUERY / RETRIEVAL
        Hermes Agent query → top-k relevant chunks
        → re-rank → grounded coefficient extraction
```

#### 5.1.1 Ingestion & Parsing

- **Source corpus (Phase 1):** peer-reviewed and institutional ecotoxicological studies specific to the Gulf of Kutch / Indus Delta region — the *Bundal Island Ecotoxicological Study* is the canonical Phase 1 seed document, alongside comparable sediment/species surveys as they become available.
- **Parser:** a layout-aware document parser (table-structure-preserving) is required, not plain-text extraction — the target data (Igeo, BCF, TF, metal concentration tables) is almost always embedded in **tables and figure captions**, which naive text extraction corrupts.
- **Output of this stage:** a structured intermediate representation per document — page-anchored text blocks, extracted tables as structured rows (metal, location, concentration, index value), and figure captions linked to their referenced figure.

#### 5.1.2 Chunking Strategy

Plain fixed-window chunking is insufficient because a single relevant fact (e.g., "Cr Igeo = 2.8 at Site B") is meaningless without its table header context (which metal, which site, which index). Chunking therefore is **structure-aware**:
- Narrative text: chunked by section/subsection boundaries (e.g., "Results — Heavy Metal Accumulation").
- Tables: each row (or logical row-group) is serialized as a **self-contained statement** — e.g., *"At Bundal Island Sector 3, the Geo-accumulation Index (Igeo) for Chromium (Cr) is 2.8, classified as moderately to strongly polluted."* This denormalization is critical: it ensures a retrieved chunk carries full semantic context even in isolation.
- Each chunk retains a pointer back to its exact source location (document ID, page number, table/paragraph ID) for citation and audit purposes.

#### 5.1.3 Metadata Tagging

Every chunk is tagged at ingestion time with structured metadata to support hybrid (metadata-filtered + semantic) retrieval:

| Metadata Field | Example Values |
|---|---|
| `document_id` | `bundal-island-ecotox-2024` |
| `location` | `Bundal Island`, `Gulf of Kutch`, `Indus Delta` |
| `species` | `Avicennia marina` |
| `metal` | `Fe`, `Cr`, `Mn`, `Zn`, `Pb` |
| `metric_type` | `Igeo`, `BCF`, `TF`, `raw_concentration` |
| `metric_value` | numeric, extracted where structured |
| `source_page` | integer |

#### 5.1.4 Embedding & Vector Storage

- Each chunk (narrative or serialized table row) is embedded using a domain-appropriate embedding model.
- Vectors are stored in a **Vector DB** alongside their metadata payload and raw source text, enabling three retrieval modes:
  1. **Pure semantic search** (natural-language query → nearest chunks)
  2. **Metadata-filtered search** (e.g., `metal=Cr AND location=Bundal Island` narrowed before/alongside vector similarity)
  3. **Hybrid** (default for Hermes Agent queries — filter by AOI location tags first, then rank by semantic relevance to the query intent)

#### 5.1.5 Semantic Query / Extraction

When the Hermes Planning phase dispatches a toxicological query (§4.1.2, step 3), the RAG pipeline executes:

1. **Query construction** — the Agent builds a query scoped by AOI location and target species (e.g., *"heavy metal penalty coefficients Fe Cr Mn Zn Pb Avicennia marina Bundal Island"*).
2. **Retrieval** — top-k chunks returned via hybrid search, re-ranked for relevance.
3. **Grounded extraction** — the LLM extracts structured coefficients (Igeo class, BCF, TF, per-metal values) **only from retrieved chunk text**, with each extracted value carrying its source citation. The extraction step is constrained (structured-output / schema-enforced) to prevent hallucinated numeric values — if a queried coefficient is not present in retrieved chunks, the pipeline returns "insufficient literature coverage" rather than fabricating a figure.
4. **Return to Planner** — structured coefficient object + citations passed back to the Hermes Planning phase for score reconciliation.

**Example structured extraction output:**
```json
{
  "query_scope": "Bundal Island / Avicennia marina",
  "coefficients": [
    {"metal": "Cr", "igeo": 2.8, "igeo_class": "moderately to strongly polluted", "bcf": 1.42, "tf": 0.38, "citation": "bundal-island-ecotox-2024, p.12, Table 4"},
    {"metal": "Pb", "igeo": 1.1, "igeo_class": "unpolluted to moderately polluted", "bcf": 0.87, "tf": 0.52, "citation": "bundal-island-ecotox-2024, p.13, Table 5"}
  ],
  "coverage": "complete_for_scope"
}
```

### 5.2 Why This Matters: Grounding Discipline

The single most important architectural constraint in the RAG pipeline is that **numeric penalty coefficients are never generated — only retrieved and cited**. Ecotoxicological thresholds are scientifically and legally consequential; an LLM approximating "Cr Igeo is probably around 2.5" from parametric knowledge is unacceptable. The schema-enforced extraction step and the "insufficient coverage" fallback exist specifically to prevent this failure mode.

---

## 6. Composite Site Viability Scoring

The reconciliation step in Planning (§4.1.2) combines both pipelines into one actionable score:

```
Composite Score = f(Macro Viability Signal, Toxicological Penalty)

where:
  Macro Viability Signal ∈ [0, 1]   — derived from NDVI/NDMI/inundation/shoreline trend
  Toxicological Penalty  ∈ [0, 1]   — derived from Igeo class + BCF/TF profile
                                       per retrieved metal coefficients

  Composite Score = Macro Viability Signal × (1 − Toxicological Penalty)
```

- A site with strong vegetative/tidal indicators but a high Igeo class for Cr or Pb (elevated bioaccumulation risk for *Avicennia marina*) is **down-weighted**, even though satellite data alone would have flagged it as prime real estate.
- A site with moderate vegetative indicators but clean toxicological literature coverage may be **up-weighted** relative to a purely macro-driven ranking.
- If no literature coverage exists for a given AOI, the score is returned with an explicit **`coverage: unknown`** flag rather than assuming a neutral/zero penalty — this prevents silent overconfidence in under-studied areas and instead routes the site to the escalation queue for manual scientific review or literature commissioning.

This scoring function is intentionally simple and interpretable for Phase 1 — every component is traceable to its source (a specific satellite index value or a specific cited coefficient), which is the core auditability requirement for a restoration-investment decision tool.

---

## 7. Operational Workflow Summary

**End-to-end cycle, one AOI:**

1. New Sentinel-2 scene lands for Gulf of Kutch tile → **Perception** triggers.
2. Hermes Agent recomputes NDVI/NDMI/inundation indices for affected AOIs → **Planning** begins.
3. AOIs clearing the macro threshold are queried against the RAG pipeline, scoped by location/species metadata.
4. RAG pipeline retrieves and grounds Igeo/BCF/TF coefficients for Fe/Cr/Mn/Zn/Pb from indexed literature (e.g., Bundal Island study) with citations.
5. Hermes Agent reconciles macro + toxicological signals into a Composite Site Viability Score.
6. **Action:** score persisted to Site Registry; if the score crosses an alert threshold (newly high-risk or newly viable), a localized alert is pushed to the GIS dashboard/notification channel with full evidence trace; low-confidence/low-coverage cases are escalated to a human ecotoxicologist.
7. Evidence Ledger records the full chain (scene ID + RAG chunk IDs) for audit.
8. Loop repeats on next satellite revisit or next literature ingestion event.

---

## 8. Phase 1 Scope Boundaries

**In scope:**
- Single-region corpus (Gulf of Kutch / Indus Delta), seeded with the Bundal Island Ecotoxicological Study and comparable regional literature.
- Five target metals: Fe, Cr, Mn, Zn, Pb.
- Single target species: *Avicennia marina*.
- Composite scoring + alerting; human-in-the-loop escalation for low-confidence cases.

**Explicitly out of scope for Phase 1 (candidate Phase 2+):**
- Automated field-report feedback loop closing back into score calibration.
- Multi-species tolerance modeling.
- Automated remediation-cost estimation.
- Real-time IoT soil-sensor ingestion (literature-derived coefficients only in Phase 1; sensor fusion is a future extension of the Perception layer).

---

## 9. Success Metrics

| Metric | Phase 1 Target |
|---|---|
| Reduction in plantation failure rate (vs. ~50% baseline) | Directional evidence via retrospective backtest against known failed sites |
| RAG extraction precision (coefficient correctness vs. manual audit) | ≥95% on sampled citations |
| Alert-to-evidence traceability | 100% (every alert must resolve to a specific scene + chunk citation) |
| "Insufficient coverage" false-negative rate (i.e., coefficient existed but pipeline missed it) | <5% on held-out document set |

---

*End of Phase 1 Architecture Specification.*
