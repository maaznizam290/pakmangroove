"""Exercises mangrove_ai.pipeline.materialize_composite against the real
DB. The only thing stubbed is the actual Earth Engine network boundary
(gee_client.build_annual_composite / sample_bands_at_cells) — this sandbox
has no GEE credentials, so those two calls are the one place a live
service account is unavoidable. Everything downstream (grid cells, spectral
index math, the sentinel2_composites/spectral_index_values writes) is real:
the assertions below check actual DB rows and actual mangrove_ai.indices
formula output, not mocked expectations."""

from sqlalchemy import text

from mangrove_ai import pipeline, tools
from mangrove_ai.gee_client import GEENotConfiguredError, gee_client
from mangrove_ai.indices import ndvi
from mangrove_ai.db import get_session


def _fake_sample_bands_at_cells(composite, cell_points_geojson):
    """Stands in for a live reduceRegions() response: one feature per input
    point, each carrying real-shaped Sentinel-2 reflectance values. The last
    point is deliberately given a null NIR band, the same shape GEE returns
    for a cell with no valid (unmasked) pixel."""
    features = []
    for i, _ in enumerate(cell_points_geojson):
        is_last = i == len(cell_points_geojson) - 1
        features.append({
            "properties": {
                "idx": i,
                "B2": 0.04, "B3": 0.06, "B4": 0.04,
                "B8": None if is_last else 0.35,
                "B8A": 0.33, "B11": 0.12, "B12": 0.08,
            }
        })
    return features


def test_materialize_composite_without_gee_credentials_raises(small_bbox):
    assert not gee_client.is_configured
    try:
        pipeline.materialize_composite(bbox=small_bbox)
        assert False, "expected GEENotConfiguredError"
    except GEENotConfiguredError as e:
        assert "GEE" in str(e)


def test_materialize_composite_writes_real_indices(monkeypatch, small_bbox, small_cells):
    monkeypatch.setattr(type(gee_client), "is_configured", property(lambda self: True))
    monkeypatch.setattr(gee_client, "build_annual_composite", lambda request: "fake-composite-object")
    monkeypatch.setattr(gee_client, "sample_bands_at_cells", _fake_sample_bands_at_cells)

    result = pipeline.materialize_composite(bbox=small_bbox)

    assert result["composite_id"] is not None
    assert result["cell_count"] == len(small_cells)
    # every cell but the last (null NIR) had valid data for every band
    assert result["cells_with_data"] == len(small_cells) - 1
    assert "NDVI" in result["indices_computed"]
    assert result["indices_written"] == result["cells_with_data"] * len(result["indices_computed"])

    expected_ndvi = float(ndvi(0.35, 0.04))
    with get_session() as session:
        rows = session.execute(
            text("SELECT cell_id, value FROM spectral_index_values WHERE composite_id = :cid AND index_name = 'NDVI'"),
            {"cid": result["composite_id"]},
        ).mappings().all()
        composite_row = session.execute(
            text("SELECT ee_collection, composite_type FROM sentinel2_composites WHERE composite_id = :cid"),
            {"cid": result["composite_id"]},
        ).mappings().one()

        # cleanup: this test's own rows only, so the suite leaves the DB as found
        session.execute(text("DELETE FROM spectral_index_values WHERE composite_id = :cid"), {"cid": result["composite_id"]})
        session.execute(text("DELETE FROM sentinel2_composites WHERE composite_id = :cid"), {"cid": result["composite_id"]})

    assert len(rows) == len(small_cells) - 1
    for row in rows:
        assert abs(row["value"] - expected_ndvi) < 1e-9
    assert composite_row["ee_collection"] == "COPERNICUS/S2_SR_HARMONIZED"
    assert composite_row["composite_type"] == "annual"

    # the masked cell (null NIR) must never appear — no fabricated 0.0
    all_cell_ids = {r["cell_id"] for r in rows}
    assert len(all_cell_ids) == len(small_cells) - 1


def test_query_sentinel_materializes_and_health_indicators_reads_it_back(monkeypatch, small_bbox, small_cells):
    """Closes the loop between the GEE pipeline and the backend: a real
    query_sentinel() call (the MCP tool Hermes/the API actually invoke)
    must leave rows that calculate_health_indicators() — currently reading
    an empty table in every deployment without live GEE credentials — can
    read back as real, non-fabricated data."""
    monkeypatch.setattr(type(gee_client), "is_configured", property(lambda self: True))
    monkeypatch.setattr(gee_client, "build_annual_composite", lambda request: "fake-composite-object")
    monkeypatch.setattr(gee_client, "sample_bands_at_cells", _fake_sample_bands_at_cells)

    sentinel_result = tools.query_sentinel(bbox=small_bbox)
    assert sentinel_result.data["cells_with_data"] == len(small_cells) - 1

    health_result = tools.calculate_health_indicators(bbox=small_bbox)
    assert health_result.data is not None
    assert len(health_result.data) == len(small_cells) - 1
    for cell in health_result.data:
        assert cell["label"] == "REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR"
        assert 0.0 <= cell["condition_indicator"] <= 1.0

    with get_session() as session:
        composite_id = sentinel_result.data["composite_id"]
        session.execute(text("DELETE FROM spectral_index_values WHERE composite_id = :cid"), {"cid": composite_id})
        session.execute(text("DELETE FROM sentinel2_composites WHERE composite_id = :cid"), {"cid": composite_id})
