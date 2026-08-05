"""Renewable PostgreSQL coordinator authority for strict document runs."""

from __future__ import annotations

from dataclasses import dataclass
import os
from threading import Event, Thread
from typing import Any
from uuid import uuid4


class CoordinatorLeaseLost(RuntimeError):
    pass


def _connect(database_url: str) -> Any:
    import psycopg

    return psycopg.connect(database_url, autocommit=False)


@dataclass(frozen=True)
class CoordinatorLease:
    run_ref: str
    coordinator_ref: str
    token: str
    epoch: int
    lease_seconds: int


class CoordinatorLeaseGuard:
    """Acquire, renew and release one coordinator lease for a run.

    Renewal occurs on an independent connection so a long worker frontier or
    finalisation transaction cannot starve the authority heartbeat.
    """

    def __init__(
        self,
        *,
        database_url: str,
        run_ref: str,
        lease_seconds: int = 90,
        coordinator_ref: str | None = None,
    ) -> None:
        if lease_seconds < 3:
            raise ValueError("coordinator lease must be at least three seconds")
        self.database_url = database_url
        self.run_ref = run_ref
        self.lease_seconds = lease_seconds
        self.coordinator_ref = coordinator_ref or (
            f"coordinator:{run_ref}:{os.getpid()}:{uuid4().hex}"
        )
        self.lease: CoordinatorLease | None = None
        self._stop = Event()
        self._lost = Event()
        self._thread: Thread | None = None

    def acquire(self) -> CoordinatorLease:
        connection = _connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    token = uuid4().hex
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_coordinator_lease
                            (run_ref, coordinator_ref, lease_token,
                             lease_expires_at, backend_pid)
                        VALUES (%s, %s, %s,
                                CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                                pg_backend_pid())
                        ON CONFLICT (run_ref) DO UPDATE SET
                            coordinator_ref = EXCLUDED.coordinator_ref,
                            lease_token = EXCLUDED.lease_token,
                            lease_epoch = execution.semantic_coordinator_lease.lease_epoch + 1,
                            lease_expires_at = EXCLUDED.lease_expires_at,
                            heartbeat_at = CURRENT_TIMESTAMP,
                            backend_pid = EXCLUDED.backend_pid,
                            acquired_at = CURRENT_TIMESTAMP
                        WHERE execution.semantic_coordinator_lease.lease_expires_at
                              < CURRENT_TIMESTAMP
                        RETURNING lease_token, lease_epoch
                        """,
                        (
                            self.run_ref,
                            self.coordinator_ref,
                            token,
                            self.lease_seconds,
                        ),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise CoordinatorLeaseLost(
                            f"coordinator lease already held for {self.run_ref}"
                        )
                    self.lease = CoordinatorLease(
                        run_ref=self.run_ref,
                        coordinator_ref=self.coordinator_ref,
                        token=str(row[0]),
                        epoch=int(row[1]),
                        lease_seconds=self.lease_seconds,
                    )
                    return self.lease
        finally:
            connection.close()

    def renew(self) -> bool:
        lease = self.lease
        if lease is None:
            return False
        connection = _connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE execution.semantic_coordinator_lease
                        SET lease_expires_at = CURRENT_TIMESTAMP
                                + (%s * INTERVAL '1 second'),
                            heartbeat_at = CURRENT_TIMESTAMP,
                            backend_pid = pg_backend_pid()
                        WHERE run_ref = %s AND coordinator_ref = %s
                          AND lease_token = %s AND lease_epoch = %s
                        """,
                        (
                            lease.lease_seconds,
                            lease.run_ref,
                            lease.coordinator_ref,
                            lease.token,
                            lease.epoch,
                        ),
                    )
                    return cursor.rowcount == 1
        finally:
            connection.close()

    def assert_current(self) -> None:
        if self._lost.is_set() or self.lease is None:
            raise CoordinatorLeaseLost(f"coordinator lease lost for {self.run_ref}")

    def release(self) -> None:
        lease = self.lease
        if lease is None:
            return
        connection = _connect(self.database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM execution.semantic_coordinator_lease
                        WHERE run_ref = %s AND coordinator_ref = %s
                          AND lease_token = %s AND lease_epoch = %s
                        """,
                        (
                            lease.run_ref,
                            lease.coordinator_ref,
                            lease.token,
                            lease.epoch,
                        ),
                    )
        finally:
            connection.close()
        self.lease = None

    def _heartbeat(self) -> None:
        interval = max(1.0, self.lease_seconds / 3)
        while not self._stop.wait(interval):
            try:
                if not self.renew():
                    self._lost.set()
                    return
            except Exception:
                self._lost.set()
                return

    def __enter__(self) -> "CoordinatorLeaseGuard":
        self.acquire()
        self._stop.clear()
        self._lost.clear()
        self._thread = Thread(
            target=self._heartbeat,
            name=f"semantic-coordinator-heartbeat:{self.run_ref}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.lease_seconds / 2))
            self._thread = None
        if exc is None:
            self.assert_current()
        self.release()


__all__ = [
    "CoordinatorLease",
    "CoordinatorLeaseGuard",
    "CoordinatorLeaseLost",
]
