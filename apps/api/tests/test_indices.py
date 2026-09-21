import numpy as np
import pytest

from mangrove_ai.indices import INDEX_REGISTRY, compute_all_indices, ndvi, ndwi


def test_ndvi_range_and_direction():
    healthy_veg = ndvi(nir=np.array([0.4]), red=np.array([0.05]))
    bare_ground = ndvi(nir=np.array([0.15]), red=np.array([0.12]))
    assert healthy_veg[0] > bare_ground[0]
    assert -1 <= healthy_veg[0] <= 1


def test_ndvi_handles_zero_denominator_without_nan():
    result = ndvi(nir=np.array([0.0]), red=np.array([0.0]))
    assert not np.isnan(result[0])


def test_water_has_negative_ndwi_and_vegetation_positive():
    water = ndwi(green=np.array([0.08]), nir=np.array([0.03]))
    veg = ndwi(green=np.array([0.06]), nir=np.array([0.40]))
    assert water[0] > 0  # McFeeters NDWI: water > 0
    assert veg[0] < 0


def test_compute_all_indices_skips_missing_bands():
    partial = compute_all_indices({"nir": np.array([0.3]), "red": np.array([0.1])})
    assert "NDVI" in partial
    assert "MNDWI" not in partial  # requires swir1, not provided


def test_compute_all_indices_full_bands_computes_every_index():
    bands = {k: np.array([0.1]) for k in ("blue", "green", "red", "nir", "swir1")}
    full = compute_all_indices(bands)
    assert set(full.keys()) == set(INDEX_REGISTRY.keys())


@pytest.mark.parametrize("index_name", list(INDEX_REGISTRY.keys()))
def test_every_registered_index_is_finite(index_name):
    bands = {k: np.array([0.12, 0.25, 0.4]) for k in ("blue", "green", "red", "nir", "swir1")}
    result = compute_all_indices(bands)[index_name]
    assert np.all(np.isfinite(result))
