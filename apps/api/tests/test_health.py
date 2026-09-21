import pytest

from mangrove_ai.health import INDICATOR_LABEL, STRESS_THRESHOLD, canopy_condition_indicator


def test_label_is_not_ecosystem_health():
    assert "HEALTH" not in INDICATOR_LABEL.upper() or "CONDITION INDICATOR" in INDICATOR_LABEL
    assert INDICATOR_LABEL == "REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR"


def test_high_indices_yield_high_indicator_no_stress():
    result = canopy_condition_indicator({"NDVI": 0.8, "EVI": 0.6, "NDMI": 0.5})
    assert result.condition_indicator > STRESS_THRESHOLD
    assert result.stress_flag is False


def test_low_indices_flag_stress():
    result = canopy_condition_indicator({"NDVI": -0.5, "EVI": -0.3, "NDMI": -0.4})
    assert result.stress_flag is True


def test_missing_indices_still_computes_from_whats_present():
    result = canopy_condition_indicator({"NDVI": 0.5})
    assert result.contributing_indices == {"NDVI": 0.5}


def test_raises_without_any_supported_index():
    with pytest.raises(ValueError):
        canopy_condition_indicator({"BSI": 0.2})
