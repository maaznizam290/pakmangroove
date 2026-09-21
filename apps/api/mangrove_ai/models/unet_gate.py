"""UNet++ deep-learning segmentation is intentionally NOT implemented yet.

Per the build strategy: "The MVP should prioritize a working validated
model over architectural complexity" and UNet++ is to be built "only if
the available labeled image tiles justify deep learning."

This module is the explicit gate check other code (and Hermes) calls
before any deep-learning training path is allowed to run.
"""

from __future__ import annotations

MIN_LABELED_TILES_FOR_UNET = 500  # a floor, not a guarantee of sufficiency — revisit with real class balance/tile stats


def unet_training_justified(n_labeled_tiles: int, n_classes_represented: int) -> tuple[bool, str]:
    if n_labeled_tiles < MIN_LABELED_TILES_FOR_UNET:
        return False, (
            f"Only {n_labeled_tiles} labeled image tiles available (< {MIN_LABELED_TILES_FOR_UNET}). "
            "Continue with the Random Forest / Gradient Boosting baseline "
            "(mangrove_ai.models.baseline) until real labeled Sentinel-2 "
            "tiles from the ingested Zenodo/GMW/CGMD sources justify the jump."
        )
    if n_classes_represented < 2:
        return False, "Fewer than 2 classes represented in labeled tiles — insufficient for segmentation training."
    return True, "Labeled tile volume and class coverage justify evaluating a UNet++ baseline against the RF/GBM model."
