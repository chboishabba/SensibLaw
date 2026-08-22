#!/usr/bin/env python3
"""Run the complete tranche pipeline on the strict numeric PostgreSQL path.

The historical ``run_complete_tranche.py`` CLI retains compatibility-replay
semantics for parity and migration workflows.  Production must not silently pay
that document-sized typing/persistence cost.  This entrypoint makes the intended
production mode explicit by injecting ``--strict-exact`` unless the caller has
already supplied it.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_complete_tranche.py"


def production_argv(arguments: list[str]) -> list[str]:
    if "--strict-exact" in arguments:
        return list(arguments)
    return ["--strict-exact", *arguments]


def main() -> int:
    saved_argv = sys.argv
    try:
        sys.argv = [str(RUNNER), *production_argv(saved_argv[1:])]
        namespace = runpy.run_path(str(RUNNER), run_name="_sensiblaw_complete_tranche")
        runner_main = namespace.get("main")
        if not callable(runner_main):
            raise RuntimeError("complete tranche runner does not expose main()")
        return int(runner_main())
    finally:
        sys.argv = saved_argv


if __name__ == "__main__":
    raise SystemExit(main())
