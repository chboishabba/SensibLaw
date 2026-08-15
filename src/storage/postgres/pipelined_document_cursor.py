"""Pipeline synchronous PostgreSQL persistence without changing SQL order.

The ordered document savepoint remains the publication authority.  This wrapper
only removes client/server synchronization points between consecutive statements
whose results have not yet been observed.  Any fetch, row-count observation,
COPY boundary, or explicit ``sync()`` flushes the pipeline first.

The wrapper is deliberately cursor-shaped so existing persistence helpers do not
need table-specific fast paths.  On drivers/connections without psycopg3 pipeline
support it degrades to the original synchronous cursor exactly.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


class PipelinedDocumentCursor:
    """Cursor facade with demand-driven psycopg pipeline synchronization."""

    def __init__(self, cursor: Any):
        self._cursor = cursor
        self._pipeline_cm: Any | None = None
        self._pipeline: Any | None = None
        self._pending = False
        self._open_pipeline()

    @property
    def connection(self) -> Any:
        return self._cursor.connection

    def _open_pipeline(self) -> None:
        factory = getattr(self.connection, "pipeline", None)
        if not callable(factory):
            return
        self._pipeline_cm = factory()
        self._pipeline = self._pipeline_cm.__enter__()

    def _close_pipeline(
        self,
        exc_type: type[BaseException] | None = None,
        exc: BaseException | None = None,
        traceback: Any | None = None,
    ) -> None:
        cm = self._pipeline_cm
        if cm is None:
            return
        try:
            cm.__exit__(exc_type, exc, traceback)
        finally:
            self._pipeline_cm = None
            self._pipeline = None
            self._pending = False

    def sync(self) -> None:
        pipeline = self._pipeline
        if pipeline is not None and self._pending:
            pipeline.sync()
        self._pending = False

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> "PipelinedDocumentCursor":
        if params is None:
            self._cursor.execute(query, *args, **kwargs)
        else:
            self._cursor.execute(query, params, *args, **kwargs)
        self._pending = self._pipeline is not None
        return self

    def executemany(self, query: Any, params_seq: Any, *args: Any, **kwargs: Any) -> "PipelinedDocumentCursor":
        self._cursor.executemany(query, params_seq, *args, **kwargs)
        self._pending = self._pipeline is not None
        return self

    def fetchone(self) -> Any:
        self.sync()
        return self._cursor.fetchone()

    def fetchmany(self, *args: Any, **kwargs: Any) -> Any:
        self.sync()
        return self._cursor.fetchmany(*args, **kwargs)

    def fetchall(self) -> Any:
        self.sync()
        return self._cursor.fetchall()

    def __iter__(self) -> Iterator[Any]:
        self.sync()
        return iter(self._cursor)

    @property
    def rowcount(self) -> int:
        self.sync()
        return int(self._cursor.rowcount)

    @property
    def description(self) -> Any:
        self.sync()
        return self._cursor.description

    @contextmanager
    def copy(self, *args: Any, **kwargs: Any) -> Iterator[Any]:
        # psycopg COPY is not a pipeline operation.  Preserve the exact COPY
        # contract by closing the current pipeline around that boundary, then
        # start a fresh pipeline for subsequent ordinary statements.
        self.sync()
        self._close_pipeline()
        try:
            with self._cursor.copy(*args, **kwargs) as copy:
                yield copy
        finally:
            self._open_pipeline()

    def close(self) -> None:
        self._close_pipeline()
        self._cursor.close()

    def __getattr__(self, name: str) -> Any:
        # Unknown cursor attributes/methods may expose a result of the preceding
        # command.  Synchronize conservatively before delegation rather than
        # allowing an optimization to weaken driver semantics.
        self.sync()
        return getattr(self._cursor, name)

    def __enter__(self) -> "PipelinedDocumentCursor":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any | None,
    ) -> None:
        self._close_pipeline(exc_type, exc, traceback)


__all__ = ["PipelinedDocumentCursor"]
