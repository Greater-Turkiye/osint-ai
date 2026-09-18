"""The imagery red line: no tile of Türkiye is ever searched, downloaded, tiled or scored.

Handbook ``tr/02-red-lines.md`` §1 forbids collecting, analysing or publishing the positions
and movements of Turkish forces. For text signals the collectors enforce this with a per-point
geofence. Imagery is different in one way that matters: a satellite scene is an *area*, so a
per-point test is not enough — an area of interest either overlaps Türkiye or it does not, and
if it does, the safe answer is to refuse the whole request rather than to crop it.

So this module is a gate, not a filter. It runs before the first network call in
:mod:`gt_osint_ai.cli`, and a refusal is an error exit, not a warning.

Two deliberate choices make it conservative:

* **A wider buffer than the collectors use.** The collectors' fence is
  ``land + internal waters + 12 nm`` (the territorial sea). Here the buffer is
  :data:`IMAGERY_BUFFER_NM` = 15 nm: the 12 nm territorial sea plus a 3 nm (≈5.6 km) standoff,
  which covers a tile's own 2.56 km extent with room to spare and absorbs the fact that the
  vendored 1:50m coastline omits small islands (``data/tr_geofence.json``,
  ``provenance.land.note``). With the file's recorded margins the effective radius is ≈30.6 km.

  This has a real cost and it is not hidden: at 15 nm the gate also refuses Idlib, Latakia and
  the Greek islands that lie close to the Turkish coast, all of which are legitimately in the
  mission's scope. Losing them is the price of a rule that cannot be argued with case by case.
  An area that must cover such a place does not get a flag — it gets a maintainer and a new
  handbook ADR.
* **Sampling plus a vertex test.** An axis-aligned box and a polygon can intersect without any
  of the box's corners being inside, so the box is sampled on a grid of at most
  :data:`SAMPLE_STEP_KM` and, separately, every fence vertex is tested for falling inside the
  box. Either kind of hit refuses. This is an approximation and it errs towards refusing:
  the fenced band is ~30 km thick, far wider than the 5 km sampling step, so a fenced area
  cannot slip between samples.

What this module does **not** claim to do: it does not decide whether an image contains
Turkish forces, and nothing in this repository ever will. The rule is structural — we do not
hold imagery of Türkiye at all, so we cannot produce that analysis by accident.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

from gt_osint_ai.geo import KM_PER_DEG_LAT, KM_PER_DEG_LON_EQUATOR, Geofence, load_geofence_data

IMAGERY_BUFFER_NM = 15.0
SAMPLE_STEP_KM = 5.0
MAX_SAMPLES_PER_AXIS = 400  # a guard: a hemisphere-wide box must not sample forever

REFUSAL_TR = (
    "KIRMIZI ÇİZGİ: bu alan Türkiye coğrafi çitine giriyor; görüntü analizi yapılmaz. "
    "Alanı Türkiye kıyısından/sınırından en az {buffer:.0f} deniz mili uzakta yeniden tanımlayın."
)
REFUSAL_EN = (
    "RED LINE: this area of interest enters the Türkiye geofence; no imagery analysis is run. "
    "Redefine the area at least {buffer:.0f} nautical miles clear of Türkiye's coast and borders."
)


@dataclass(frozen=True, slots=True)
class BBox:
    """A geographic bounding box in degrees, ``west, south, east, north``."""

    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        for name, value in (
            ("west", self.west),
            ("south", self.south),
            ("east", self.east),
            ("north", self.north),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if not -180.0 <= self.west <= 180.0 or not -180.0 <= self.east <= 180.0:
            raise ValueError("longitudes must be within [-180, 180]")
        if not -90.0 <= self.south <= 90.0 or not -90.0 <= self.north <= 90.0:
            raise ValueError("latitudes must be within [-90, 90]")
        if self.east <= self.west:
            raise ValueError("east must be greater than west (boxes crossing 180° are not supported)")
        if self.north <= self.south:
            raise ValueError("north must be greater than south")

    @classmethod
    def parse(cls, text: str) -> BBox:
        """Parse ``"west,south,east,north"``, the order the STAC API and GeoJSON both use."""
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 4:
            raise ValueError("a bbox is four comma-separated numbers: west,south,east,north")
        try:
            west, south, east, north = (float(p) for p in parts)
        except ValueError as exc:
            raise ValueError("a bbox is four comma-separated numbers: west,south,east,north") from exc
        return cls(west, south, east, north)

    def as_list(self) -> list[float]:
        return [self.west, self.south, self.east, self.north]

    def width_km(self) -> float:
        mid_lat = (self.south + self.north) / 2.0
        return (self.east - self.west) * KM_PER_DEG_LON_EQUATOR * math.cos(math.radians(mid_lat))

    def height_km(self) -> float:
        return (self.north - self.south) * KM_PER_DEG_LAT

    def contains_point(self, lat: float, lon: float) -> bool:
        return self.west <= lon <= self.east and self.south <= lat <= self.north

    def __str__(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"


CLEAR_TR = "Alan Türkiye coğrafi çitinin dışında."
CLEAR_EN = "Area is clear of the Türkiye geofence."


@dataclass(frozen=True, slots=True)
class Verdict:
    """The outcome of the gate. ``allowed`` is the only thing callers may branch on."""

    allowed: bool
    reason_tr: str
    reason_en: str
    hit: tuple[float, float] | None = None  # (lat, lon) of the first point that refused it


@cache
def imagery_geofence() -> Geofence:
    """Türkiye land + internal waters + :data:`IMAGERY_BUFFER_NM`, for imagery only.

    Built from the same ``gt-geofence/1`` file and the same code as the collectors' fence, so
    a correction to the coastline lands in both.
    """
    return Geofence.from_mapping(load_geofence_data(), buffer_nm=IMAGERY_BUFFER_NM)


def _samples(bbox: BBox) -> list[tuple[float, float]]:
    """A lat/lon grid over ``bbox`` with a step of at most :data:`SAMPLE_STEP_KM`."""
    steps_x = min(MAX_SAMPLES_PER_AXIS, max(1, math.ceil(abs(bbox.width_km()) / SAMPLE_STEP_KM)))
    steps_y = min(MAX_SAMPLES_PER_AXIS, max(1, math.ceil(bbox.height_km() / SAMPLE_STEP_KM)))
    lons = [bbox.west + (bbox.east - bbox.west) * i / steps_x for i in range(steps_x + 1)]
    lats = [bbox.south + (bbox.north - bbox.south) * j / steps_y for j in range(steps_y + 1)]
    return [(lat, lon) for lat in lats for lon in lons]


def check_bbox(bbox: BBox) -> Verdict:
    """Refuse any area of interest that touches the Türkiye imagery geofence."""
    fence = imagery_geofence()
    min_lon, min_lat, max_lon, max_lat = fence.bbox
    if bbox.east < min_lon or bbox.west > max_lon or bbox.north < min_lat or bbox.south > max_lat:
        return Verdict(True, CLEAR_TR, CLEAR_EN)

    for lat, lon in _samples(bbox):
        if fence.contains(lat, lon):
            return Verdict(
                False,
                REFUSAL_TR.format(buffer=IMAGERY_BUFFER_NM),
                REFUSAL_EN.format(buffer=IMAGERY_BUFFER_NM),
                (lat, lon),
            )

    # A box can overlap the fence without containing a sample: catch it from the other side.
    for ring in fence.rings:
        for lon, lat in ring:
            if bbox.contains_point(lat, lon):
                return Verdict(
                    False,
                    REFUSAL_TR.format(buffer=IMAGERY_BUFFER_NM),
                    REFUSAL_EN.format(buffer=IMAGERY_BUFFER_NM),
                    (lat, lon),
                )

    return Verdict(True, CLEAR_TR, CLEAR_EN)
