"""Greater Türkiye OSINT AI — design-stage scaffold.

Today this package does exactly one honest thing end to end: given a bounding box and a
date range it refuses anything the imagery red line forbids (:mod:`gt_osint_ai.redlines`),
asks the free Earth Search STAC API which open Sentinel-2 or Landsat scenes exist
(:mod:`gt_osint_ai.stac`), and prints the work it *would* do (:mod:`gt_osint_ai.tiling`).

There is no model, no inference, no download and no credential anywhere in this package,
and there will not be until the plan in ``MODELS.md`` and ``EVALUATION.md`` is executed.
"""

from __future__ import annotations

__version__ = "0.0.1"

__all__ = ["__version__"]
