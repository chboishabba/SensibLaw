#!/usr/bin/env python3
"""Run the complete tranche as an ordered world fold with parser lookahead.

This entrypoint preserves the existing complete-tranche CLI.  It replaces only
the directory compiler binding so that:

* document semantic compilation and PostgreSQL publication remain ordered;
* at most one partition-worthy future document is pre-parsed;
* the pre-parser writes only document-scoped parser-fibre checkpoints;
* foreground replay waits for an active prefetch instead of parsing twice; and
* the parser lane and foreground lane remain within ``--worker-budget``.

Use ``--document-workers 1``.  More than one semantic document worker is
rejected because later documents must compile against the world published by
earlier documents.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Importing from the script directory keeps the existing CLI and tranche phase
# implementation as the sole orchestration authority.
import run_complete_tranche as complete_tranche  # noqa: E402

from src.policy.ordered_world_parser_lookahead import (  # noqa: E402
    compile_directory_postgres_ordered_world,
)


def main() -> int:
    complete_tranche.compile_directory_postgres = (
        compile_directory_postgres_ordered_world
    )
    return complete_tranche.main()


if __name__ == "__main__":
    raise SystemExit(main())
