# Mangrove_AI_Knowledge — RAG Knowledge Base

Mirrors the RAGFlow knowledge base named `Mangrove_AI_Knowledge` (see
`infra/ragflow/README.md`). `SOURCES_MANIFEST.yaml` is the single source of
truth for every document this system is allowed to cite — the ingestion
pipeline (`apps/api/mangrove_ai/rag/ingest.py`) refuses to index or cite
anything not listed there.

## Categories

```
01_Global_Mangrove_Research   05_Mangrove_Restoration
02_Pakistan_Mangrove_Research 06_Species_Biodiversity
03_Karachi_Indus_Delta        07_Ecological_Risk
04_Sentinel2_Remote_Sensing   08_Dataset_Documentation
```

Each source in the manifest declares its `category` — the ingestion CLI
places the uploaded file under that folder and reads the manifest entry's
`title`/`authors`/`year`/`doi`/`source`/`dataset`/`location`/`license`
fields as the mandatory citation metadata attached to every chunk it
produces (`section`/`page` are extracted from the document itself at parse
time, per document).

## Current status

As of this build, **no source files have been uploaded** — arXiv, Zenodo,
the four journal DOIs, GMW, and the two Kaggle datasets are all behind this
sandbox's blocked egress (arxiv.org / zenodo.org / doi.org / sciencedirect.com
/ springer.com / frontiersin.org / tandfonline.com / kaggle.com all return
403 from the proxy), and the Bundal Island PDF has not yet been attached to
this session. Every entry in the manifest is `status: not_yet_uploaded`
(one, the Springer DOI, is `needs_validation` — see the manifest for why).

To add a source: drop the file under its category folder, then run
`python -m mangrove_ai.rag.ingest --id <manifest id>` — it validates the
file against the manifest entry, chunks + embeds it, and flips `status` to
`ingested`. Nothing is fabricated in place of a missing document: until a
source is ingested, `search_ragflow`/`search_rag_fallback` simply cannot
retrieve from it, and any query scoped to it returns
`"Insufficient evidence in the indexed scientific sources."`
