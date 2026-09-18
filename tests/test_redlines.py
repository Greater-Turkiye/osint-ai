"""The red-line gate. These tests are mandatory: CI fails if any of them is skipped.

If one of these ever needs "fixing" by loosening the rule, that is a handbook ADR, not a diff.
"""

from __future__ import annotations

import pytest

from gt_osint_ai.redlines import IMAGERY_BUFFER_NM, BBox, check_bbox, imagery_geofence

# Boxes that must be refused. Each one either contains Turkish territory or sits inside the
# standoff around it. The comment says which, so a future reader can check the claim.
REFUSED = [
    ("Ankara", (32.6, 39.7, 33.1, 40.1)),  # inland Türkiye
    ("Istanbul and the Bosphorus", (28.9, 40.9, 29.3, 41.2)),  # land + internal waters
    ("Antalya coast", (30.5, 36.6, 31.0, 37.0)),  # coast + territorial sea
    ("Aegean off Izmir", (26.0, 38.2, 26.5, 38.6)),  # territorial sea
    ("Kilis, the Syrian border strip", (36.9, 36.6, 37.2, 36.8)),  # straddles the land border
    ("Idlib city", (36.4, 35.8, 36.9, 36.1)),  # inside the standoff; a real cost, see the module docstring
    ("Latakia port", (35.7, 35.4, 36.0, 35.7)),  # inside the standoff
    ("Lesbos", (26.0, 39.0, 26.4, 39.3)),  # a few km off the Turkish coast
    ("a box swallowing all of Türkiye", (20.0, 30.0, 50.0, 48.0)),  # no sample need be inside
]

# Boxes that must be allowed: outward-looking, clear of the standoff.
ALLOWED = [
    ("open sea south of Cyprus", (32.0, 33.2, 33.0, 33.9)),
    ("Aleppo", (37.0, 36.0, 37.4, 36.3)),
    ("Benghazi", (19.9, 32.0, 20.3, 32.3)),
    ("north Crete", (24.8, 35.3, 25.3, 35.6)),
    ("Baku", (49.7, 40.2, 50.1, 40.5)),
    ("central Black Sea", (33.0, 43.0, 34.0, 43.6)),
    ("the Atlantic, nowhere near the fence bbox", (-30.0, 30.0, -29.0, 31.0)),
]


@pytest.mark.parametrize(("name", "coords"), REFUSED, ids=[n for n, _ in REFUSED])
def test_refuses_turkiye_and_its_standoff(name: str, coords: tuple[float, float, float, float]) -> None:
    verdict = check_bbox(BBox(*coords))
    assert not verdict.allowed, f"{name} must be refused"
    assert verdict.hit is not None
    assert "RED LINE" in verdict.reason_en
    assert "KIRMIZI ÇİZGİ" in verdict.reason_tr


@pytest.mark.parametrize(("name", "coords"), ALLOWED, ids=[n for n, _ in ALLOWED])
def test_allows_outward_looking_areas(name: str, coords: tuple[float, float, float, float]) -> None:
    verdict = check_bbox(BBox(*coords))
    assert verdict.allowed, f"{name} must be allowed"
    assert verdict.hit is None


def test_a_box_containing_the_country_is_caught_by_the_vertex_test() -> None:
    """The sampling grid alone could miss a fence that is entirely inside a coarse box."""
    huge = BBox(20.0, 30.0, 50.0, 48.0)
    fence = imagery_geofence()
    assert any(huge.contains_point(lat, lon) for ring in fence.rings for lon, lat in ring)
    assert not check_bbox(huge).allowed


def test_the_buffer_is_wider_than_the_collectors_fence() -> None:
    """A regression guard: imagery stands further off than a point signal does."""
    assert IMAGERY_BUFFER_NM > 12.0
    assert imagery_geofence().radius_km > 12.0 * 1.852


@pytest.mark.parametrize(
    "text",
    [
        "1,2,3",  # too few
        "1,2,3,4,5",  # too many
        "a,b,c,d",  # not numbers
        "10,10,5,20",  # east <= west
        "10,20,20,10",  # north <= south
        "200,10,210,20",  # longitude out of range
        "10,-100,20,-80",  # latitude out of range
    ],
)
def test_bad_bboxes_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        BBox.parse(text)


def test_bbox_round_trips() -> None:
    bbox = BBox.parse("32.0,33.2,33.0,33.9")
    assert bbox.as_list() == [32.0, 33.2, 33.0, 33.9]
    assert str(bbox) == "32.0,33.2,33.0,33.9"
    assert bbox.height_km() == pytest.approx(0.7 * 110.574, rel=1e-6)
    assert bbox.width_km() > 0
