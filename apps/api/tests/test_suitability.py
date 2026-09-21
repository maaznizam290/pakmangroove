from mangrove_ai.suitability import FIELD_VALIDATION_LABEL, SuitabilityFeatures, compute_suitability


def test_strong_candidate_scores_high_with_expected_reasons():
    features = SuitabilityFeatures(
        historical_mangrove_presence=True,
        mangrove_proximity_score=0.9,
        ndvi=0.5, evi=0.4, ndmi=0.35,
        intertidal_proxy_score=0.8,
        coastline_proximity_score=0.9,
        current_stress_score=0.1,
        model_predict_confidence=0.8,
        data_sources=("cgmd-extent30", "gmw", "sentinel2"),
    )
    result = compute_suitability(features)
    assert result.classification in ("HIGH", "VERY_HIGH")
    assert "HISTORICAL_MANGROVE" in result.reason_codes
    assert "NEAR_EXISTING_MANGROVE" in result.reason_codes
    assert result.field_validation_label == FIELD_VALIDATION_LABEL


def test_built_up_is_hard_excluded_regardless_of_other_signals():
    features = SuitabilityFeatures(built_up_exclusion=True, ndvi=0.9, historical_mangrove_presence=True)
    result = compute_suitability(features)
    assert result.classification == "EXCLUDED"
    assert result.suitability_score == 0.0
    assert "BUILT_UP_EXCLUSION" in result.reason_codes


def test_road_infrastructure_is_hard_excluded():
    features = SuitabilityFeatures(road_infrastructure_exclusion=True, ndvi=0.9)
    result = compute_suitability(features)
    assert result.classification == "EXCLUDED"


def test_empty_feature_set_yields_low_confidence_and_excluded():
    result = compute_suitability(SuitabilityFeatures())
    assert result.classification == "EXCLUDED"
    assert "LOW_CONFIDENCE" in result.reason_codes
    assert result.confidence < 0.4


def test_sparse_data_flags_low_confidence_even_if_not_excluded():
    result = compute_suitability(SuitabilityFeatures(ndvi=0.3))
    assert "LOW_CONFIDENCE" in result.reason_codes


def test_current_mangrove_cell_is_capped_not_rewarded():
    # A cell that IS already mangrove isn't a restoration *candidate* —
    # the scoring engine should cap rather than boost it.
    as_new_candidate = SuitabilityFeatures(
        historical_mangrove_presence=True, ndvi=0.6, evi=0.5, ndmi=0.4,
        intertidal_proxy_score=0.8, mangrove_proximity_score=0.9,
    )
    as_existing_mangrove = SuitabilityFeatures(
        current_mangrove_probability=0.95,
        historical_mangrove_presence=True, ndvi=0.6, evi=0.5, ndmi=0.4,
        intertidal_proxy_score=0.8, mangrove_proximity_score=0.9,
    )
    result_new = compute_suitability(as_new_candidate)
    result_existing = compute_suitability(as_existing_mangrove)
    assert result_existing.suitability_score <= 0.2
    assert result_existing.suitability_score < result_new.suitability_score


def test_every_reason_code_is_a_recognized_code():
    from mangrove_ai.suitability import REASON_CODES

    features = SuitabilityFeatures(
        historical_mangrove_presence=True, mangrove_proximity_score=0.9,
        ndvi=0.5, evi=0.4, ndmi=0.4, ndwi=0.4, mndwi=0.4,
        intertidal_proxy_score=0.9, current_stress_score=0.9,
        built_up_exclusion=False, road_infrastructure_exclusion=False,
        historical_mangrove_loss=True, fragmentation_score=0.9,
    )
    result = compute_suitability(features)
    assert set(result.reason_codes) <= REASON_CODES
