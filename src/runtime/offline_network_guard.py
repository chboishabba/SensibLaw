"""Process-local guard proving that an offline build attempted no sockets."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
import socket
from types import TracebackType
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


class OfflineNetworkViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class NetworkAbsenceReceipt:
    guard_ref: str
    attempted_connections: tuple[str, ...]

    @property
    def receipt_ref(self) -> str:
        return "network-absence-receipt:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref,
            **asdict(self),
            "network_attempt_count": len(self.attempted_connections),
            "network_absent": not self.attempted_connections,
        }


class OfflineNetworkGuard(AbstractContextManager["OfflineNetworkGuard"]):
    """Reject socket creation during deterministic catalogue/parity execution."""

    def __init__(self, *, guard_ref: str = "offline-curated-legal-ir:v0_1") -> None:
        self.guard_ref = guard_ref
        self._attempts: list[str] = []
        self._original_create_connection = socket.create_connection
        self._original_connect = socket.socket.connect

    def _block_create_connection(self, address: Any, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        self._attempts.append(repr(address))
        raise OfflineNetworkViolation(f"offline build attempted network access: {address!r}")

    def _block_connect(self, instance: socket.socket, address: Any) -> Any:
        del instance
        self._attempts.append(repr(address))
        raise OfflineNetworkViolation(f"offline build attempted network access: {address!r}")

    def __enter__(self) -> "OfflineNetworkGuard":
        socket.create_connection = self._block_create_connection  # type: ignore[assignment]
        socket.socket.connect = self._block_connect  # type: ignore[method-assign]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        del exc_type, exc_value, traceback
        socket.create_connection = self._original_create_connection
        socket.socket.connect = self._original_connect  # type: ignore[method-assign]
        return None

    @property
    def receipt(self) -> NetworkAbsenceReceipt:
        return NetworkAbsenceReceipt(
            guard_ref=self.guard_ref,
            attempted_connections=tuple(self._attempts),
        )


__all__ = [
    "NetworkAbsenceReceipt",
    "OfflineNetworkGuard",
    "OfflineNetworkViolation",
]
