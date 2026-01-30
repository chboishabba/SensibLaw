from __future__ import annotations

from urllib.parse import urlparse

from .base import FetchResult
from .rate_limit import RateLimit, TokenBucketRateLimiter


class AustLiiFetchAdapter:
    source_name = "austlii.fetch"

    def __init__(
        self,
        limiter: TokenBucketRateLimiter | None = None,
        session=None,
        user_agent: str | None = None,
        timeout_s: float = 30.0,
    ):
        import requests  # lazy import

        self.limiter = limiter or TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1))
        self.session = session or requests.Session()
        self.user_agent = user_agent or "SensibLaw/0.1 (+https://sensiblaw.local)"
        self.timeout_s = timeout_s

    def fetch(self, url: str) -> FetchResult:
        parsed = urlparse(url)
        if not parsed.netloc.endswith("austlii.edu.au"):
            raise ValueError(f"Not an AustLII URL: {url}")

        self.limiter.acquire()

        resp = self.session.get(url, headers={"User-Agent": self.user_agent}, timeout=self.timeout_s)
        resp.raise_for_status()
        return FetchResult(
            content=resp.content,
            content_type=resp.headers.get("Content-Type"),
            url=url,
            metadata={
                "source": "austlii",
                "path": parsed.path,
                "status_code": resp.status_code,
            },
        )
