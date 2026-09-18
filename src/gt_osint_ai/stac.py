"""A small, dependency-free STAC client for the free open-imagery catalogues.

Only searching metadata. This module never downloads a pixel: it asks which scenes exist so
:mod:`gt_osint_ai.tiling` can say how much work they would be. See ``DATA.md`` for why that
distinction matters (the imagery is open, but we redistribute derived features, not imagery).

Default endpoint: Earth Search v1 (Element 84), which indexes the AWS Registry of Open Data
and needs no account, no key and no payment method — which is what makes it usable under
handbook ADR 0008. It is offered "as a best effort", so treat an outage as normal and
:data:`MIRRORS` as the fallback list.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

EARTH_SEARCH_V1 = "https://earth-search.aws.element84.com/v1"

#: Alternative free STAC APIs, in the order we would try them. All are metadata-only for us.
MIRRORS = (
    ("earth-search", EARTH_SEARCH_V1, "Element 84, AWS Open Data; no account"),
    (
        "planetary-computer",
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        "search is open; asset URLs need a free SAS token",
    ),
    ("cdse", "https://stac.dataspace.copernicus.eu/v1", "Copernicus Data Space; free account for downloads"),
)

#: The collections we allow. Anything not listed here has not had its licence checked.
COLLECTIONS: dict[str, dict[str, str]] = {
    "sentinel-2-l2a": {
        "mission": "Sentinel-2 MSI L2A (surface reflectance)",
        "gsd_m": "10",
        "revisit_days": "5",
        "licence": "Copernicus open licence (free, full, open; attribution required)",
    },
    "sentinel-2-c1-l2a": {
        "mission": "Sentinel-2 MSI L2A, Collection 1 (reprocessed, replacing sentinel-2-l2a)",
        "gsd_m": "10",
        "revisit_days": "5",
        "licence": "Copernicus open licence (free, full, open; attribution required)",
    },
    "sentinel-1-grd": {
        "mission": "Sentinel-1 SAR GRD (cloud- and night-independent)",
        "gsd_m": "10",
        "revisit_days": "12",
        "licence": "Copernicus open licence (free, full, open; attribution required)",
    },
    "landsat-c2-l2": {
        "mission": "Landsat Collection 2 Level-2 (Landsat 8/9 OLI-TIRS)",
        "gsd_m": "30",
        "revisit_days": "8",
        "licence": "USGS/NASA, public domain (attribution requested)",
    },
}

DEFAULT_TIMEOUT_S = 30.0
MAX_LIMIT = 100  # one page; we do not paginate yet, and we say so rather than pretend


class StacError(RuntimeError):
    """The catalogue could not be queried, or answered something we will not parse."""


@dataclass(frozen=True, slots=True)
class Scene:
    """One catalogue entry. Metadata only — ``id`` is a pointer, not a picture."""

    id: str
    collection: str
    datetime: str | None
    cloud_cover: float | None
    bbox: tuple[float, float, float, float] | None
    platform: str | None

    @property
    def licence(self) -> str:
        return COLLECTIONS.get(self.collection, {}).get("licence", "unknown — do not use")


def _feature_to_scene(feature: dict[str, Any], *, fallback_collection: str) -> Scene:
    props = feature.get("properties") or {}
    raw_bbox = feature.get("bbox")
    bbox: tuple[float, float, float, float] | None = None
    if isinstance(raw_bbox, list) and len(raw_bbox) >= 4:
        bbox = (float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3]))
    cloud = props.get("eo:cloud_cover")
    return Scene(
        id=str(feature.get("id", "")),
        collection=str(feature.get("collection") or fallback_collection),
        datetime=props.get("datetime"),
        cloud_cover=float(cloud) if isinstance(cloud, (int, float)) else None,
        bbox=bbox,
        platform=props.get("platform"),
    )


def parse_feature_collection(doc: dict[str, Any], *, fallback_collection: str = "") -> list[Scene]:
    """Turn a STAC ``FeatureCollection`` into scenes. Used by the tests without a network."""
    if doc.get("type") != "FeatureCollection":
        raise StacError("expected a STAC FeatureCollection")
    features = doc.get("features")
    if not isinstance(features, list):
        raise StacError("FeatureCollection has no features array")
    return [
        _feature_to_scene(f, fallback_collection=fallback_collection) for f in features if isinstance(f, dict)
    ]


def build_query(
    bbox: list[float],
    start: str,
    end: str,
    *,
    collection: str,
    max_cloud: float | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """The STAC item-search body. Kept separate so a test can assert it without a network."""
    if collection not in COLLECTIONS:
        raise StacError(
            f"collection {collection!r} is not on the checked-licence list: {sorted(COLLECTIONS)}"
        )
    if not 1 <= limit <= MAX_LIMIT:
        raise StacError(f"limit must be between 1 and {MAX_LIMIT}")
    query: dict[str, Any] = {
        "collections": [collection],
        "bbox": bbox,
        "datetime": f"{start}/{end}",
        "limit": limit,
    }
    if max_cloud is not None:
        if not 0.0 <= max_cloud <= 100.0:
            raise StacError("max_cloud is a percentage between 0 and 100")
        # Sentinel-1 is radar: it has no cloud-cover property, so the filter is dropped there.
        if collection != "sentinel-1-grd":
            query["query"] = {"eo:cloud_cover": {"lte": max_cloud}}
    return query


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects outright rather than follow a catalogue somewhere unexpected."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0917
        raise StacError(f"catalogue answered {code} redirect to {newurl!r}; refusing to follow")


def search(
    bbox: list[float],
    start: str,
    end: str,
    *,
    collection: str = "sentinel-2-l2a",
    max_cloud: float | None = None,
    limit: int = 20,
    api_url: str = EARTH_SEARCH_V1,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> list[Scene]:
    """POST one page of item-search. No credential is sent, because none is needed."""
    if not api_url.startswith("https://"):
        raise StacError("the catalogue endpoint must be https")
    body = json.dumps(build_query(bbox, start, end, collection=collection, max_cloud=max_cloud, limit=limit))
    request = urllib.request.Request(  # noqa: S310 - the https scheme is checked above
        f"{api_url.rstrip('/')}/search",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/geo+json",
            "User-Agent": "gt-osint-ai/0.0.1 (+https://github.com/Greater-Turkiye/osint-ai)",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise StacError(f"catalogue returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise StacError(f"catalogue unreachable: {exc.reason}") from exc
    try:
        doc = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StacError("catalogue returned something that is not JSON") from exc
    return parse_feature_collection(doc, fallback_collection=collection)
