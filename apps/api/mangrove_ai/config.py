"""Central configuration. Every credential is read from the environment —
never hardcoded, never committed (see .env.example)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/mangrove_ai"

    # --- Google Earth Engine ---
    # Path to a service-account JSON key. Unset -> gee_client runs in
    # fixture mode (no live calls), per the explicit decision to build the
    # real GEE client without live calls until credentials are supplied.
    gee_service_account_email: str | None = None
    gee_service_account_key_path: str | None = None
    gee_project: str | None = None

    # Per build instructions: do not assume "CGMD-AFCC305" exists. This
    # must be confirmed against the CGMD data hub before use; left unset
    # by default so misconfiguration fails loudly instead of silently
    # querying a possibly-nonexistent asset.
    cgmd_extent_asset_id: str = "projects/mangrovedatahub2_assets/CGMD-Extent30SO"
    cgmd_afcc_asset_id: str | None = None

    s2_sr_collection: str = "COPERNICUS/S2_SR_HARMONIZED"
    s2_cloud_prob_collection: str = "COPERNICUS/S2_CLOUD_PROBABILITY"
    s2_cloud_prob_max: float = 40.0

    # --- RAG ---
    rag_backend: str = "pgvector_fallback"  # "ragflow" | "pgvector_fallback"
    ragflow_base_url: str | None = None
    ragflow_api_key: str | None = None
    ragflow_kb_name: str = "Mangrove_AI_Knowledge"

    # --- Hermes / LLM planning ---
    # If unset, Hermes runs its deterministic rule-based planner instead of
    # LLM-driven planning — it still calls the same tools in the same
    # documented sequence, it just doesn't reason about ambiguous cases.
    anthropic_api_key: str | None = None
    hermes_model: str = "claude-sonnet-5"

    # --- Restoration suitability ---
    # Proximity (metres) within which a suitability cell is considered
    # "near" an ecological_risk_samples point, for the
    # LOCAL_ECOLOGICAL_RISK_EVIDENCE_AVAILABLE flag. This is a fixed
    # radius around real sample points, never an interpolation.
    ecological_risk_proximity_m: float = 500.0

    grid_cell_size_m: float = 30.0


settings = Settings()
