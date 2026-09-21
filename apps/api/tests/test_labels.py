import geopandas as gpd
import pytest
from shapely.geometry import Point
from sqlalchemy import text

from mangrove_ai.db import get_session
from mangrove_ai.labels import TARGET_RESOLUTION_M, ingest_labels

TEST_SOURCE = "test-fixture-labels"  # not a real manifest id — labels.ingest_labels doesn't gate on the manifest


@pytest.fixture()
def cleanup_test_labels():
    yield
    with get_session() as session:
        session.execute(text("DELETE FROM training_labels WHERE source = :s"), {"s": TEST_SOURCE})


def test_ingest_splits_spatially_not_randomly(cleanup_test_labels):
    # 10 points spread west-to-east; the split bands are longitude-based,
    # so the westernmost points must all land in 'train' and the
    # easternmost in 'test' — never mixed by chance.
    pts = [Point(67.10 + i * 0.01, 24.78) for i in range(10)]
    gdf = gpd.GeoDataFrame({"geometry": pts}, crs="EPSG:4326")

    counts = ingest_labels(gdf, source=TEST_SOURCE, default_label_class="mangrove", source_resolution_m=30.0)

    assert sum(counts.values()) == 10
    assert counts["train"] > 0

    with get_session() as session:
        rows = session.execute(
            text("SELECT spatial_split, ST_X(geom) AS lon FROM training_labels WHERE source = :s ORDER BY lon"),
            {"s": TEST_SOURCE},
        ).mappings().all()
    lons_by_split = {}
    for r in rows:
        lons_by_split.setdefault(r["spatial_split"], []).append(r["lon"])

    if "train" in lons_by_split and "test" in lons_by_split:
        assert max(lons_by_split["train"]) < min(lons_by_split["test"])


def test_coarser_than_target_resolution_is_flagged_weak(cleanup_test_labels):
    gdf = gpd.GeoDataFrame({"geometry": [Point(67.10, 24.78)]}, crs="EPSG:4326")
    ingest_labels(gdf, source=TEST_SOURCE, default_label_class="mangrove", source_resolution_m=30.0)
    assert 30.0 > TARGET_RESOLUTION_M

    with get_session() as session:
        is_weak = session.execute(text("SELECT is_weak_label FROM training_labels WHERE source = :s"), {"s": TEST_SOURCE}).scalar()
    assert is_weak is True


def test_missing_label_class_raises():
    gdf = gpd.GeoDataFrame({"geometry": [Point(67.10, 24.78)]}, crs="EPSG:4326")
    with pytest.raises(ValueError):
        ingest_labels(gdf, source=TEST_SOURCE)
