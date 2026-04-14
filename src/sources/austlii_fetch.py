from __future__ import annotations

from urllib.parse import urlparse

from .base import FetchResult
from .rate_limit import RateLimit, TokenBucketRateLimiter
from src.tools.network_progress import TransferProgressReporter


class AustLiiFetchAdapter:
    source_name = "austlii.fetch"

    def __init__(
        self,
        limiter: TokenBucketRateLimiter | None = None,
        session=None,
        user_agent: str | None = None,
        timeout_s: float = 30.0,
        progress_callback=None,
        progress_enabled: bool | None = None,
    ):
        import requests  # lazy import

        self.limiter = limiter or TokenBucketRateLimiter(RateLimit(rps=0.25, burst=1))
        self.session = session or requests.Session()
        self.user_agent = user_agent or "SensibLaw/0.1 (+https://sensiblaw.local)"
        self.timeout_s = timeout_s
        self.progress_callback = progress_callback
        self.progress_enabled = progress_enabled

    def fetch(self, url: str) -> FetchResult:
        parsed = urlparse(url)
        if not parsed.netloc.endswith("austlii.edu.au"):
            raise ValueError(f"Not an AustLII URL: {url}")

        self.limiter.acquire()
        label = parsed.path or parsed.netloc or url
        try:
            resp = self.session.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_s,
                stream=True,
            )
        except TypeError:
            resp = self.session.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_s,
            )
        resp.raise_for_status()
        total_bytes = None
        headers = getattr(resp, "headers", {}) or {}
        try:
            total_header = headers.get("Content-Length")
            total_bytes = int(total_header) if total_header else None
        except (TypeError, ValueError):
            total_bytes = None

        reporter = TransferProgressReporter(
            label=label,
            total_bytes=total_bytes,
            callback=self.progress_callback,
            enabled=self.progress_enabled,
        )
        reporter.start()
        downloaded_bytes = 0
        if hasattr(resp, "iter_content"):
            chunks: list[bytes] = []
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                chunks.append(chunk)
                downloaded_bytes += len(chunk)
                reporter.update(downloaded_bytes)
            content = b"".join(chunks)
        else:
            content = resp.content
            downloaded_bytes = len(content)
        progress = reporter.finish(downloaded_bytes)
        return FetchResult(
            content=content,
            content_type=headers.get("Content-Type"),
            url=url,
            metadata={
                "source": "austlii",
                "path": parsed.path,
                "status_code": resp.status_code,
                "downloaded_bytes": downloaded_bytes,
                "content_length_bytes": total_bytes,
                "elapsed_s": progress["elapsed_s"],
                "speed_bytes_per_s": progress["speed_bytes_per_s"],
            },
        )
