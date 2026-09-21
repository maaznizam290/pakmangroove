"""Canopy condition indicator — deliberately NOT called "ecosystem health".

Per the build spec: "Do not call NDVI alone 'ecosystem health'." This
combines multiple independent Sentinel-2-derived indices into a single
interpretable indicator and labels it precisely as a
REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR — a proxy, not a
verified ecological-health measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

INDICATOR_LABEL = "REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR"

# Weights are a documented, simple, equal-ish blend of vegetation vigor
# (NDVI, EVI) and moisture (NDMI) — not a fitted/calibrated model. Revisit
# once real field-validated health outcomes exist to fit against.
_WEIGHTS = {"NDVI": 0.4, "EVI": 0.35, "NDMI": 0.25}

STRESS_THRESHOLD = 0.35  # condition_indicator below this -> stress_flag True


@dataclass
class ConditionResult:
    condition_indicator: float
    contributing_indices: dict[str, float]
    stress_flag: bool
    label: str = INDICATOR_LABEL


def canopy_condition_indicator(indices: dict[str, float]) -> ConditionResult:
    """indices: dict with at least NDVI, EVI, NDMI keys (values in roughly
    [-1, 1] range from mangrove_ai.indices). Missing indices are dropped
    from the weighted blend and weights are renormalized over what's
    present, rather than assuming a value."""
    present = {k: v for k, v in _WEIGHTS.items() if k in indices}
    if not present:
        raise ValueError("At least one of NDVI/EVI/NDMI is required to compute a condition indicator.")

    weight_sum = sum(present.values())
    # indices are roughly in [-1, 1]; rescale contribution to [0, 1] before blending
    score = sum((indices[k] + 1) / 2 * (w / weight_sum) for k, w in present.items())

    contributing = {k: float(indices[k]) for k in present}
    return ConditionResult(
        condition_indicator=round(float(score), 4),
        contributing_indices=contributing,
        stress_flag=score < STRESS_THRESHOLD,
    )
