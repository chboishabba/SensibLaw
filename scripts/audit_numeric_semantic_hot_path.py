#!/usr/bin/env python3
"""Fail-closed audit for the post-tokenisation semantic hot path.

Regex remains legitimate in explicitly boundary-oriented ingestion/citation/source
parsers.  This audit targets the compiled PNF runtime and reusable semantic cue
surface, where regex/string matching must plead an explicit boundary case.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOT_PYTHON = (
    ROOT / "src" / "policy" / "numeric_cue_automaton.py",
    ROOT / "src" / "policy" / "relative_octant_codec.py",
    ROOT / "src" / "policy" / "reopenable_runtime.py",
    ROOT / "src" / "text" / "phrase_cues.py",
)
HOT_SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "089_numeric_incremental_runtime_economy.sql",
    ROOT
    / "database"
    / "postgres_migrations"
    / "090_numeric_parser_evidence_and_learning.sql",
)

PYTHON_FORBIDDEN = (
    "import re",
    "from re import",
    "re.compile(",
    "re.search(",
    "re.match(",
)
SQL_REGEX_FORBIDDEN = (" SIMILAR TO ", " ~ ", " ~* ")


def audit() -> list[str]:
    failures: list[str] = []
    for path in HOT_PYTHON:
        text = path.read_text(encoding="utf-8")
        for marker in PYTHON_FORBIDDEN:
            if marker in text:
                failures.append(
                    f"{path.relative_to(ROOT)}: forbidden semantic regex marker {marker!r}"
                )

    for path in HOT_SQL:
        text = path.read_text(encoding="utf-8")
        upper = text.upper()
        for marker in SQL_REGEX_FORBIDDEN:
            if marker.upper() in upper:
                failures.append(
                    f"{path.relative_to(ROOT)}: forbidden SQL regex operator {marker!r}"
                )

    # Expensive 083 functions are redeclared in 089/090.  The replacement
    # identity-evidence function must not join semantic_symbol merely to compare
    # a token's POS/dependency/entity/cue label at document scale.
    replacement = HOT_SQL[1].read_text(encoding="utf-8")
    numeric_required = (
        "semantic_pnf_hot_symbol_constant",
        "semantic_pnf_hot_cue_symbol",
        "token.pos_symbol_id=constant.propn_id",
        "source_token.dependency_symbol_id=constant.appos_id",
        "entity.entity_type_symbol_id=constant.person_id",
    )
    for marker in numeric_required:
        if marker not in replacement:
            failures.append(f"090 numeric parser evidence missing {marker!r}")
    return failures


def main() -> int:
    failures = audit()
    if failures:
        for failure in failures:
            print(f"SIN-BIN: {failure}")
        return 1
    print(
        "OK: semantic hot-path audit found no regex execution and numeric parser cues are compiled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
