"""Process-local guard proving that an offline build attempted no external network."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
import socket
from types import TracebackType
from typing import Any, Callable

from src.policy.carriers.canonical import canonical_sha256


class OfflineNetworkViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class NetworkAbsenceReceipt:
    guard_ref: str
    allowed_connections: tuple[str, ...]
    blocked_connections: tuple[str, ...]

    @property
    def receipt_ref(self) -> str:
        return "network-absence-receipt:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref,
            **asdict(self),
            "network_attempt_count": len(self.blocked_connections),
            "external_network_absent": not self.blocked_connections,
            "allowed_local_connection_count": len(self.allowed_connections),
        }


class OfflineNetworkGuard(AbstractContextManager["OfflineNetworkGuard"]):
    """Reject external sockets while allowing explicitly declared local services."""

    def __init__(
        self,
        *,
        guard_ref: str = "offline-curated-legal-ir:v0_2",
        allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "::1"),
    ) -> None:
        self.guard_ref = guard_ref
        self.allowed_hosts = frozenset(allowed_hosts)
        self._allowed: list[str] = []
        self._blocked: list[str] = []
        self._original_create_connection = socket.create_connection
        self._original_connect = socket.socket.connect
        self._patched_create_connection: Callable[..., Any] | None = None
        self._patched_connect: Callable[..., Any] | None = None

    def _is_allowed(self, address: Any) -> bool:
        if isinstance(address, str):
            return address.startswith("/")
        if isinstance(address, tuple) and address:
            return str(address[0]) in self.allowed_hosts
        return False

    def __enter__(self) -> "OfflineNetworkGuard":
        guard = self

        def guarded_create_connection(
            address: Any,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if guard._is_allowed(address):
                guard._allowed.append(repr(address))
                return guard._original_create_connection(address, *args, **kwargs)
            guard._blocked.append(repr(address))
            raise OfflineNetworkViolation(
                f"offline build attempted external access: {address!r}"
            )

        def guarded_connect(instance: socket.socket, address: Any) -> Any:
            if guard._is_allowed(address):
                guard._allowed.append(repr(address))
                return guard._original_connect(instance, address)
            guard._blocked.append(repr(address))
            raise OfflineNetworkViolation(
                f"offline build attempted external access: {address!r}"
            )

        self._patched_create_connection = guarded_create_connection
        self._patched_connect = guarded_connect
        socket.create_connection = guarded_create_connection
        socket.socket.connect = guarded_connect  # type: ignore[method-assign]
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
        self._patched_create_connection = None
        self._patched_connect = None
        return None

    @property
    def receipt(self) -> NetworkAbsenceReceipt:
        return NetworkAbsenceReceipt(
            guard_ref=self.guard_ref,
            allowed_connections=tuple(self._allowed),
            blocked_connections=tuple(self._blocked),
        )


__all__ = [
    "NetworkAbsenceReceipt",
    "OfflineNetworkGuard",
    "OfflineNetworkViolation",
]
