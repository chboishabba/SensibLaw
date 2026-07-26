from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_active_docs_do_not_invoke_internal_cli_module() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]

    internal_invocation = re.compile(
        r"(?m)^\s*(?:[-*]\s+`?)?(?:\S*/)?python -m cli\.__main__\b"
    )
    offenders = []
    for path in paths:
        if internal_invocation.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_active_docs_do_not_advertise_console_alias_as_command() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]

    console_invocation = re.compile(r"(?m)^\s*(?:[-*]\s+`?)?sensiblaw\s+[a-z]")
    offenders = []
    for path in paths:
        if console_invocation.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_authority_map_records_all_migration_tracks() -> None:
    text = (ROOT / "docs" / "authority_surfaces.md").read_text(encoding="utf-8")

    for path in (
        "database/postgres_migrations/",
        "database/migrations/",
        "migrations/",
        "schemas/migrations/",
    ):
        assert path in text
