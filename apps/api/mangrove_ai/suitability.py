"""Restoration Suitability Model — the central intelligence feature.

This module answers "where might restoration be suitable", never "where
mangroves should definitely be planted." Every output is a candidate score
with reasons, confidence, and data sources — see REASON_CODES and
CLASSIFICATION_THRESHOLDS below, and FIELD_VALIDATION_LABEL, which is
attached to every HIGH/VERY_HIGH result and enforced again at the database
layer (db/migrations/006_suitability_and_risk.sql, chk_field_validation_label).

The model combines up to ~20 candidate features (see SuitabilityFeatures).
Any feature not available for a given cell is simply omitted from the
score and from `data_sources` — never defaulted to a guessed value — and
lowers `confidence` via data completeness.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

FIELD_VALIDATION_LABEL = "Candidate restoration area — field validation required."

REASON_CODES = {
    "HISTORICAL_MANGROVE",
    "INTERTIDAL_PROXIMITY",
    "VEGETATION_SIGNAL",
    "WATER_SIGNAL",
    "HIGH_CURRENT_STRESS",
    "NEAR_EXISTING_MANGROVE",
    "BUILT_UP_EXCLUSION",
    "ROAD_INFRASTRUCTURE_EXCLUSION",
    "HISTORICAL_MANGROVE_LOSS",
    "FRAGMENTED_AREA",
    "LOW_CONFIDENCE",
}

CLASSIFICATION_THRESHOLDS = (
    ("VERY_HIGH", 0.85),
    ("HIGH", 0.65),
    ("MEDIUM", 0.40),
    ("LOW", 0.15),
)

# weight per positively-scored continuous feature; features not present in
# a given cell's SuitabilityFeatures are dropped and the remaining weights
# renormalized (see _weighted_score).
_FEATURE_WEIGHTS = {
    "current_mangrove_probability": 0.9,   # if already classified mangrove, restoration isn't the right frame — handled as a cap below
    "historical_mangrove_presence": 1.0,
    "mangrove_proximity_score": 0.8,       # precomputed 0..1, 1 = adjacent to existing mangrove
    "ndvi": 0.4,
    "evi": 0.3,
    "ndmi": 0.3,
    "ndwi": 0.2,
    "mndwi": 0.2,
    "intertidal_proxy_score": 0.9,         # 0..1, derived from persistent water/inundation-frequency signal
    "elevation_suitability_score": 0.3,    # 0..1, optional
    "coastline_proximity_score": 0.5,      # 0..1, 1 = very close
    "channel_proximity_score": 0.4,        # 0..1
}

_PENALTY_WEIGHTS = {
    "current_stress_score": 0.4,           # 0..1, 1 = highly stressed nearby canopy (health.STRESS_THRESHOLD-derived)
    "fragmentation_score": 0.2,            # 0..1
}

_HARD_EXCLUSION_FIELDS = ("built_up_exclusion", "road_infrastructure_exclusion", "open_water_exclusion")


@dataclass
class SuitabilityFeatures:
    # --- positively-weighted continuous features (0..1 where applicable) ---
    current_mangrove_probability: float | None = None
    historical_mangrove_presence: bool | None = None
    mangrove_proximity_score: float | None = None
    ndvi: float | None = None
    evi: float | None = None
    ndmi: float | None = None
    ndwi: float | None = None
    mndwi: float | None = None
    salinity_proxy: float | None = None       # SI — informational only, not weighted into the score (see module docstring)
    intertidal_proxy_score: float | None = None
    elevation_suitability_score: float | None = None
    coastline_proximity_score: float | None = None
    channel_proximity_score: float | None = None

    # --- penalties ---
    current_stress_score: float | None = None
    fragmentation_score: float | None = None
    historical_mangrove_loss: bool | None = None

    # --- hard exclusions ---
    built_up_exclusion: bool | None = None
    road_infrastructure_exclusion: bool | None = None
    open_water_exclusion: bool | None = None

    # --- prediction confidence input ---
    model_predict_confidence: float | None = None  # e.g. distance from 0.5 in RF predict_proba

    # provenance
    data_sources: tuple[str, ...] = ()


@dataclass
class SuitabilityResult:
    suitability_score: float
    confidence: float
    classification: str
    reason_codes: list[str]
    data_sources: list[str]
    field_validation_label: str = FIELD_VALIDATION_LABEL


def _weighted_score(features: SuitabilityFeatures) -> tuple[float, int, int]:
    values = {}
    for name, weight in _FEATURE_WEIGHTS.items():
        v = getattr(features, name)
        if v is None:
            continue
        v = float(v) if not isinstance(v, bool) else (1.0 if v else 0.0)
        values[name] = (v, weight)

    total_available = len(_FEATURE_WEIGHTS)
    total_present = len(values)
    if not values:
        return 0.0, total_present, total_available

    weight_sum = sum(w for _, w in values.values())
    raw = sum(v * w for v, w in values.values()) / weight_sum

    penalty = 0.0
    penalty_weight_sum = 0.0
    for name, weight in _PENALTY_WEIGHTS.items():
        v = getattr(features, name)
        if v is None:
            continue
        penalty += float(v) * weight
        penalty_weight_sum += weight
    if penalty_weight_sum > 0:
        penalty = penalty / penalty_weight_sum

    score = max(0.0, min(1.0, raw - 0.3 * penalty))

    # A cell already classified as current mangrove isn't a *restoration*
    # candidate — cap its score rather than reward it.
    if features.current_mangrove_probability is not None and features.current_mangrove_probability > 0.7:
        score = min(score, 0.2)

    return score, total_present, total_available


def _reason_codes(features: SuitabilityFeatures, score: float) -> list[str]:
    codes: list[str] = []
    if features.historical_mangrove_presence:
        codes.append("HISTORICAL_MANGROVE")
    if (features.intertidal_proxy_score or 0) >= 0.5:
        codes.append("INTERTIDAL_PROXIMITY")
    if any((getattr(features, f) or 0) >= 0.4 for f in ("ndvi", "evi", "ndmi")):
        codes.append("VEGETATION_SIGNAL")
    if any((getattr(features, f) or 0) >= 0.3 for f in ("ndwi", "mndwi")):
        codes.append("WATER_SIGNAL")
    if (features.current_stress_score or 0) >= 0.6:
        codes.append("HIGH_CURRENT_STRESS")
    if (features.mangrove_proximity_score or 0) >= 0.6:
        codes.append("NEAR_EXISTING_MANGROVE")
    if features.built_up_exclusion:
        codes.append("BUILT_UP_EXCLUSION")
    if features.road_infrastructure_exclusion:
        codes.append("ROAD_INFRASTRUCTURE_EXCLUSION")
    if features.historical_mangrove_loss:
        codes.append("HISTORICAL_MANGROVE_LOSS")
    if (features.fragmentation_score or 0) >= 0.5:
        codes.append("FRAGMENTED_AREA")
    return codes


def _classify(score: float, excluded: bool) -> str:
    if excluded:
        return "EXCLUDED"
    for label, threshold in CLASSIFICATION_THRESHOLDS:
        if score >= threshold:
            return label
    return "EXCLUDED"


def compute_suitability(features: SuitabilityFeatures) -> SuitabilityResult:
    excluded = any(getattr(features, f) for f in _HARD_EXCLUSION_FIELDS)
    score, n_present, n_total = _weighted_score(features)
    classification = _classify(score, excluded)

    data_completeness = n_present / n_total if n_total else 0.0
    model_conf = features.model_predict_confidence if features.model_predict_confidence is not None else data_completeness
    confidence = round(0.5 * data_completeness + 0.5 * model_conf, 4)

    reason_codes = _reason_codes(features, score)
    if confidence < 0.4:
        reason_codes.append("LOW_CONFIDENCE")

    return SuitabilityResult(
        suitability_score=round(score, 4) if not excluded else 0.0,
        confidence=confidence,
        classification=classification,
        reason_codes=reason_codes,
        data_sources=list(features.data_sources),
    )
