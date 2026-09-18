"""Command line: ``gt-osint-ai`` (or ``python -m gt_osint_ai``).

Two subcommands, and neither of them runs a model, downloads a pixel or needs a credential.
That is the point: the repository is at the design stage, and the CLI is here to prove that
the parts which *are* decided — the red line, the catalogue, the arithmetic — actually work.

``gt-osint-ai areas``
    Validate ``config/areas.yaml`` and print each area with its red-line verdict::

        gt-osint-ai areas --config config/areas.yaml

``gt-osint-ai scenes``
    Take a bounding box and a date range, refuse it if it touches Türkiye, ask the free
    Earth Search STAC API which open scenes exist, and print the work a pass would be::

        gt-osint-ai scenes --bbox 32.0,33.2,33.0,33.9 --from 2025-06-01 --to 2025-06-30
        gt-osint-ai scenes --area aoi-example-east-med --from 2025-06-01 --to 2025-06-30
        gt-osint-ai scenes --bbox 32.0,33.2,33.0,33.9 --from 2025-06-01 --to 2025-06-30 --json
        gt-osint-ai scenes --bbox 32.0,33.2,33.0,33.9 --from 2025-06-01 --to 2025-06-30 --input saved.json

``--input`` replays a saved STAC response instead of calling the network, which is how the
tests run and how anyone can see the output without leaving a trace in someone's access log.

Exit codes: ``0`` success, ``1`` a bad argument or an unreachable catalogue, ``2`` the red
line refused the request. ``2`` is deliberately distinct so a caller can never mistake a
refusal for an empty result.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from gt_osint_ai import __version__
from gt_osint_ai.config import ConfigError, load_areas
from gt_osint_ai.redlines import IMAGERY_BUFFER_NM, BBox, check_bbox
from gt_osint_ai.stac import COLLECTIONS, EARTH_SEARCH_V1, Scene, StacError, parse_feature_collection, search
from gt_osint_ai.tiling import human_bytes, human_duration, plan_tiles

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REDLINE = 2

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

NOT_IMPLEMENTED_NOTE = (
    "No model ran. Detection, embedding, change detection and the review queue are described "
    "in ARCHITECTURE.md and MODELS.md; none of them is implemented yet."
)


def _parse_date(value: str, *, flag: str) -> str:
    if not DATE_RE.match(value):
        raise argparse.ArgumentTypeError(f"{flag} must be a date as YYYY-MM-DD, got {value!r}")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gt-osint-ai",
        description="Greater Türkiye OSINT AI — design-stage tooling. Plans work; runs no model.",
    )
    parser.add_argument("--version", action="version", version=f"gt-osint-ai {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    areas = sub.add_parser("areas", help="validate and list the configured areas of interest")
    areas.add_argument("--config", default="config/areas.yaml", help="path to areas.yaml")
    areas.add_argument("--json", action="store_true", help="print one JSON object per area")

    scenes = sub.add_parser("scenes", help="list the open scenes available for an area and date range")
    target = scenes.add_mutually_exclusive_group(required=True)
    target.add_argument("--bbox", help="west,south,east,north in degrees")
    target.add_argument("--area", help="an id from --config")
    scenes.add_argument("--config", default="config/areas.yaml", help="path to areas.yaml, used with --area")
    scenes.add_argument("--from", dest="start", required=True, help="start date, YYYY-MM-DD")
    scenes.add_argument("--to", dest="end", required=True, help="end date, YYYY-MM-DD")
    scenes.add_argument(
        "--collection",
        default=None,
        choices=sorted(COLLECTIONS),
        help="which open collection to search (default: sentinel-2-l2a, or the area's)",
    )
    scenes.add_argument(
        "--max-cloud", type=float, default=None, help="drop scenes cloudier than this, in percent"
    )
    scenes.add_argument("--limit", type=int, default=20, help="scenes to fetch, 1-100 (one page only)")
    scenes.add_argument("--api-url", default=EARTH_SEARCH_V1, help="STAC API root (https only)")
    scenes.add_argument("--input", help="replay a saved STAC response instead of calling the network")
    scenes.add_argument("--json", action="store_true", help="print the plan as a single JSON object")
    return parser


def _refuse(bbox: BBox, reason_tr: str, reason_en: str, hit: tuple[float, float] | None, *, out) -> int:
    print(f"bbox   {bbox}", file=out)
    print(f"verdict REFUSED (red line, buffer {IMAGERY_BUFFER_NM:.0f} nm)", file=out)
    print(f"  TR   {reason_tr}", file=out)
    print(f"  EN   {reason_en}", file=out)
    if hit is not None:
        print(f"  hit  lat {hit[0]:.4f}, lon {hit[1]:.4f}", file=out)
    print("Nothing was requested from any catalogue.", file=out)
    return EXIT_REDLINE


def _cmd_areas(args: argparse.Namespace, out, err) -> int:
    try:
        areas = load_areas(args.config)
    except (OSError, ConfigError) as exc:
        print(f"error: {exc}", file=err)
        return EXIT_ERROR
    for area in areas:
        verdict = check_bbox(area.bbox)
        if args.json:
            print(
                json.dumps(
                    {
                        "id": area.id,
                        "name": area.name,
                        "bbox": area.bbox.as_list(),
                        "collection": area.collection,
                        "cadence_days": area.cadence_days,
                        "enabled": area.enabled,
                        "max_cloud": area.max_cloud,
                        "redline_allowed": verdict.allowed,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=out,
            )
        else:
            state = "enabled" if area.enabled else "disabled"
            line = f"{area.id}  [{state}]  {area.collection}  every {area.cadence_days}d  bbox {area.bbox}"
            print(line, file=out)
            if area.name:
                print(f"    {area.name}", file=out)
            print(f"    red line: {'clear' if verdict.allowed else 'REFUSED'}", file=out)
    print(f"{len(areas)} area(s) validated. Nothing was collected.", file=err)
    return EXIT_OK


def _load_scenes(
    args: argparse.Namespace, bbox: BBox, collection: str, max_cloud: float | None
) -> list[Scene]:
    if args.input:
        doc = json.loads(Path(args.input).read_text(encoding="utf-8"))
        return parse_feature_collection(doc, fallback_collection=collection)
    return search(
        bbox.as_list(),
        f"{args.start}T00:00:00Z",
        f"{args.end}T23:59:59Z",
        collection=collection,
        max_cloud=max_cloud,
        limit=args.limit,
        api_url=args.api_url,
    )


def _cmd_scenes(args: argparse.Namespace, out, err) -> int:
    try:
        _parse_date(args.start, flag="--from")
        _parse_date(args.end, flag="--to")
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=err)
        return EXIT_ERROR
    if args.start > args.end:
        print("error: --from must not be after --to", file=err)
        return EXIT_ERROR

    collection = args.collection
    max_cloud = args.max_cloud
    if args.area:
        try:
            areas = {a.id: a for a in load_areas(args.config)}
        except (OSError, ConfigError) as exc:
            print(f"error: {exc}", file=err)
            return EXIT_ERROR
        area = areas.get(args.area)
        if area is None:
            print(f"error: no area {args.area!r} in {args.config}; known: {sorted(areas)}", file=err)
            return EXIT_ERROR
        bbox = area.bbox
        collection = collection or area.collection
        max_cloud = max_cloud if max_cloud is not None else area.max_cloud
    else:
        try:
            bbox = BBox.parse(args.bbox)
        except ValueError as exc:
            print(f"error: {exc}", file=err)
            return EXIT_ERROR
    collection = collection or "sentinel-2-l2a"

    verdict = check_bbox(bbox)
    if not verdict.allowed:
        return _refuse(bbox, verdict.reason_tr, verdict.reason_en, verdict.hit, out=out)

    try:
        scenes = _load_scenes(args, bbox, collection, max_cloud)
    except (OSError, StacError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=err)
        return EXIT_ERROR

    meta = COLLECTIONS[collection]
    gsd = float(meta["gsd_m"])
    plan = plan_tiles(bbox, gsd_m=gsd)
    total_tiles = plan.tiles * len(scenes)

    if args.json:
        print(
            _as_json(args, bbox=bbox, collection=collection, meta=meta, scenes=scenes, plan=plan),
            file=out,
        )
        return EXIT_OK
    _render(
        args,
        bbox=bbox,
        collection=collection,
        meta=meta,
        gsd=gsd,
        scenes=scenes,
        plan=plan,
        total_tiles=total_tiles,
        out=out,
    )
    return EXIT_OK


def _as_json(args, *, bbox, collection, meta, scenes, plan) -> str:
    return json.dumps(
        {
            "bbox": bbox.as_list(),
            "from": args.start,
            "to": args.end,
            "collection": collection,
            "licence": meta["licence"],
            "redline_allowed": True,
            "scenes": [
                {"id": s.id, "datetime": s.datetime, "cloud_cover": s.cloud_cover, "platform": s.platform}
                for s in scenes
            ],
            "plan": {
                "tile_px": plan.tile_px,
                "overlap_px": plan.overlap_px,
                "gsd_m": plan.gsd_m,
                "tiles_per_scene": plan.tiles,
                "tiles_total": plan.tiles * len(scenes),
                "bytes_read_estimate": plan.bytes_read * len(scenes),
                "embedding_seconds_estimate": plan.embedding_seconds * len(scenes),
            },
            "executed": False,
            "note": NOT_IMPLEMENTED_NOTE,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _render(args, *, bbox, collection, meta, gsd, scenes, plan, total_tiles, out) -> None:
    source = f"replayed from {args.input}" if args.input else args.api_url
    print(f"bbox       {bbox}  ({plan.width_km:.0f} x {plan.height_km:.0f} km)", file=out)
    print(f"dates      {args.start} .. {args.end}", file=out)
    print(f"collection {collection} — {meta['mission']}", file=out)
    print(f"licence    {meta['licence']}", file=out)
    print(f"resolution {gsd:g} m/pixel, nominal revisit {meta['revisit_days']} d", file=out)
    print(f"red line   clear ({IMAGERY_BUFFER_NM:.0f} nm Türkiye geofence)", file=out)
    print(f"source     {source}", file=out)
    print("", file=out)
    if not scenes:
        print("No scenes matched. Widen the dates or raise --max-cloud.", file=out)
    else:
        print(f"{len(scenes)} scene(s) available (metadata only; nothing downloaded):", file=out)
        for scene in scenes:
            cloud = f"{scene.cloud_cover:.0f}% cloud" if scene.cloud_cover is not None else "cloud n/a"
            line = f"  {scene.id}  {scene.datetime or '?'}  {cloud}  {scene.platform or ''}"
            print(line.rstrip(), file=out)
    print("", file=out)
    print("Would process, if the pipeline existed:", file=out)
    print(f"  tiles     {plan.tiles_x} x {plan.tiles_y} = {plan.tiles}/scene, {total_tiles} total", file=out)
    print(f"            {plan.tile_px} px tiles, {plan.overlap_px} px overlap, {plan.bands} bands", file=out)
    read = human_bytes(plan.bytes_read * len(scenes))
    print(f"  read      ~{read} from the catalogue, kept: 0 B", file=out)
    embed = human_duration(plan.embedding_seconds * len(scenes))
    print(f"  embed     ~{embed} of GPU at an assumed 20 tiles/s (a planning figure, not a", file=out)
    print("            measurement — nothing here has ever been run)", file=out)
    print("", file=out)
    print(NOT_IMPLEMENTED_NOTE, file=out)


def main(argv: list[str] | None = None, *, out=None, err=None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    args = _build_parser().parse_args(argv)
    if args.command == "areas":
        return _cmd_areas(args, out, err)
    return _cmd_scenes(args, out, err)
