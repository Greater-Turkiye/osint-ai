"""Areas of interest (YAML). Strict: unknown keys and invalid values are errors.

``config/areas.yaml``::

    areas:
      - id: aoi-example                 # unique, [a-z0-9-], 3-64 chars
        name: Example area
        bbox: [32.0, 34.0, 33.0, 34.8]  # west, south, east, north
        collection: sentinel-2-l2a      # must be on the checked-licence list in stac.py
        max_cloud: 40                   # percent; omitted for radar collections
        cadence_days: 5                 # >= 1; how often a pass would run
        enabled: false                  # nothing is enabled until a maintainer reviews it
        notes: free text                # optional

Every area is validated against the imagery red line at load time (:mod:`gt_osint_ai.redlines`),
so a box that touches Türkiye cannot sit in the configuration file waiting to be enabled by
accident. That check runs whether or not ``enabled`` is true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from gt_osint_ai.redlines import BBox, check_bbox
from gt_osint_ai.stac import COLLECTIONS

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
REQUIRED = ("id", "bbox", "collection", "cadence_days", "enabled")
OPTIONAL = ("name", "max_cloud", "notes")
MIN_CADENCE_DAYS = 1


class ConfigError(ValueError):
    """The configuration file is not usable. Never a warning: loading fails."""


@dataclass(frozen=True, slots=True)
class Area:
    id: str
    bbox: BBox
    collection: str
    cadence_days: int
    enabled: bool
    name: str | None = None
    max_cloud: float | None = None
    notes: str | None = None


def _area_from_mapping(raw: Any, *, index: int) -> Area:
    where = f"areas[{index}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where} must be a mapping")
    unknown = sorted(set(raw) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise ConfigError(f"{where}: unknown keys {unknown}")
    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise ConfigError(f"{where}: missing keys {missing}")

    area_id = raw["id"]
    if not isinstance(area_id, str) or not ID_RE.match(area_id):
        raise ConfigError(f"{where}: id must match {ID_RE.pattern}")

    bbox_raw = raw["bbox"]
    if not isinstance(bbox_raw, list) or len(bbox_raw) != 4:
        raise ConfigError(f"{where}: bbox must be [west, south, east, north]")
    try:
        bbox = BBox(*(float(v) for v in bbox_raw))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{where}: {exc}") from exc

    verdict = check_bbox(bbox)
    if not verdict.allowed:
        raise ConfigError(f"{where}: {verdict.reason_en}")

    collection = raw["collection"]
    if collection not in COLLECTIONS:
        raise ConfigError(f"{where}: collection must be one of {sorted(COLLECTIONS)}")

    cadence = raw["cadence_days"]
    if not isinstance(cadence, int) or isinstance(cadence, bool) or cadence < MIN_CADENCE_DAYS:
        raise ConfigError(f"{where}: cadence_days must be an integer >= {MIN_CADENCE_DAYS}")

    enabled = raw["enabled"]
    if not isinstance(enabled, bool):
        raise ConfigError(f"{where}: enabled must be true or false")

    max_cloud = raw.get("max_cloud")
    if max_cloud is not None:
        if isinstance(max_cloud, bool) or not isinstance(max_cloud, (int, float)):
            raise ConfigError(f"{where}: max_cloud must be a number")
        if not 0.0 <= float(max_cloud) <= 100.0:
            raise ConfigError(f"{where}: max_cloud is a percentage between 0 and 100")
        max_cloud = float(max_cloud)

    name = raw.get("name")
    if name is not None and not isinstance(name, str):
        raise ConfigError(f"{where}: name must be text")
    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ConfigError(f"{where}: notes must be text")

    return Area(
        id=area_id,
        bbox=bbox,
        collection=collection,
        cadence_days=cadence,
        enabled=enabled,
        name=name,
        max_cloud=max_cloud,
        notes=notes,
    )


def load_areas(path: str | Path) -> list[Area]:
    """Read and validate ``config/areas.yaml``. Raises :class:`ConfigError` on anything odd."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(doc, dict) or "areas" not in doc:
        raise ConfigError(f"{path}: the file must be a mapping with an 'areas' key")
    unknown = sorted(set(doc) - {"areas"})
    if unknown:
        raise ConfigError(f"{path}: unknown top-level keys {unknown}")
    raw_areas = doc["areas"]
    if not isinstance(raw_areas, list) or not raw_areas:
        raise ConfigError(f"{path}: 'areas' must be a non-empty list")

    areas = [_area_from_mapping(raw, index=i) for i, raw in enumerate(raw_areas)]
    seen: set[str] = set()
    for area in areas:
        if area.id in seen:
            raise ConfigError(f"{path}: duplicate area id {area.id!r}")
        seen.add(area.id)
    return areas
