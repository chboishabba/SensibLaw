#!/usr/bin/env python3
"""Audit the composed PostgreSQL migration chain before provisioning.

The audit models *final active trigger ownership*, rather than treating every
historical migration as simultaneously authoritative.  It also reports recurring
hot-path churn shapes so new migrations cannot silently reintroduce them.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DROP_TRIGGER = re.compile(
    r"DROP\s+TRIGGER\s+IF\s+EXISTS\s+(?P<name>[A-Za-z_][\w$]*)\s+ON\s+"
    r"(?P<table>(?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)\s*;",
    re.IGNORECASE,
)
CREATE_TRIGGER = re.compile(
    r"CREATE\s+TRIGGER\s+(?P<name>[A-Za-z_][\w$]*)\s+"
    r"(?P<body>.*?)\bON\s+(?P<table>(?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)\s+"
    r"(?P<tail>.*?)(?:EXECUTE|CALL)\s+(?:FUNCTION|PROCEDURE)\s+"
    r"(?P<function>(?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)\s*\(",
    re.IGNORECASE | re.DOTALL,
)
ROW_LEVEL = re.compile(r"FOR\s+EACH\s+ROW", re.IGNORECASE)
STATEMENT_LEVEL = re.compile(r"FOR\s+EACH\s+STATEMENT", re.IGNORECASE)
DELETE_INSERT = re.compile(
    r"DELETE\s+FROM\s+(?P<table>(?:execution\.)?semantic_pnf_[A-Za-z_][\w$]*)"
    r"(?:(?!\$\$).)*?INSERT\s+INTO\s+(?P=table)",
    re.IGNORECASE | re.DOTALL,
)

# These relations have explicit statement-level owners in the current runtime.
FORBIDDEN_FINAL_ROW_TRIGGER_TABLES = {
    "execution.semantic_pnf_demand_candidate",
    "execution.semantic_pnf_candidate_execution_event",
    "execution.semantic_pnf_candidate_admissibility_event",
    "execution.semantic_pnf_candidate_preference",
}

# Append-only history guards are intentionally row-level: they reject UPDATE
# of immutable history and do not project rows into another relation.  They
# must not be confused with the row-level hot-path projection triggers this
# audit is intended to catch.
APPEND_ONLY_GUARD_FUNCTIONS = {
    "execution.reject_numeric_pnf_runtime_history_update",
}


@dataclass(frozen=True, slots=True)
class TriggerOwner:
    migration: str
    name: str
    table: str
    function: str
    level: str


def _canonical_table(value: str) -> str:
    return value if "." in value else f"public.{value}"


def audit_migrations(paths: Iterable[Path]) -> dict[str, object]:
    active: dict[tuple[str, str], TriggerOwner] = {}
    fatal: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    ordered = sorted(paths, key=lambda path: path.name)
    for path in ordered:
        sql = path.read_text(encoding="utf-8")
        events: list[tuple[int, str, re.Match[str]]] = []
        events.extend((m.start(), "drop", m) for m in DROP_TRIGGER.finditer(sql))
        events.extend((m.start(), "create", m) for m in CREATE_TRIGGER.finditer(sql))
        for _offset, kind, match in sorted(events, key=lambda item: item[0]):
            table = _canonical_table(match.group("table"))
            key = (table.lower(), match.group("name").lower())
            if kind == "drop":
                active.pop(key, None)
                continue

            previous = active.get(key)
            if previous is not None:
                fatal.append(
                    {
                        "kind": "trigger-owner-collision",
                        "migration": path.name,
                        "table": table,
                        "trigger": match.group("name"),
                        "previous_migration": previous.migration,
                    }
                )
            text = match.group(0)
            level = "row" if ROW_LEVEL.search(text) else (
                "statement" if STATEMENT_LEVEL.search(text) else "unspecified"
            )
            active[key] = TriggerOwner(
                migration=path.name,
                name=match.group("name"),
                table=table,
                function=match.group("function"),
                level=level,
            )

        for match in DELETE_INSERT.finditer(sql):
            warnings.append(
                {
                    "kind": "delete-reinsert-same-relation",
                    "migration": path.name,
                    "table": _canonical_table(match.group("table")),
                }
            )

    for owner in active.values():
        if (
            owner.table.lower() in FORBIDDEN_FINAL_ROW_TRIGGER_TABLES
            and owner.level == "row"
            and owner.function.lower() not in APPEND_ONLY_GUARD_FUNCTIONS
        ):
            fatal.append(
                {
                    "kind": "forbidden-final-row-trigger",
                    "migration": owner.migration,
                    "table": owner.table,
                    "trigger": owner.name,
                    "function": owner.function,
                }
            )

    return {
        "contract_ref": "sensiblaw.pg-migration-runtime-audit.v0_1",
        "migration_count": len(ordered),
        "active_trigger_count": len(active),
        "fatal_count": len(fatal),
        "warning_count": len(warnings),
        "fatal": fatal,
        "warnings": warnings,
        "active_triggers": [
            {
                "migration": owner.migration,
                "name": owner.name,
                "table": owner.table,
                "function": owner.function,
                "level": owner.level,
            }
            for owner in sorted(active.values(), key=lambda x: (x.table, x.name))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "migrations_dir",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "database" / "postgres_migrations",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = audit_migrations(args.migrations_dir.glob("*.sql"))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 2 if report["fatal_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
