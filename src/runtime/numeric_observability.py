"""Execution-only switches for scan-heavy numeric observability.

Semantic authority must never depend on these switches.  They exist so benchmark
and calibration runs can opt into aggregate corpus diagnostics without charging
ordinary production for the measurements themselves.
"""

from __future__ import annotations

import os


def controlled_reuse_measurement_enabled() -> bool:
    """Whether fresh numeric compiles record the scan-heavy learning observatory."""

    return os.environ.get("SENSIBLAW_RECORD_CONTROLLED_REUSE", "0") == "1"


def numeric_authority_counts_enabled() -> bool:
    """Whether numeric parser/PNF receipts include document-wide cardinalities."""

    return os.environ.get("SENSIBLAW_NUMERIC_AUTHORITY_COUNTS", "0") == "1"


__all__ = [
    "controlled_reuse_measurement_enabled",
    "numeric_authority_counts_enabled",
]
