"""Small reusable psycopg pools for document-persistence execution lanes.

These connections carry execution-only, rebuildable staging and telemetry rows;
they never publish semantic authority. Each COPY lease still owns an independent
PostgreSQL transaction. By default those execution transactions use
``synchronous_commit=off`` so the coordinator does not wait for WAL flush on
rows whose only crash contract is recomputation. The ordered document authority
connection is separate and retains its normal durability.
"""

from __future__ import annotations

import atexit
from contextlib import contextmanager
import os
from queue import Empty, LifoQueue
from threading import Lock
from typing import Any, Iterator


def _async_stage_commit_enabled() -> bool:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_ASYNC_STAGE_COMMIT", "1")
    return raw.strip().lower() not in {"0", "false", "no", "off"}


class _ReusablePool:
    def __init__(self, dsn: str, *, max_size: int):
        self.dsn = dsn
        self.max_size = max(1, max_size)
        self._idle: LifoQueue[Any] = LifoQueue()
        self._created = 0
        self._lock = Lock()

    def _connect(self) -> Any:
        import psycopg  # type: ignore[import-not-found]

        return psycopg.connect(self.dsn)

    def _take(self) -> Any:
        try:
            connection = self._idle.get_nowait()
        except Empty:
            with self._lock:
                if self._created < self.max_size:
                    self._created += 1
                    try:
                        return self._connect()
                    except BaseException:
                        self._created -= 1
                        raise
            connection = self._idle.get()
        if getattr(connection, "closed", False):
            with self._lock:
                self._created = max(0, self._created - 1)
            return self._take()
        return connection

    def _discard(self, connection: Any) -> None:
        try:
            connection.close()
        finally:
            with self._lock:
                self._created = max(0, self._created - 1)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        connection = self._take()
        reusable = True
        try:
            with connection.transaction():
                if _async_stage_commit_enabled():
                    # This connection never carries authority tables. A host/DB
                    # crash can lose a recently acknowledged staging transaction;
                    # the deterministic stage is simply recomputed on restart.
                    connection.execute("SET LOCAL synchronous_commit TO off")
                yield connection
        except BaseException:
            if getattr(connection, "closed", False) or getattr(
                connection, "broken", False
            ):
                reusable = False
            raise
        finally:
            if reusable and not getattr(connection, "closed", False):
                self._idle.put(connection)
            else:
                self._discard(connection)

    def close(self) -> None:
        while True:
            try:
                connection = self._idle.get_nowait()
            except Empty:
                break
            try:
                connection.close()
            finally:
                with self._lock:
                    self._created = max(0, self._created - 1)


class _TelemetryConnection:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._connection: Any | None = None
        self._lock = Lock()

    def _connect(self) -> Any:
        import psycopg  # type: ignore[import-not-found]

        connection = psycopg.connect(self.dsn, autocommit=True)
        if _async_stage_commit_enabled():
            connection.execute("SET synchronous_commit TO off")
        return connection

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        with self._lock:
            connection = self._connection
            if connection is None or getattr(connection, "closed", False):
                connection = self._connect()
                self._connection = connection
            try:
                with connection.cursor() as cursor:
                    yield cursor
            except BaseException:
                if getattr(connection, "closed", False) or getattr(
                    connection, "broken", False
                ):
                    try:
                        connection.close()
                    except Exception:
                        pass
                    self._connection = None
                raise

    def close(self) -> None:
        with self._lock:
            connection = self._connection
            self._connection = None
        if connection is not None:
            connection.close()


_POOLS: dict[str, _ReusablePool] = {}
_TELEMETRY: dict[str, _TelemetryConnection] = {}
_REGISTRY_LOCK = Lock()


def _pool_size() -> int:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_CONNECTION_POOL_MAX", "8")
    value = int(raw)
    if value < 1:
        raise ValueError("SENSIBLAW_PERSISTENCE_CONNECTION_POOL_MAX must be positive")
    return value


def transactional_persistence_connection(dsn: str) -> Any:
    with _REGISTRY_LOCK:
        pool = _POOLS.get(dsn)
        if pool is None:
            pool = _ReusablePool(dsn, max_size=_pool_size())
            _POOLS[dsn] = pool
    return pool.transaction()


def persistence_telemetry_cursor(dsn: str) -> Any:
    with _REGISTRY_LOCK:
        telemetry = _TELEMETRY.get(dsn)
        if telemetry is None:
            telemetry = _TelemetryConnection(dsn)
            _TELEMETRY[dsn] = telemetry
    return telemetry.cursor()


def close_reusable_persistence_connections() -> None:
    with _REGISTRY_LOCK:
        pools = tuple(_POOLS.values())
        telemetry = tuple(_TELEMETRY.values())
        _POOLS.clear()
        _TELEMETRY.clear()
    for value in pools:
        value.close()
    for value in telemetry:
        value.close()


atexit.register(close_reusable_persistence_connections)


__all__ = [
    "close_reusable_persistence_connections",
    "persistence_telemetry_cursor",
    "transactional_persistence_connection",
]
