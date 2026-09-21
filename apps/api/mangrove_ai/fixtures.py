"""Synthetic fixture data generators — clearly labeled as SYNTHETIC
everywhere they're used. These exist only because this sandbox has no GEE
credentials and no ingested labeled imagery yet; they let the ML pipeline,
suitability engine, and test suite run end-to-end now, and get swapped for
real materialized Sentinel-2/CGMD/label data the moment credentials and
label files are available (mangrove_ai.pipeline.materialize_composite /
mangrove_ai.labels.ingest are the real, non-fixture code paths).

Every function name is prefixed `synthetic_` and every returned dict/frame
carries a `"is_synthetic": True` marker so no caller can mistake this for
observed data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_RNG = np.random.default_rng(42)


def synthetic_band_pixels(n: int = 2000, mangrove_fraction: float = 0.35) -> pd.DataFrame:
    """n synthetic Sentinel-2-like pixels with plausible reflectance ranges
    for a mixed mangrove / water / bare-soil / built-up coastal scene, and a
    ground-truth `label` column for baseline-model training/testing."""
    n_mangrove = int(n * mangrove_fraction)
    n_other = n - n_mangrove

    def _class(n_pts, blue, green, red, nir, swir1, label):
        return pd.DataFrame({
            "blue": _RNG.normal(blue, 0.015, n_pts).clip(0, 1),
            "green": _RNG.normal(green, 0.015, n_pts).clip(0, 1),
            "red": _RNG.normal(red, 0.015, n_pts).clip(0, 1),
            "nir": _RNG.normal(nir, 0.03, n_pts).clip(0, 1),
            "swir1": _RNG.normal(swir1, 0.02, n_pts).clip(0, 1),
            "label": label,
        })

    mangrove = _class(n_mangrove, 0.04, 0.06, 0.04, 0.38, 0.12, "mangrove")
    n_water = n_other // 3
    n_soil = n_other // 3
    n_built = n_other - n_water - n_soil
    water = _class(n_water, 0.05, 0.06, 0.04, 0.03, 0.02, "non_mangrove")
    soil = _class(n_soil, 0.12, 0.14, 0.16, 0.20, 0.28, "non_mangrove")
    built = _class(n_built, 0.15, 0.16, 0.18, 0.22, 0.30, "non_mangrove")

    df = pd.concat([mangrove, water, soil, built], ignore_index=True)
    df["is_synthetic"] = True
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


def synthetic_extent_timeseries(start_year: int = 1984, end_year: int = 2023, base_km2: float = 45.0) -> pd.DataFrame:
    """A plausible-shaped 1984-2023 gain/loss series for chart/API dev only.
    Never served as if it were CGMD-Extent30 output — callers must check
    `is_synthetic`."""
    years = list(range(start_year, end_year + 1))
    net_extent = base_km2
    rows = []
    for year in years:
        gain = max(0.0, _RNG.normal(0.6, 0.4))
        loss = max(0.0, _RNG.normal(0.5, 0.5)) + (0.3 if year > 2005 else 0.0)
        net_extent = max(0.0, net_extent + gain - loss)
        rows.append({"year": year, "gain_km2": round(gain, 3), "loss_km2": round(loss, 3),
                      "net_km2": round(gain - loss, 3), "total_extent_km2": round(net_extent, 3)})
    df = pd.DataFrame(rows)
    df["is_synthetic"] = True
    return df
