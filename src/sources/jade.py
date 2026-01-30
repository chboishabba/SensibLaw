from __future__ import annotations

import os
import requests

from .base import FetchResult
from .rate_limit import RateLimit, TokenBucketRateLimiter


class JadeAdapter:
    """Adapter for jade.io-like legal document endpoints (skeleton).

    Fetches raw bytes + provenance only; no semantics.
    """

    source_name = "jade.io"

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        limiter: TokenBucketRateLimiter | None = None,
        session: requests.Session | None = None,
        user_agent: str | None = None,
        timeout_s: float = 30.0,
    ):
        self.api_base = api_base or os.environ.get("JADE_API_BASE", "https://jade.io")
        self.api_key = api_key or os.environ.get("JADE_API_KEY")
        self.limiter = limiter or TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1))
        self.session = session or requests.Session()
        self.user_agent = user_agent or "SensibLaw/0.1 (+https://sensiblaw.local)"
        self.timeout_s = timeout_s

    def fetch(self, citation: str) -> FetchResult:
        self.limiter.acquire()

        url = f"{self.api_base.rstrip('/')}/api/doc/{citation}"
        headers = {"User-Agent": self.user_agent}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        resp = self.session.get(url, headers=headers, timeout=self.timeout_s)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type")
        return FetchResult(
            content=resp.content,
            content_type=content_type,
            url=url,
            metadata={
                "source": self.source_name,
                "citation": citation,
                "content_type": content_type,
                "status_code": resp.status_code,
            },
        )
