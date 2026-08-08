#!/usr/bin/env python3
"""Run the ordered tranche with parser lookahead and full-budget persistence.

The semantic frontier remains one document at a time. Parser observations may
run one heavy document ahead, but when the foreground enters PostgreSQL
persistence the parser lane is quiesced and the complete ``--worker-budget`` is
transferred to parallel provisional COPY lanes and fixed set-based merges.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_complete_tranche as complete_tranche  # noqa: E402

from src.policy.work_conserving_ordered_compilation import (  # noqa: E402
    compile_directory_postgres_work_conserving_ordered,
)


def main() -> int:
    complete_tranche.compile_directory_postgres = (
        compile_directory_postgres_work_conserving_ordered
    )
    return complete_tranche.main()


if __name__ == "__main__":
    raise SystemExit(main())
