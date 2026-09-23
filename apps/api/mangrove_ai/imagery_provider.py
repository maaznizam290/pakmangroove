"""The shared contract every satellite imagery provider (Sentinel-2 today;
Sentinel-1/Landsat once a validated methodology exists) implements, so
mangrove_ai.pipeline and mangrove_ai.tools can eventually take a provider as
a parameter instead of importing mangrove_ai.gee_client.gee_client directly.

A typing.Protocol, not an ABC: mangrove_ai.gee_client.GEEClient already
satisfies this structurally and needs no code change or inheritance to
conform — see PEP 544. Deliberately small (no `import ee` here) so this
module stays importable without the earthengine-api dependency.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageryProvider(Protocol):
    """One satellite dataset's real Earth Engine access — filtering,
    compositing, per-cell sampling, and map-tile visualization. Never
    returns fabricated values: an unconfigured or unimplemented provider
    raises rather than silently returning fixture data."""

    @property
    def is_configured(self) -> bool:
        """Whether real credentials are present for this provider."""
        ...

    def build_annual_composite(self, request):
        """Filter -> mask -> composite this provider's imagery for one
        AOI/period. Returns a provider-specific ee.Image."""
        ...

    def sample_bands_at_cells(self, composite, cell_points_geojson: list[dict]) -> list[dict]:
        """Real reduceRegions-style per-cell band sampling of `composite`."""
        ...

    def get_map_layer(self, composite, layer: str) -> dict:
        """A real, credential-free tile URL for one visualization of
        `composite` (see mangrove_ai.gee_client.SUPPORTED_MAP_LAYERS for the
        Sentinel-2 provider's supported layer names — each provider defines
        its own set based on what bands/indices it actually has)."""
        ...
