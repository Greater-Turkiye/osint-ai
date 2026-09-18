"""How much work a scene would be, in tiles, pixels and free-tier budget.

The arithmetic here is the whole answer to "we will scan millions of images". We never scan
millions of images; we scan a bounded number of *tiles* per pass, and this module is what
makes that number visible before anything is run. Every figure it prints is an estimate from
geometry, clearly labelled as such — nothing here measures a real run, because there has not
been one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from gt_osint_ai.redlines import BBox

DEFAULT_TILE_PX = 256  # Clay v1.5 embeds 256x256 tiles; keep the default aligned with it
DEFAULT_OVERLAP_PX = 32  # so a feature on a tile edge is whole in the neighbouring tile
BYTES_PER_SAMPLE = 2  # Sentinel-2 L2A reflectance is uint16

#: Rough embedding throughput, tiles per second, measured by others and not by us.
#: Clay's own note for v1.5 is ~20 embeddings/s; free Colab/Kaggle hardware varies, so this
#: is a planning figure with an order-of-magnitude of confidence, not a benchmark.
ASSUMED_TILES_PER_SECOND = 20.0


@dataclass(frozen=True, slots=True)
class TilePlan:
    """What one scene-sized area of interest would be cut into. Estimates only."""

    tile_px: int
    overlap_px: int
    gsd_m: float
    bands: int
    width_km: float
    height_km: float
    tiles_x: int
    tiles_y: int

    @property
    def tiles(self) -> int:
        return self.tiles_x * self.tiles_y

    @property
    def pixels(self) -> int:
        return self.tiles * self.tile_px * self.tile_px

    @property
    def bytes_read(self) -> int:
        """Bytes that *would* be read from the open catalogue. We store none of them."""
        return self.pixels * self.bands * BYTES_PER_SAMPLE

    @property
    def embedding_seconds(self) -> float:
        return self.tiles / ASSUMED_TILES_PER_SECOND


def plan_tiles(
    bbox: BBox,
    *,
    gsd_m: float,
    tile_px: int = DEFAULT_TILE_PX,
    overlap_px: int = DEFAULT_OVERLAP_PX,
    bands: int = 4,
) -> TilePlan:
    """Cut ``bbox`` into overlapping square tiles at ``gsd_m`` metres per pixel."""
    if gsd_m <= 0:
        raise ValueError("gsd_m must be positive")
    if tile_px <= 0:
        raise ValueError("tile_px must be positive")
    if not 0 <= overlap_px < tile_px:
        raise ValueError("overlap_px must be at least 0 and smaller than tile_px")
    if bands <= 0:
        raise ValueError("bands must be positive")

    stride_m = (tile_px - overlap_px) * gsd_m
    width_km = abs(bbox.width_km())
    height_km = bbox.height_km()
    tiles_x = max(1, math.ceil(width_km * 1000.0 / stride_m))
    tiles_y = max(1, math.ceil(height_km * 1000.0 / stride_m))
    return TilePlan(
        tile_px=tile_px,
        overlap_px=overlap_px,
        gsd_m=gsd_m,
        bands=bands,
        width_km=width_km,
        height_km=height_km,
        tiles_x=tiles_x,
        tiles_y=tiles_y,
    )


def human_bytes(n: int) -> str:
    """A short, honest size string. Deliberately decimal (GB, not GiB)."""
    units = ("B", "kB", "MB", "GB", "TB", "PB")
    value = float(n)
    for unit in units:
        if value < 1000.0 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1000.0
    raise AssertionError("unreachable")  # pragma: no cover


def human_duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 90 * 60:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"
