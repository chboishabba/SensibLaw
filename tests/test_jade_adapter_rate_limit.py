from __future__ import annotations

from types import SimpleNamespace

from src.sources.jade import JadeAdapter
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


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, headers, timeout):
        self.calls += 1
        return SimpleNamespace(
            status_code=200,
            content=b"%PDF-1.4 fake",
            headers={"Content-Type": "application/pdf"},
            raise_for_status=lambda: None,
        )


def test_jade_adapter_respects_rate_limit():
    c = FakeClock()
    limiter = TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1), now=c.now, sleep=c.sleep)
    session = FakeSession()

    adapter = JadeAdapter(api_base="https://jade.io", limiter=limiter, session=session)

    adapter.fetch("X")
    adapter.fetch("Y")

    assert session.calls == 2
    assert len(c.sleeps) == 1  # second call waited


def test_jade_adapter_normalizes_mnc_to_content_ext_url():
    session = FakeSession()
    adapter = JadeAdapter(api_base="https://jade.barnet.com.au", session=session)
    result = adapter.fetch("[2011] HCA 1")
    assert result.url.endswith("/content/ext/mnc/2011/hca/1")


def test_jade_adapter_allows_explicit_jade_url():
    session = FakeSession()
    adapter = JadeAdapter(session=session)
    result = adapter.fetch("https://jade.barnet.com.au/content/ext/mnc/2011/hca/1")
    assert result.url == "https://jade.barnet.com.au/content/ext/mnc/2011/hca/1"
