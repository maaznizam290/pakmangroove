"""Spectral index formulas over Sentinel-2 surface reflectance bands.

These are standard, published remote-sensing formulas — not fitted or
invented — applied to whatever band arrays are passed in. Each function is
a pure function over numpy arrays so it works identically on a single
in-memory tile, a GEE-side `ee.Image.expression`, or a unit test fixture.

Band naming follows Sentinel-2 L2A: B2=Blue, B3=Green, B4=Red, B8=NIR,
B8A=NIR-narrow, B11=SWIR1, B12=SWIR2. All formulas assume reflectance
values (not raw DN) as float arrays.

None of these indices is, by itself, "mangrove health" or "salinity" or
"soil moisture" in an absolute/calibrated sense — see
docs/architecture note in mangrove_ai.health for how they're combined and
labeled as a "REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR"
rather than an ecosystem-health claim, and SI is documented below as a
spectral *proxy*, never a calibrated salinity value.
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-9


def _safe_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return numerator / np.where(np.abs(denominator) < _EPS, _EPS, denominator)


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index (Rouse et al. 1974)."""
    return _safe_ratio(nir - red, nir + red)


def evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Enhanced Vegetation Index (Huete et al. 2002)."""
    return 2.5 * _safe_ratio(nir - red, nir + 6 * red - 7.5 * blue + 1)


def msavi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Modified Soil-Adjusted Vegetation Index (Qi et al. 1994)."""
    inner = (2 * nir + 1) ** 2 - 8 * (nir - red)
    return (2 * nir + 1 - np.sqrt(np.clip(inner, 0, None))) / 2


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """McFeeters (1996) Normalized Difference Water Index."""
    return _safe_ratio(green - nir, green + nir)


def mndwi(green: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    """Xu (2006) Modified Normalized Difference Water Index."""
    return _safe_ratio(green - swir1, green + swir1)


def ndmi(nir: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    """Normalized Difference Moisture Index (Gao 1996)."""
    return _safe_ratio(nir - swir1, nir + swir1)


def mvi(nir: np.ndarray, green: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    """Mangrove Vegetation Index (Baloloy et al. 2020): (NIR-Green)/(SWIR1-Green).
    Cross-check against the ingested arXiv 2411.11918 / Frontiers methodology
    papers once available (see data/knowledge_base/SOURCES_MANIFEST.yaml)."""
    return _safe_ratio(nir - green, swir1 - green)


def si(green: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Salinity Index spectral proxy: sqrt(Green * Red).
    This is a spectral proxy only — never treat its output as a calibrated
    salinity value (ppt/EC); the build spec explicitly forbids inventing
    spatialized salinity. Use only as a relative, unitless input feature."""
    product = np.clip(green * red, 0, None)
    return np.sqrt(product)


def bsi(swir1: np.ndarray, red: np.ndarray, nir: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Bare Soil Index (Rikimaru et al. 2002)."""
    return _safe_ratio((swir1 + red) - (nir + blue), (swir1 + red) + (nir + blue))


INDEX_REGISTRY: dict[str, tuple[str, ...]] = {
    "NDVI": ("nir", "red"),
    "EVI": ("nir", "red", "blue"),
    "MSAVI": ("nir", "red"),
    "NDWI": ("green", "nir"),
    "MNDWI": ("green", "swir1"),
    "NDMI": ("nir", "swir1"),
    "MVI": ("nir", "green", "swir1"),
    "SI": ("green", "red"),
    "BSI": ("swir1", "red", "nir", "blue"),
}

_FUNCS = {"NDVI": ndvi, "EVI": evi, "MSAVI": msavi, "NDWI": ndwi, "MNDWI": mndwi,
          "NDMI": ndmi, "MVI": mvi, "SI": si, "BSI": bsi}


def compute_all_indices(bands: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Compute every index in INDEX_REGISTRY whose required bands are present
    in `bands`. Indices whose bands are missing are silently skipped (not
    zero-filled) so callers can tell "not computed" from "computed as 0"."""
    results: dict[str, np.ndarray] = {}
    for name, required in INDEX_REGISTRY.items():
        if all(b in bands for b in required):
            results[name] = _FUNCS[name](*(bands[b] for b in required))
    return results
