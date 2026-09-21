"""Google Earth Engine client: Sentinel-2 SR + cloud-probability pipeline.

Real `earthengine-api` calls, gated on credentials being configured. With
no service-account key present (mangrove_ai.config.settings), every method
raises GEENotConfiguredError instead of silently returning fabricated
numbers — per the explicit build decision, this sandbox has no GEE
credentials, so live calls are not attempted here; the code path is real
and ready for a key to be dropped into .env.

Pipeline, per the build spec:
    AOI -> image filtering -> cloud masking -> cloud probability masking
    -> seasonal/annual compositing -> spectral bands -> spectral indices
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mangrove_ai.config import settings

_S2_BAND_MAP = {
    "blue": "B2", "green": "B3", "red": "B4",
    "nir": "B8", "nir_narrow": "B8A", "swir1": "B11", "swir2": "B12",
}


class GEENotConfiguredError(RuntimeError):
    """Raised when a live Earth Engine call is attempted without credentials."""


@dataclass
class CompositeRequest:
    aoi_geojson: dict
    period_start: date
    period_end: date
    composite_type: str = "annual"  # "annual" | "seasonal" | "monthly"
    cloud_prob_max: float = settings.s2_cloud_prob_max


class GEEClient:
    def __init__(self) -> None:
        self._initialized = False

    @property
    def is_configured(self) -> bool:
        return bool(settings.gee_service_account_key_path and settings.gee_service_account_email)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        if not self.is_configured:
            raise GEENotConfiguredError(
                "GEE_SERVICE_ACCOUNT_KEY_PATH / GEE_SERVICE_ACCOUNT_EMAIL are not set. "
                "No live Earth Engine call was made — this is not a fabricated result."
            )
        import ee  # local import: keep earthengine-api optional at module load time

        credentials = ee.ServiceAccountCredentials(
            settings.gee_service_account_email, settings.gee_service_account_key_path
        )
        ee.Initialize(credentials, project=settings.gee_project)
        self._initialized = True

    def build_annual_composite(self, request: CompositeRequest):
        """Filter -> cloud-mask -> composite COPERNICUS/S2_SR_HARMONIZED for
        one AOI/period, using COPERNICUS/S2_CLOUD_PROBABILITY. Returns an
        ee.Image; callers reduce it to per-cell band means (see
        mangrove_ai.pipeline.materialize_composite) rather than exporting
        full rasters, keeping this MVP grid-cell-scoped."""
        self._ensure_initialized()
        import ee

        aoi = ee.Geometry(request.aoi_geojson)
        s2 = (
            ee.ImageCollection(settings.s2_sr_collection)
            .filterBounds(aoi)
            .filterDate(str(request.period_start), str(request.period_end))
        )
        cloud_prob = (
            ee.ImageCollection(settings.s2_cloud_prob_collection)
            .filterBounds(aoi)
            .filterDate(str(request.period_start), str(request.period_end))
        )

        joined = ee.Join.saveFirst("cloud_probability").apply(
            primary=s2,
            secondary=cloud_prob,
            condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
        )

        def _mask(img):
            img = ee.Image(img)
            prob = ee.Image(img.get("cloud_probability")).select("probability")
            clear = prob.lt(request.cloud_prob_max)
            return img.updateMask(clear).divide(10000)  # SR scale factor

        masked = ee.ImageCollection(joined).map(_mask)
        return masked.median().clip(aoi)

    def sample_bands_at_cells(self, composite, cell_points_geojson: list[dict]) -> list[dict]:
        """Reduce the composite to band values at a list of cell centroids.
        Real GEE reduceRegion calls, one FeatureCollection round trip."""
        self._ensure_initialized()
        import ee

        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(g), {"idx": i}) for i, g in enumerate(cell_points_geojson)])
        bands = list(_S2_BAND_MAP.values())
        sampled = composite.select(bands).reduceRegions(
            collection=fc, reducer=ee.Reducer.mean(), scale=10
        )
        return sampled.getInfo()["features"]


gee_client = GEEClient()
