from __future__ import annotations

import os
from urllib.parse import urlparse
import requests

from src.citations.normalize import jade_content_ext_url, normalize_mnc

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
        self.api_base = api_base or os.environ.get("JADE_API_BASE", "https://jade.barnet.com.au")
        self.api_key = api_key or os.environ.get("JADE_API_KEY")
        self.limiter = limiter or TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1))
        self.session = session or requests.Session()
        self.user_agent = user_agent or "SensibLaw/0.1 (+https://sensiblaw.local)"
        self.timeout_s = timeout_s

    def fetch(self, citation: str) -> FetchResult:
        self.limiter.acquire()

        url = self._resolve_url(citation)
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

    def _resolve_url(self, citation: str) -> str:
        value = (citation or "").strip()
        if not value:
            raise ValueError("citation must be provided")

        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            if not parsed.netloc.endswith(("jade.io", "jade.barnet.com.au")):
                raise ValueError(f"Not a JADE URL: {citation}")
            return value

        key = normalize_mnc(value)
        if key is not None:
            return jade_content_ext_url(key, base=self.api_base)

        return f"{self.api_base.rstrip('/')}/api/doc/{value}"
