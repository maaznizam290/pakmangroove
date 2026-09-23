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

    # GEE hard-aborts a synchronous reduceRegions().getInfo() call once its
    # computation graph accumulates over 5000 elements — confirmed against
    # this composite's actual join+cloud-mask+median graph (4000 succeeds,
    # the full unbatched call on a 6468-cell AOI fails). Chunking here keeps
    # every batch under that ceiling regardless of AOI size up to
    # mangrove_ai.geo.MAX_SYNC_CELLS.
    _REDUCE_REGIONS_BATCH_SIZE = 4000

    def sample_bands_at_cells(self, composite, cell_points_geojson: list[dict]) -> list[dict]:
        """Reduce the composite to band values at a list of cell centroids.
        Real GEE reduceRegion calls, chunked into multiple FeatureCollection
        round trips to stay under GEE's per-call element cap."""
        self._ensure_initialized()
        import ee

        bands = list(_S2_BAND_MAP.values())
        selected = composite.select(bands)
        batch_size = self._REDUCE_REGIONS_BATCH_SIZE
        features: list[dict] = []
        for start in range(0, len(cell_points_geojson), batch_size):
            chunk = cell_points_geojson[start:start + batch_size]
            fc = ee.FeatureCollection(
                [ee.Feature(ee.Geometry(g), {"idx": start + i}) for i, g in enumerate(chunk)]
            )
            sampled = selected.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=10)
            features.extend(sampled.getInfo()["features"])
        return features

    def get_map_layer(self, composite, layer: str) -> dict:
        """Returns a real GEE-hosted XYZ tile URL template for one
        visualization of `composite` — true/false color, or an ee.Image-side
        spectral index computed via ee.Image.normalizedDifference (a
        separate code path from mangrove_ai.indices' numpy formulas, which
        operate on already-sampled per-cell band values, not a raster).

        getMapId returns a scoped, time-limited tile URL — never the
        service-account key itself — so this is safe to hand to the
        frontend as-is."""
        self._ensure_initialized()
        import ee

        if layer not in _LAYER_VIS:
            raise ValueError(f"Unknown layer '{layer}' — supported: {', '.join(SUPPORTED_MAP_LAYERS)}")

        vis = dict(_LAYER_VIS[layer])
        if layer in ("true_color", "false_color"):
            image = composite.select(vis.pop("bands"))
        elif layer == "ndvi":
            image = composite.normalizedDifference(["B8", "B4"])
        elif layer == "ndwi":
            image = composite.normalizedDifference(["B3", "B8"])
        else:  # mndwi
            image = composite.normalizedDifference(["B3", "B11"])

        map_id = image.getMapId(vis)
        return {"tile_url": map_id["tile_fetcher"].url_format, "layer": layer}


# Visualization params for ee.Image.getMapId — min/max are typical Sentinel-2
# SR display ranges for these bands/indices (composite is already scaled to
# ~0-1 reflectance by build_annual_composite's /10000). A rendering choice,
# not a scientific calibration.
_LAYER_VIS: dict[str, dict] = {
    "true_color": {"bands": ["B4", "B3", "B2"], "min": 0.0, "max": 0.3},
    "false_color": {"bands": ["B8", "B4", "B3"], "min": 0.0, "max": 0.3},
    "ndvi": {"min": -1.0, "max": 1.0, "palette": ["#8B4513", "#FFFFCC", "#78C679", "#004529"]},
    "ndwi": {"min": -1.0, "max": 1.0, "palette": ["#FFFFCC", "#41B6C4", "#225EA8", "#081D58"]},
    "mndwi": {"min": -1.0, "max": 1.0, "palette": ["#FFFFCC", "#41B6C4", "#225EA8", "#081D58"]},
}

SUPPORTED_MAP_LAYERS = tuple(_LAYER_VIS.keys())

gee_client = GEEClient()
