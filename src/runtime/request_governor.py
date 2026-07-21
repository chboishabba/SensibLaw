"""Reusable host-aware request pacing for bounded acquisition workers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import random
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse


REQUEST_GOVERNOR_CONTRACT = "request-governor:v0_1"


class Clock(Protocol):
    def __call__(self) -> float: ...


class Sleeper(Protocol):
    def __call__(self, seconds: float) -> None: ...


@dataclass(frozen=True)
class RequestGovernorPolicy:
    minimum_interval_seconds: float = 1.0
    maximum_attempts: int = 3
    backoff_seconds: float = 2.0
    jitter_seconds: float = 0.25
    request_budget: int = 64

    def __post_init__(self) -> None:
        if self.minimum_interval_seconds < 0:
            raise ValueError("minimum_interval_seconds must be nonnegative")
        if self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be positive")
        if self.backoff_seconds < 0 or self.jitter_seconds < 0:
            raise ValueError("backoff and jitter must be nonnegative")
        if self.request_budget < 1:
            raise ValueError("request_budget must be positive")


@dataclass(frozen=True)
class RequestAttemptReceipt:
    url: str
    host: str
    attempt: int
    state: str
    elapsed_seconds: float
    error_type: str | None = None
    error_detail: str | None = None
    contract_ref: str = REQUEST_GOVERNOR_CONTRACT

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value not in (None, "")
        }


class RequestGovernor:
    """Pace requests per host, enforce a total budget, and retain attempt receipts."""

    def __init__(
        self,
        policy: RequestGovernorPolicy | None = None,
        *,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self.policy = policy or RequestGovernorPolicy()
        self._clock = clock
        self._sleep = sleeper
        self._random = random_value
        self._last_started_by_host: dict[str, float] = {}
        self._request_count = 0
        self._receipts: list[RequestAttemptReceipt] = []

    @property
    def receipts(self) -> tuple[RequestAttemptReceipt, ...]:
        return tuple(self._receipts)

    @property
    def request_count(self) -> int:
        return self._request_count

    def _host(self, url: str) -> str:
        return str(urlparse(url).hostname or "").casefold()

    def _wait_for_host(self, host: str) -> None:
        previous = self._last_started_by_host.get(host)
        if previous is None:
            return
        remaining = self.policy.minimum_interval_seconds - (self._clock() - previous)
        if remaining > 0:
            self._sleep(remaining)

    def call(self, url: str, operation: Callable[[], Any]) -> Any:
        host = self._host(url)
        last_error: Exception | None = None
        for attempt in range(1, self.policy.maximum_attempts + 1):
            if self._request_count >= self.policy.request_budget:
                raise RuntimeError("request governor budget exhausted")
            self._wait_for_host(host)
            started = self._clock()
            self._last_started_by_host[host] = started
            self._request_count += 1
            try:
                result = operation()
            except Exception as error:  # noqa: BLE001 - receipt must preserve worker failure
                last_error = error
                elapsed = self._clock() - started
                self._receipts.append(
                    RequestAttemptReceipt(
                        url=url,
                        host=host,
                        attempt=attempt,
                        state="failed",
                        elapsed_seconds=elapsed,
                        error_type=type(error).__name__,
                        error_detail=str(error),
                    )
                )
                if attempt == self.policy.maximum_attempts:
                    raise
                delay = self.policy.backoff_seconds * (2 ** (attempt - 1))
                delay += self.policy.jitter_seconds * self._random()
                self._sleep(delay)
                continue
            elapsed = self._clock() - started
            self._receipts.append(
                RequestAttemptReceipt(
                    url=url,
                    host=host,
                    attempt=attempt,
                    state="completed",
                    elapsed_seconds=elapsed,
                )
            )
            return result
        assert last_error is not None
        raise last_error

    def summary(self) -> Mapping[str, Any]:
        return {
            "contract_ref": REQUEST_GOVERNOR_CONTRACT,
            "request_count": self.request_count,
            "request_budget": self.policy.request_budget,
            "attempts": [row.to_dict() for row in self.receipts],
            "authority": "request_execution_receipt_only",
        }


__all__ = [
    "REQUEST_GOVERNOR_CONTRACT",
    "RequestAttemptReceipt",
    "RequestGovernor",
    "RequestGovernorPolicy",
]
