#!/usr/bin/env python3
"""Compatibility fixture for the generic proof-relevant entity reporter.

Reagan is intentionally not resolved by bespoke logic here.  This wrapper only
chooses report-entry surface strings and delegates all admissibility, identity,
and factor semantics to ``epistemic_factor_report``.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.storage.postgres.epistemic_factor_report import (
    collect_epistemic_entity_report,
    render_epistemic_entity_report,
)
from src.storage.postgres.spacy_parser_model import connect


DEFAULT_DATABASE_URL = (
    "postgresql://postgres@127.0.0.1:5433/sensiblaw_sparse_bench"
)
DEFAULT_OUTPUT = Path(
    ".tmp/exact-0008-current-20260804/trial-sparse-bench/gwb/"
    "reagan_factor_semantic_report.md"
)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    with connect(database_url) as connection:
        report = collect_epistemic_entity_report(
            connection,
            ("reagan", "ronald"),
        )
        rendered = render_epistemic_entity_report(report)

    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(rendered, encoding="utf-8")
    print(DEFAULT_OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
