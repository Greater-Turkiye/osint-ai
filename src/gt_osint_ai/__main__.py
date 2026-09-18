"""``python -m gt_osint_ai`` is the same entry point as ``gt-osint-ai``."""

from __future__ import annotations

import sys

from gt_osint_ai.cli import main

if __name__ == "__main__":
    sys.exit(main())
