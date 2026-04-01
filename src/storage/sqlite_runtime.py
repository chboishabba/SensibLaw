from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable


def resolve_sqlite_db_path(
    explicit_db_path: str | Path | None = None,
    *,
    env_vars: Iterable[str] = (),
    default: str | Path = ".cache_local/itir.sqlite",
) -> Path:
    candidates: list[str] = []
    if explicit_db_path is not None:
        text = str(explicit_db_path).strip()
        if text:
            candidates.append(text)
    for key in env_vars:
        value = (os.environ.get(key) or "").strip()
        if value:
            candidates.append(value)
    candidates.append(str(default))
    return Path(candidates[0]).expanduser().resolve()


def connect_sqlite(
    db_path: str | Path,
    *,
    readonly: bool = False,
    immutable: bool = False,
) -> sqlite3.Connection:
    resolved = Path(db_path).expanduser().resolve()
    if readonly:
        suffix = "?mode=ro"
        if immutable:
            suffix += "&immutable=1"
        conn = sqlite3.connect(f"file:{resolved}{suffix}", uri=True)
    else:
        conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    return conn
