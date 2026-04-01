from __future__ import annotations

import sqlite3
from pathlib import Path

from src.storage.sqlite_runtime import connect_sqlite, resolve_sqlite_db_path


def test_resolve_sqlite_db_path_prefers_explicit_then_env(monkeypatch, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.sqlite"
    env_path = tmp_path / "env.sqlite"
    monkeypatch.setenv("ITIR_DB_PATH", str(env_path))
    assert resolve_sqlite_db_path(str(explicit), env_vars=("ITIR_DB_PATH",)) == explicit.resolve()
    assert resolve_sqlite_db_path(None, env_vars=("ITIR_DB_PATH",)) == env_path.resolve()


def test_connect_sqlite_opens_readonly_and_sets_row_factory(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE demo(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO demo(value) VALUES (?)", ("hello",))

    with connect_sqlite(db_path, readonly=True, immutable=True) as conn:
        row = conn.execute("SELECT value FROM demo").fetchone()
        assert row["value"] == "hello"
