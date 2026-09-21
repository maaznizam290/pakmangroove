import pytest

from mangrove_ai.geo import AOITooLargeError, ensure_grid_cells, resolve_aoi


def test_resolve_aoi_with_explicit_bbox(small_bbox):
    resolved = resolve_aoi(bbox=small_bbox)
    assert resolved["aoi_id"] is None
    assert resolved["bounds"] == small_bbox


def test_resolve_aoi_falls_back_to_seeded_default():
    resolved = resolve_aoi()
    assert resolved["aoi_id"] is not None
    x0, y0, x1, y1 = resolved["bounds"]
    assert x1 > x0 and y1 > y0


def test_ensure_grid_cells_materializes_and_is_idempotent(small_cells):
    assert len(small_cells) > 0
    from mangrove_ai.geo import ensure_grid_cells as ensure_again

    second_call = ensure_again((67.10, 24.78, 67.101, 24.781))
    assert len(second_call) == len(small_cells)  # no duplicate cells created
    assert {c["cell_id"] for c in second_call} == {c["cell_id"] for c in small_cells}


def test_oversized_aoi_raises_before_touching_db():
    with pytest.raises(AOITooLargeError):
        ensure_grid_cells((66.85, 24.65, 67.45, 24.95))  # the full original Karachi coast bbox, ~2M cells
