from __future__ import annotations

import json
from pathlib import Path

import pytest

from gt_osint_ai.stac import COLLECTIONS, StacError, build_query, parse_feature_collection, search

FIXTURE = Path(__file__).parent / "fixtures" / "earth-search-s2.json"


def test_fixture_parses_into_scenes() -> None:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenes = parse_feature_collection(doc, fallback_collection="sentinel-2-l2a")
    assert len(scenes) == 3
    first = scenes[0]
    assert first.id == "S2B_36SUB_20250629_0_L2A"
    assert first.collection == "sentinel-2-l2a"
    assert first.datetime is not None and first.datetime.startswith("2025-06-29")
    assert first.cloud_cover is not None and 0 <= first.cloud_cover <= 100
    assert first.platform == "sentinel-2b"
    assert first.bbox is not None and len(first.bbox) == 4
    assert "Copernicus" in first.licence


def test_every_allowed_collection_records_a_licence() -> None:
    for name, meta in COLLECTIONS.items():
        assert meta["licence"], f"{name} has no licence recorded"
        assert float(meta["gsd_m"]) > 0
        assert int(meta["revisit_days"]) > 0


def test_query_shape() -> None:
    query = build_query(
        [1.0, 2.0, 3.0, 4.0],
        "2025-06-01T00:00:00Z",
        "2025-06-30T23:59:59Z",
        collection="sentinel-2-l2a",
        max_cloud=40,
        limit=5,
    )
    assert query["collections"] == ["sentinel-2-l2a"]
    assert query["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert query["datetime"] == "2025-06-01T00:00:00Z/2025-06-30T23:59:59Z"
    assert query["limit"] == 5
    assert query["query"] == {"eo:cloud_cover": {"lte": 40}}


def test_radar_has_no_cloud_filter() -> None:
    query = build_query([1.0, 2.0, 3.0, 4.0], "a", "b", collection="sentinel-1-grd", max_cloud=40)
    assert "query" not in query


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"collection": "maxar-worldview"}, "checked-licence list"),
        ({"collection": "sentinel-2-l2a", "limit": 0}, "limit must be"),
        ({"collection": "sentinel-2-l2a", "limit": 1000}, "limit must be"),
        ({"collection": "sentinel-2-l2a", "max_cloud": 150}, "percentage"),
    ],
)
def test_query_refuses_bad_input(kwargs: dict, message: str) -> None:
    with pytest.raises(StacError, match=message):
        build_query([1.0, 2.0, 3.0, 4.0], "a", "b", **kwargs)


def test_search_refuses_a_plaintext_endpoint() -> None:
    with pytest.raises(StacError, match="must be https"):
        search([1.0, 2.0, 3.0, 4.0], "a", "b", api_url="http://example.invalid/v1")


@pytest.mark.parametrize("doc", [{"type": "Feature"}, {"type": "FeatureCollection"}])
def test_bad_documents_are_refused(doc: dict) -> None:
    with pytest.raises(StacError):
        parse_feature_collection(doc)


@pytest.mark.network
def test_live_catalogue_answers() -> None:
    """Deselected in CI (`-m 'not network'`); run it by hand to check the endpoint still works."""
    scenes = search(
        [32.0, 33.2, 33.0, 33.9],
        "2025-06-01T00:00:00Z",
        "2025-06-30T23:59:59Z",
        collection="sentinel-2-l2a",
        max_cloud=40,
        limit=3,
    )
    assert scenes
    assert all(s.id for s in scenes)
