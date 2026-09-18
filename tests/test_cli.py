"""End to end, without a network: the CLI is the promise the README makes."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from gt_osint_ai.cli import EXIT_ERROR, EXIT_OK, EXIT_REDLINE, main

FIXTURE = Path(__file__).parent / "fixtures" / "earth-search-s2.json"
REPO_CONFIG = Path(__file__).resolve().parents[1] / "config" / "areas.yaml"

OPEN_SEA = "32.0,33.2,33.0,33.9"
ANKARA = "32.6,39.7,33.1,40.1"


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(list(argv), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_scenes_end_to_end_from_a_saved_response() -> None:
    code, out, _ = run(
        "scenes", "--bbox", OPEN_SEA, "--from", "2025-06-01", "--to", "2025-06-30", "--input", str(FIXTURE)
    )
    assert code == EXIT_OK
    assert "3 scene(s) available" in out
    assert "S2B_36SUB_20250629_0_L2A" in out
    assert "Copernicus" in out  # the licence is always printed
    assert "red line   clear" in out
    assert "Would process, if the pipeline existed" in out
    assert "No model ran." in out
    assert "kept: 0 B" in out


def test_scenes_json_is_machine_readable_and_admits_it_did_nothing() -> None:
    code, out, _ = run(
        "scenes",
        "--bbox",
        OPEN_SEA,
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-30",
        "--input",
        str(FIXTURE),
        "--json",
    )
    assert code == EXIT_OK
    doc = json.loads(out)
    assert doc["executed"] is False
    assert doc["redline_allowed"] is True
    assert doc["collection"] == "sentinel-2-l2a"
    assert len(doc["scenes"]) == 3
    assert doc["plan"]["tiles_total"] == doc["plan"]["tiles_per_scene"] * 3
    assert doc["plan"]["gsd_m"] == 10.0


def test_the_red_line_refuses_before_any_network_call() -> None:
    code, out, _ = run("scenes", "--bbox", ANKARA, "--from", "2025-06-01", "--to", "2025-06-30")
    assert code == EXIT_REDLINE
    assert "REFUSED" in out
    assert "KIRMIZI ÇİZGİ" in out
    assert "RED LINE" in out
    assert "Nothing was requested from any catalogue." in out


def test_a_refusal_is_not_an_empty_result() -> None:
    """The two outcomes must never share an exit code."""
    assert EXIT_REDLINE != EXIT_OK
    assert EXIT_REDLINE != EXIT_ERROR


def test_areas_lists_the_repository_config() -> None:
    code, out, err = run("areas", "--config", str(REPO_CONFIG))
    assert code == EXIT_OK
    assert "aoi-example-east-med" in out
    assert "[disabled]" in out
    assert "red line: clear" in out
    assert "Nothing was collected." in err


def test_areas_json() -> None:
    code, out, _ = run("areas", "--config", str(REPO_CONFIG), "--json")
    assert code == EXIT_OK
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert rows
    assert all(row["redline_allowed"] for row in rows)
    assert all(row["enabled"] is False for row in rows)


def test_scenes_by_area_id() -> None:
    code, out, _ = run(
        "scenes",
        "--area",
        "aoi-example-east-med",
        "--config",
        str(REPO_CONFIG),
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-30",
        "--input",
        str(FIXTURE),
    )
    assert code == EXIT_OK
    assert "sentinel-2-l2a" in out


@pytest.mark.parametrize(
    "argv",
    [
        ("scenes", "--bbox", OPEN_SEA, "--from", "01-06-2025", "--to", "2025-06-30"),
        ("scenes", "--bbox", OPEN_SEA, "--from", "2025-06-30", "--to", "2025-06-01"),
        ("scenes", "--bbox", "nonsense", "--from", "2025-06-01", "--to", "2025-06-30"),
        ("scenes", "--area", "no-such-area", "--from", "2025-06-01", "--to", "2025-06-30"),
        ("areas", "--config", "no-such-file.yaml"),
    ],
)
def test_bad_arguments_exit_one(argv: tuple[str, ...]) -> None:
    code, _, err = run(*argv)
    assert code == EXIT_ERROR
    assert err.startswith("error:")


def test_missing_area_message_names_the_config(tmp_path: Path) -> None:
    code, _, err = run(
        "scenes",
        "--area",
        "ghost",
        "--config",
        str(REPO_CONFIG),
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-30",
    )
    assert code == EXIT_ERROR
    assert "aoi-example-east-med" in err


def test_version() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
