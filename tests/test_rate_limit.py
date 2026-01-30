from __future__ import annotations

from src.sources.rate_limit import RateLimit, TokenBucketRateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, dt: float) -> None:
        self.sleeps.append(dt)
        self.t += dt


def test_rate_limiter_allows_burst():
    c = FakeClock()
    rl = TokenBucketRateLimiter(RateLimit(rps=1.0, burst=2), now=c.now, sleep=c.sleep)

    rl.acquire()
    rl.acquire()
    assert c.sleeps == []  # within burst, no waiting


def test_rate_limiter_waits_after_burst():
    c = FakeClock()
    rl = TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1), now=c.now, sleep=c.sleep)

    rl.acquire()  # consumes burst
    rl.acquire()  # must wait
    assert len(c.sleeps) == 1
    assert abs(c.sleeps[0] - 1.0) < 1e-9


def test_rate_limiter_refills_over_time():
    c = FakeClock()
    rl = TokenBucketRateLimiter(RateLimit(rps=2.0, burst=1), now=c.now, sleep=c.sleep)

    rl.acquire()  # tokens -> 0
    c.t += 0.5   # refill 1 token at 2 rps * 0.5s
    rl.acquire()  # should not sleep
    assert c.sleeps == []
