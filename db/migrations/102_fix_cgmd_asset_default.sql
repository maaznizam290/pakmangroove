-- 003 seeded cgmd_extent_annual.source_asset with a default that was
-- confirmed NOT accessible from a real GEE project (live query, Sept
-- 2026): projects/mangrovedatahub2_assets/CGMD-Extent30SO. Corrects it to
-- match the value now in mangrove_ai.config.settings.cgmd_extent_asset_id
-- — see data/knowledge_base/SOURCES_MANIFEST.yaml (cgmd-extent30) for the
-- search provenance behind the corrected id. No existing rows to backfill:
-- CGMD has not been ingested yet in any environment this migration has run
-- against, so this only changes the column default for future inserts.

ALTER TABLE cgmd_extent_annual
    ALTER COLUMN source_asset SET DEFAULT 'projects/mangrovedatahub2/assets/CGMD-Extent30';

UPDATE cgmd_extent_annual
    SET source_asset = 'projects/mangrovedatahub2/assets/CGMD-Extent30'
    WHERE source_asset = 'projects/mangrovedatahub2_assets/CGMD-Extent30SO';
