"""Training-label ingestion: Zenodo Pakistan mangrove dataset (Indus Delta /
Sandspit / MangroveSitesShapefile prioritized per the build spec) and GMW,
loaded into `training_labels` with an enforced spatial train/val/test split
and an explicit weak-label flag.

Real ingestion code, ready to run the moment a shapefile/GeoJSON is
uploaded — nothing here is exercised against fabricated data; there is no
Pakistan mangrove data in this sandbox (zenodo.org is blocked by egress
policy), so running this module today requires a user-supplied file.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import geopandas as gpd
from sqlalchemy import text

from mangrove_ai.db import get_session

TARGET_RESOLUTION_M = 10.0  # Sentinel-2-native — anything coarser than this is a weak label by default


@dataclass
class SplitBands:
    """Spatially separated train/val/test bands by longitude — avoids the
    classic mistake of a random point-level split leaking spatially
    autocorrelated neighbors across train/val. Bands are wide (not a fine
    checkerboard) so a model can't learn local texture on one side of a
    boundary and exploit it on the other."""
    train_max_lon: float
    val_max_lon: float
    # everything above val_max_lon is test

    def assign(self, lon: float) -> tuple[str, str]:
        if lon <= self.train_max_lon:
            return "train", "west_band"
        if lon <= self.val_max_lon:
            return "val", "middle_band"
        return "test", "east_band"


def default_split_bands(gdf: gpd.GeoDataFrame) -> SplitBands:
    minx, _, maxx, _ = gdf.total_bounds
    span = maxx - minx
    return SplitBands(train_max_lon=minx + 0.7 * span, val_max_lon=minx + 0.85 * span)


def ingest_labels(
    gdf: gpd.GeoDataFrame,
    source: str,
    label_class_column: str | None = None,
    default_label_class: str | None = None,
    source_resolution_m: float = 30.0,
    split_bands: SplitBands | None = None,
) -> dict[str, int]:
    if label_class_column is None and default_label_class is None:
        raise ValueError("Provide either label_class_column or default_label_class.")
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    split_bands = split_bands or default_split_bands(gdf)
    is_weak = source_resolution_m > TARGET_RESOLUTION_M
    counts = {"train": 0, "val": 0, "test": 0}

    with get_session() as session:
        for _, row in gdf.iterrows():
            label_class = row[label_class_column] if label_class_column else default_label_class
            centroid = row.geometry.centroid
            split, region = split_bands.assign(centroid.x)
            session.execute(
                text("""INSERT INTO training_labels (geom, label_class, source, source_resolution_m, is_weak_label, spatial_split, split_region)
                         VALUES (ST_SetSRID(ST_GeomFromText(:wkt), 4326), :label_class, :source, :resolution, :is_weak, :split, :region)"""),
                {"wkt": row.geometry.wkt, "label_class": label_class, "source": source,
                 "resolution": source_resolution_m, "is_weak": is_weak, "split": split, "region": region},
            )
            counts[split] += 1

    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a Zenodo/GMW mangrove label file (shapefile/GeoJSON) into training_labels.")
    parser.add_argument("--file", required=True, help="Path to a shapefile (.shp) or GeoJSON")
    parser.add_argument("--source", required=True, help="Manifest id, e.g. zenodo-10.5281-zenodo.10732690")
    parser.add_argument("--label-class-column", default=None)
    parser.add_argument("--default-label-class", default=None, choices=["mangrove", "non_mangrove", "degraded_mangrove", "water", "built_up", "other"])
    parser.add_argument("--resolution-m", type=float, default=30.0)
    args = parser.parse_args()

    gdf = gpd.read_file(args.file)
    result = ingest_labels(gdf, args.source, args.label_class_column, args.default_label_class, args.resolution_m)
    print(f"Ingested {sum(result.values())} labels: {result}")
