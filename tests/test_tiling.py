from __future__ import annotations

import pytest

from gt_osint_ai.redlines import BBox
from gt_osint_ai.tiling import human_bytes, human_duration, plan_tiles


def test_a_100km_box_at_10m_is_a_few_thousand_tiles() -> None:
    # ~92 km x ~111 km, Sentinel-2 resolution, 256 px tiles with 32 px overlap -> 2.24 km stride.
    plan = plan_tiles(BBox(32.0, 33.0, 33.0, 34.0), gsd_m=10.0)
    assert plan.tiles_x == 42
    assert plan.tiles_y == 50
    assert plan.tiles == 2100
    assert plan.pixels == 2100 * 256 * 256
    assert plan.bytes_read == plan.pixels * 4 * 2
    assert plan.embedding_seconds == pytest.approx(105.0)


def test_landsat_resolution_needs_nine_times_fewer_tiles() -> None:
    bbox = BBox(32.0, 33.0, 33.0, 34.0)
    s2 = plan_tiles(bbox, gsd_m=10.0)
    landsat = plan_tiles(bbox, gsd_m=30.0)
    assert landsat.tiles < s2.tiles
    assert s2.tiles / landsat.tiles == pytest.approx(9.0, rel=0.05)


def test_a_tiny_box_is_still_one_tile() -> None:
    plan = plan_tiles(BBox(32.0, 33.0, 32.001, 33.001), gsd_m=10.0)
    assert plan.tiles == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"gsd_m": 0.0}, "gsd_m must be positive"),
        ({"gsd_m": 10.0, "tile_px": 0}, "tile_px must be positive"),
        ({"gsd_m": 10.0, "overlap_px": 256}, "overlap_px"),
        ({"gsd_m": 10.0, "overlap_px": -1}, "overlap_px"),
        ({"gsd_m": 10.0, "bands": 0}, "bands must be positive"),
    ],
)
def test_rejects_nonsense(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        plan_tiles(BBox(32.0, 33.0, 33.0, 34.0), **kwargs)


def test_human_bytes() -> None:
    assert human_bytes(512) == "512 B"
    assert human_bytes(2_500) == "2.5 kB"
    assert human_bytes(3_400_000_000) == "3.4 GB"


def test_human_duration() -> None:
    assert human_duration(30) == "30 s"
    assert human_duration(600) == "10.0 min"
    assert human_duration(7200) == "2.0 h"
