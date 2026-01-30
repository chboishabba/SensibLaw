from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class RateLimit:
    """Simple rate limit config.

    rps: requests per second (float, e.g. 1.0 = one request per second)
    burst: maximum tokens available instantly
    """

    rps: float = 1.0
    burst: int = 1


class TokenBucketRateLimiter:
    """Deterministic token bucket limiter.

    Supports dependency injection of clock/sleep for unit tests.
    """

    def __init__(self, cfg: RateLimit, now=time.monotonic, sleep=time.sleep):
        if cfg.rps <= 0:
            raise ValueError("rps must be > 0")
        if cfg.burst <= 0:
            raise ValueError("burst must be > 0")
        self.cfg = cfg
        self._now = now
        self._sleep = sleep
        self._lock = Lock()
        self._tokens = float(cfg.burst)
        self._last = self._now()

    def acquire(self, tokens: float = 1.0) -> None:
        if tokens <= 0:
            return
        with self._lock:
            while True:
                now = self._now()
                elapsed = max(0.0, now - self._last)
                self._last = now

                # refill tokens
                self._tokens = min(float(self.cfg.burst), self._tokens + elapsed * self.cfg.rps)

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                deficit = tokens - self._tokens
                wait_s = deficit / self.cfg.rps
                self._sleep(wait_s)
