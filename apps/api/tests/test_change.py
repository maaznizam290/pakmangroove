import numpy as np
import pytest

from mangrove_ai.change import classify_extent_change, fragmentation_index


def test_growing_extent_classified_as_gain():
    series = {2000: 10.0, 2005: 12.0, 2010: 15.0}
    result = classify_extent_change(series, sources=["cgmd-extent30"])
    assert result.change_class == "gain"
    assert result.change_rate_km2_per_yr > 0
    assert result.result_type == "OBSERVED"


def test_shrinking_extent_classified_as_loss():
    series = {2000: 15.0, 2010: 5.0}
    result = classify_extent_change(series)
    assert result.change_class == "loss"
    assert result.change_rate_km2_per_yr < 0


def test_stable_extent_with_low_condition_reclassified_degraded_and_modelled():
    series = {2000: 10.0, 2010: 10.005}
    result = classify_extent_change(series, condition_indicator_latest=0.1)
    assert result.change_class == "degraded_stressed"
    assert result.result_type == "MODELLED"


def test_single_year_series_returns_stable_observed():
    result = classify_extent_change({2020: 10.0})
    assert result.change_class == "stable"
    assert result.result_type == "OBSERVED"


def test_fragmentation_index_solid_block_is_zero():
    solid = np.ones((5, 5))
    assert fragmentation_index(solid) == 0.0


def test_fragmentation_index_checkerboard_is_high():
    checker = np.indices((4, 4)).sum(axis=0) % 2
    result = fragmentation_index(checker)
    assert result > 0.5


def test_fragmentation_index_raises_on_empty_grid():
    with pytest.raises(ValueError):
        fragmentation_index(np.zeros((3, 3)))
