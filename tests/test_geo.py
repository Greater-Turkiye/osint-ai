"""The vendored geofence must still behave like the reference implementation.

``src/gt_osint_ai/geo.py`` is a copy of ``platform/collectors/src/gt_collectors/geo.py``. These
cases are the ones the collectors rely on; if a future edit here drifts from that behaviour,
this file fails rather than a red line silently widening.
"""

from __future__ import annotations

import pytest

from gt_osint_ai.geo import Geofence, load_geofence_data, turkiye_geofence

# (name, lat, lon, inside the 12 nm collectors' fence?)
POINTS = [
    ("Ankara", 39.93, 32.86, True),
    ("Istanbul", 41.01, 28.98, True),
    ("Van", 38.49, 43.38, True),
    ("Sea of Marmara", 40.70, 28.20, True),
    ("Aegean, 5 km off Çeşme", 38.32, 26.25, True),
    ("Athens", 37.98, 23.73, False),
    ("Aleppo", 36.20, 37.16, False),
    ("Nicosia", 35.19, 33.38, False),
    ("open Black Sea", 43.50, 33.50, False),
    ("Baku", 40.41, 49.87, False),
]


@pytest.mark.parametrize(("name", "lat", "lon", "inside"), POINTS, ids=[p[0] for p in POINTS])
def test_collectors_fence_points(name: str, lat: float, lon: float, inside: bool) -> None:
    assert turkiye_geofence().contains(lat, lon) is inside, name


def test_geofence_file_is_the_one_platform_builds() -> None:
    data = load_geofence_data()
    assert data["schema"] == "gt-geofence/1"
    assert data["name"] == "TUR"
    assert data["buffer_nm"] == 12.0
    assert data["provenance"]["builder"] == "python -m gt_collectors.tools.build_geofence"
    assert data["polygons"], "the geofence must have at least one polygon"


def test_buffer_override_widens_the_fence() -> None:
    data = load_geofence_data()
    narrow = Geofence.from_mapping(data)
    wide = Geofence.from_mapping(data, buffer_nm=15.0)
    assert wide.radius_km > narrow.radius_km
    # A point in the band between the two radii is outside the narrow fence and inside the wide one.
    assert narrow.rings == wide.rings


def test_rejects_a_foreign_schema() -> None:
    with pytest.raises(ValueError, match="unsupported geofence schema"):
        Geofence.from_mapping({"schema": "something-else"})


def test_rings_need_three_vertices() -> None:
    with pytest.raises(ValueError, match="at least 3 distinct vertices"):
        Geofence([[(0.0, 0.0), (1.0, 1.0)]], 1.0)


def test_radius_must_be_finite_and_non_negative() -> None:
    square = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]
    with pytest.raises(ValueError, match="finite, non-negative"):
        Geofence(square, -1.0)
