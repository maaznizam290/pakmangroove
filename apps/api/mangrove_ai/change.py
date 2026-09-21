"""Change detection: combines Zenodo Pakistan / GMW / CGMD / Sentinel-2
derived signals into gain/loss/stable/degraded_stressed classification,
change rate, and a fragmentation metric — every result tagged OBSERVED,
DERIVED, or MODELLED per the build spec so nothing downstream conflates a
raw dataset value with a model output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

ResultType = str  # "OBSERVED" | "DERIVED" | "MODELLED"


@dataclass
class ChangeResult:
    change_class: str
    change_rate_km2_per_yr: float | None
    fragmentation_index: float | None
    sources: list[str]
    result_type: ResultType


def classify_extent_change(
    extent_by_year: dict[int, float],
    condition_indicator_latest: float | None = None,
    sources: list[str] | None = None,
) -> ChangeResult:
    """extent_by_year: {year: total_extent_km2, ...} — OBSERVED/DERIVED time
    series (e.g. from cgmd_extent_annual or extent_timeseries_cache).
    condition_indicator_latest: if provided, a low value alongside stable-
    or-declining extent reclassifies the cell as degraded_stressed rather
    than merely 'stable' — this is where MODELLED enters."""
    sources = sources or []
    years = sorted(extent_by_year)
    if len(years) < 2:
        return ChangeResult("stable", None, None, sources, "OBSERVED")

    first_year, last_year = years[0], years[-1]
    delta = extent_by_year[last_year] - extent_by_year[first_year]
    span = last_year - first_year
    rate = delta / span if span > 0 else 0.0

    if abs(rate) < 0.01:
        change_class = "stable"
        result_type: ResultType = "OBSERVED"
    elif rate > 0:
        change_class = "gain"
        result_type = "OBSERVED"
    else:
        change_class = "loss"
        result_type = "OBSERVED"

    if change_class == "stable" and condition_indicator_latest is not None:
        from mangrove_ai.health import STRESS_THRESHOLD

        if condition_indicator_latest < STRESS_THRESHOLD:
            change_class = "degraded_stressed"
            result_type = "MODELLED"  # combines an observed extent series with a derived condition indicator

    return ChangeResult(
        change_class=change_class,
        change_rate_km2_per_yr=round(float(rate), 4),
        fragmentation_index=None,
        sources=sources,
        result_type=result_type,
    )


def fragmentation_index(binary_presence_grid: np.ndarray) -> float:
    """Edge-density fragmentation metric over a 2D binary (0/1) mangrove-
    presence raster/grid: fraction of mangrove-cell boundary edges that
    touch a non-mangrove cell. 0 = fully solid patch, 1 = maximally
    fragmented (checkerboard). DERIVED — requires actual spatial adjacency
    data; returns None-equivalent (raises) if the grid has no mangrove
    cells at all, rather than a misleading 0."""
    grid = np.asarray(binary_presence_grid).astype(int)
    if grid.sum() == 0:
        raise ValueError("No mangrove-presence cells in grid; fragmentation index is undefined, not zero.")

    mangrove_mask = grid == 1
    total_edges = 0
    boundary_edges = 0
    rows, cols = grid.shape
    for r in range(rows):
        for c in range(cols):
            if not mangrove_mask[r, c]:
                continue
            for dr, dc in ((0, 1), (1, 0)):
                nr, nc = r + dr, c + dc
                if nr < rows and nc < cols:
                    total_edges += 1
                    if grid[nr, nc] == 0:
                        boundary_edges += 1
    return round(boundary_edges / total_edges, 4) if total_edges else 0.0
