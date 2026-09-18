from __future__ import annotations

from pathlib import Path

import pytest

from gt_osint_ai.config import ConfigError, load_areas

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config" / "areas.yaml"


def test_the_repository_config_is_valid_and_nothing_is_enabled() -> None:
    areas = load_areas(REPO_CONFIG)
    assert areas
    assert all(not a.enabled for a in areas), "no area ships enabled"
    known = {"sentinel-2-l2a", "sentinel-2-c1-l2a", "sentinel-1-grd", "landsat-c2-l2"}
    assert {a.collection for a in areas} <= known


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "areas.yaml"
    path.write_text(body, encoding="utf-8")
    return path


GOOD = """
areas:
  - id: aoi-test
    name: Test
    bbox: [32.0, 33.2, 33.0, 33.9]
    collection: sentinel-2-l2a
    max_cloud: 40
    cadence_days: 5
    enabled: false
"""


def test_a_good_file_loads(tmp_path: Path) -> None:
    (area,) = load_areas(_write(tmp_path, GOOD))
    assert area.id == "aoi-test"
    assert area.max_cloud == 40.0
    assert area.cadence_days == 5
    assert area.enabled is False


def test_an_area_over_turkiye_cannot_be_configured_at_all(tmp_path: Path) -> None:
    """Even with `enabled: false`: the file must not be loadable."""
    body = GOOD.replace("[32.0, 33.2, 33.0, 33.9]", "[32.6, 39.7, 33.1, 40.1]")
    with pytest.raises(ConfigError, match="RED LINE"):
        load_areas(_write(tmp_path, body))


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("areas: []\n", "non-empty list"),
        ("nope: 1\n", "'areas' key"),
        ("areas:\n  - id: x\n", "missing keys"),
        (GOOD.replace("id: aoi-test", "id: NO"), "id must match"),
        (GOOD.replace("collection: sentinel-2-l2a", "collection: maxar"), "collection must be one of"),
        (GOOD.replace("cadence_days: 5", "cadence_days: 0"), "cadence_days"),
        (GOOD.replace("enabled: false", "enabled: maybe"), "enabled must be"),
        (GOOD.replace("max_cloud: 40", "max_cloud: 400"), "percentage"),
        (GOOD.replace("name: Test", "colour: blue"), "unknown keys"),
        (GOOD.replace("bbox: [32.0, 33.2, 33.0, 33.9]", "bbox: [32.0, 33.2]"), "bbox must be"),
        (GOOD + GOOD.split("areas:")[1], "duplicate area id"),
    ],
)
def test_bad_files_are_refused(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_areas(_write(tmp_path, body))


def test_not_yaml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_areas(_write(tmp_path, "areas: [\n"))
