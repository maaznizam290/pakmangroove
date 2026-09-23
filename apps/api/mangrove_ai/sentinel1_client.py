"""Sentinel-1 GRD (SAR) provider — architectural stub.

mangrove_ai.gee_client.GEEClient (Sentinel-2) and this module both conform
to mangrove_ai.imagery_provider.ImageryProvider, so a future caller can hold
either behind the same interface. This class is real (same GEE service-
account auth, real settings.s1_grd_collection id) but its composite/sampling
methods deliberately raise Sentinel1NotImplementedError rather than fabricate
a result: Sentinel-1 SAR backscatter (VV/VH) needs its own speckle-filtering
and mangrove-specific processing chain, and mangrove_ai.indices has no
published SAR formula wired in yet (see mangrove_ai.indices for the
Sentinel-2-only formulas that do exist) — adding one is a separate,
deliberate methodology decision, not something to guess at here.

When that methodology is ready, implement build_annual_composite here the
same way mangrove_ai.gee_client.GEEClient.build_annual_composite does:
    ee.ImageCollection(settings.s1_grd_collection)
        .filterBounds(aoi).filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .select(["VV", "VH"])
    -> speckle filter -> temporal composite
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mangrove_ai.config import settings
from mangrove_ai.gee_client import GEENotConfiguredError


class Sentinel1NotImplementedError(NotImplementedError):
    """Raised by every Sentinel1Client method — real GEE auth exists and
    is_configured reports honestly, but no SAR processing chain is
    implemented yet. Distinct from GEENotConfiguredError (missing
    credentials) so callers can tell "not configured" from "not built"."""


@dataclass
class SarCompositeRequest:
    aoi_geojson: dict
    period_start: date
    period_end: date
    composite_type: str = "annual"  # "annual" | "seasonal" | "monthly"
    polarizations: tuple[str, ...] = ("VV", "VH")


class Sentinel1Client:
    """Conforms to mangrove_ai.imagery_provider.ImageryProvider. Shares
    GEEClient's is_configured check (same service-account credentials
    authenticate every GEE dataset) but every real-work method raises
    Sentinel1NotImplementedError until a SAR processing chain is built."""

    @property
    def is_configured(self) -> bool:
        return bool(settings.gee_service_account_key_path and settings.gee_service_account_email)

    def build_annual_composite(self, request: SarCompositeRequest):
        if not self.is_configured:
            raise GEENotConfiguredError(
                "GEE_SERVICE_ACCOUNT_KEY_PATH / GEE_SERVICE_ACCOUNT_EMAIL are not set."
            )
        raise Sentinel1NotImplementedError(
            f"Sentinel-1 ({settings.s1_grd_collection}) compositing is not implemented — "
            "no validated speckle-filtering/mangrove SAR methodology is wired into "
            "mangrove_ai.indices yet. See mangrove_ai.sentinel1_client module docstring."
        )

    def sample_bands_at_cells(self, composite, cell_points_geojson: list[dict]) -> list[dict]:
        raise Sentinel1NotImplementedError(
            "Sentinel-1 per-cell sampling is not implemented — see build_annual_composite."
        )

    def get_map_layer(self, composite, layer: str) -> dict:
        raise Sentinel1NotImplementedError(
            "Sentinel-1 map-tile visualization is not implemented — see build_annual_composite."
        )


sentinel1_client = Sentinel1Client()
