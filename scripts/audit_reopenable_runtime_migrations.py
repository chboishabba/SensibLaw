#!/usr/bin/env python3
"""Static source audit for the reopenable numeric runtime migrations 086-089.

This script itself is source-analysis tooling, so regex is an explicit boundary
exception: it parses SQL *source text* and never participates in semantic
execution over corpus content.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "postgres_migrations"
TARGETS = (
    "086_consumer_indexed_reopenable_runtime.sql",
    "087_reopenable_runtime_hardening.sql",
    "088_progressive_reopenable_resolution.sql",
    "089_numeric_incremental_runtime_economy.sql",
)

IDENTIFIER = re.compile(r"\bexecution\.([a-zA-Z_][a-zA-Z0-9_]*)\b")
DEFINITION = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?"
    r"(?:TABLE|VIEW|MATERIALIZED\s+VIEW|FUNCTION|PROCEDURE)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?execution\.([a-zA-Z_][a-zA-Z0-9_]*)\b",
    re.IGNORECASE,
)


def migration_sources() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(MIGRATIONS.glob("*.sql"))
    }


def audit() -> tuple[set[str], dict[str, tuple[str, ...]]]:
    sources = migration_sources()
    defined_by: dict[str, list[str]] = {}
    for filename, text in sources.items():
        for name in DEFINITION.findall(text):
            defined_by.setdefault(name.lower(), []).append(filename)

    referenced: set[str] = set()
    for filename in TARGETS:
        text = sources[filename]
        referenced.update(name.lower() for name in IDENTIFIER.findall(text))

    missing = referenced.difference(defined_by)
    provenance = {
        name: tuple(defined_by[name])
        for name in sorted(referenced)
        if name in defined_by
    }
    return missing, provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-provenance", action="store_true")
    args = parser.parse_args()
    missing, provenance = audit()
    if args.show_provenance:
        for name, filenames in provenance.items():
            print(f"execution.{name}: {', '.join(filenames)}")
    if missing:
        for name in sorted(missing):
            print(f"MISSING execution.{name}")
        return 1
    print(f"OK: {len(provenance)} execution-schema dependencies are source-defined")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
