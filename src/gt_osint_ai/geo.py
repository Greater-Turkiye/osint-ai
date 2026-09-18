"""Dependency-free geofence: point-in-polygon plus an approximate distance buffer.

Vendored **unchanged** (except the package name in :func:`load_geofence_data`) from
``platform/collectors/src/gt_collectors/geo.py``, which is the reference implementation.
Keep the two in sync: a fix there is copied here, and ``tests/test_geo.py`` re-runs the
same boundary cases so a silent drift fails CI. ``data/tr_geofence.json`` is the same file,
built by ``python -m gt_collectors.tools.build_geofence`` in ``platform``.

The Türkiye geofence is ``land polygon (+ internal waters) + 12 nautical miles``. It is loaded
from ``data/tr_geofence.json`` (built by ``gt_collectors.tools.build_geofence`` in the
``platform`` repository from the Natural Earth data in ``apps/web/assets/data/countries-50m.json``).

How "inside" is decided, erring on the side of dropping (fail safe):

1. Outside a bounding box grown by the buffer radius -> outside (fast path).
2. Inside any polygon (even-odd ray casting in lon/lat) -> inside.
3. Otherwise inside if the distance to the nearest polygon edge is <= the effective radius.

Effective radius = ``buffer_nm * 1.852 km`` + the recorded simplification error of the
vendored polygon + a source-accuracy margin, all multiplied by ``1 + APPROX_MARGIN``.

Distances use a local equirectangular projection centred on the query point. Over the
~25 km scale that matters here its error is well below 1 %, which ``APPROX_MARGIN`` covers.
The buffer is uniform: at the coast it approximates the 12 nm territorial sea; at land
borders it acts as an extra fail-safe margin (points just across a land border are dropped too).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache
from importlib import resources

KM_PER_NM = 1.852
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQUATOR = 111.320
APPROX_MARGIN = 0.01

Ring = Sequence[tuple[float, float]]  # [(lon, lat), ...], closed or open


def point_in_ring(lon: float, lat: float, ring: Ring) -> bool:
    """Even-odd ray casting. ``ring`` is a list of ``(lon, lat)`` vertices."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x_cross = xi + (lat - yi) * (xj - xi) / (yj - yi)
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def distance_km_to_segment(lat: float, lon: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    """Approximate distance (km) from a point to segment ``a``-``b`` (both ``(lon, lat)``).

    Uses an equirectangular projection centred on the query point.
    """
    kx = KM_PER_DEG_LON_EQUATOR * math.cos(math.radians(lat))
    ky = KM_PER_DEG_LAT
    ax, ay = (a[0] - lon) * kx, (a[1] - lat) * ky
    bx, by = (b[0] - lon) * kx, (b[1] - lat) * ky
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0.0:
        return math.hypot(ax, ay)
    t = -(ax * dx + ay * dy) / seg2
    t = max(0.0, min(1.0, t))
    return math.hypot(ax + t * dx, ay + t * dy)


@dataclass(frozen=True, slots=True)
class _Edge:
    a: tuple[float, float]
    b: tuple[float, float]
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float


class Geofence:
    """A set of polygons (outer rings, lon/lat) plus a uniform buffer radius in km."""

    def __init__(self, rings: Iterable[Ring], radius_km: float) -> None:
        if radius_km < 0 or not math.isfinite(radius_km):
            raise ValueError("radius_km must be a finite, non-negative number")
        self.rings: list[list[tuple[float, float]]] = []
        self._edges: list[_Edge] = []
        for ring in rings:
            pts = [(float(x), float(y)) for x, y in ring]
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) < 3:
                raise ValueError("a ring needs at least 3 distinct vertices")
            self.rings.append(pts)
            for i, a in enumerate(pts):
                b = pts[(i + 1) % len(pts)]
                self._edges.append(
                    _Edge(a, b, min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]))
                )
        if not self.rings:
            raise ValueError("geofence needs at least one ring")
        self.radius_km = radius_km
        lons = [p[0] for r in self.rings for p in r]
        lats = [p[1] for r in self.rings for p in r]
        dlat = radius_km / KM_PER_DEG_LAT
        # Longitude degrees shrink towards the poles; use the most poleward latitude (conservative).
        max_abs_lat = min(89.0, max(abs(min(lats)), abs(max(lats))) + dlat)
        dlon = radius_km / (KM_PER_DEG_LON_EQUATOR * math.cos(math.radians(max_abs_lat)))
        self.bbox = (min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat)

    def in_polygon(self, lat: float, lon: float) -> bool:
        return any(point_in_ring(lon, lat, ring) for ring in self.rings)

    def distance_km(self, lat: float, lon: float, *, limit_km: float | None = None) -> float:
        """Distance to the nearest edge in km (``0.0`` when inside a polygon).

        With ``limit_km``, edges whose bounding box is farther than ``limit_km`` are skipped and
        ``math.inf`` is returned when nothing is within reach.
        """
        if self.in_polygon(lat, lon):
            return 0.0
        best = math.inf
        if limit_km is not None:
            dlat = limit_km / KM_PER_DEG_LAT
            dlon = limit_km / (KM_PER_DEG_LON_EQUATOR * max(math.cos(math.radians(abs(lat) + dlat)), 1e-6))
        for e in self._edges:
            if limit_km is not None and (
                e.max_lat < lat - dlat
                or e.min_lat > lat + dlat
                or e.max_lon < lon - dlon
                or e.min_lon > lon + dlon
            ):
                continue
            d = distance_km_to_segment(lat, lon, e.a, e.b)
            best = min(best, d)
        return best

    def contains(self, lat: float, lon: float) -> bool:
        """True if the point is inside a polygon or within ``radius_km`` of one."""
        min_lon, min_lat, max_lon, max_lat = self.bbox
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            return False
        return self.distance_km(lat, lon, limit_km=self.radius_km) <= self.radius_km

    @classmethod
    def from_mapping(cls, data: dict, *, buffer_nm: float | None = None) -> Geofence:
        """Build from the ``gt-geofence/1`` JSON structure."""
        if data.get("schema") != "gt-geofence/1":
            raise ValueError("unsupported geofence schema")
        nm = float(data["buffer_nm"] if buffer_nm is None else buffer_nm)
        margins = float(data["max_simplification_error_km"]) + float(data["source_margin_km"])
        radius = (nm * KM_PER_NM + margins) * (1.0 + APPROX_MARGIN)
        rings = [p["ring"] for p in data["polygons"]]
        return cls(rings, radius)


def load_geofence_data() -> dict:
    ref = resources.files("gt_osint_ai").joinpath("data/tr_geofence.json")
    return json.loads(ref.read_text(encoding="utf-8"))


@cache
def turkiye_geofence() -> Geofence:
    """The Türkiye geofence used by the safety filter (land + internal waters + 12 nm)."""
    return Geofence.from_mapping(load_geofence_data())
