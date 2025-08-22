"""HTTP caching utilities with per-host rate limiting.

This module provides small helper functions for fetching web resources while
respecting a polite request rate. Responses are stored on disk keyed by the
SHA256 digest of their body which allows de-duplication of identical content.
Each URL additionally has a metadata file recording the ``ETag`` and
``Last-Modified`` headers returned by the server. Subsequent requests use
``If-None-Match`` and ``If-Modified-Since`` so that servers may respond with
``304 Not Modified``.

Network requests are throttled via a token bucket implementation allowing no
more than 30 requests per minute to any single host. This keeps the project
polite when it needs to talk to real services but still remains deterministic
for tests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Cache directories
# ---------------------------------------------------------------------------

# Root directory for cached responses.  By default this lives inside the
# repository's ``data`` folder but can be overridden via the
# ``SENSIBLAW_CACHE`` environment variable.
CACHE_DIR = Path(
    os.environ.get(
        "SENSIBLAW_CACHE", Path(__file__).resolve().parents[2] / "data" / "cache"
    )
)

# Store metadata separate from the response bodies.  ``objects`` holds files
# named by the SHA256 digest of their content while ``meta`` maps each URL to
# the digest and any caching headers.
_OBJECT_DIR = CACHE_DIR / "objects"
_META_DIR = CACHE_DIR / "meta"
for _d in (_OBJECT_DIR, _META_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Token bucket rate limiting
# ---------------------------------------------------------------------------

_REQUESTS_PER_MINUTE = 30
_REFILL_RATE = _REQUESTS_PER_MINUTE / 60.0  # tokens per second
_CAPACITY = _REQUESTS_PER_MINUTE


class _TokenBucket:
    """Simple token bucket for throttling requests per host."""

    def __init__(self) -> None:
        self.tokens = float(_CAPACITY)
        self.timestamp = time.monotonic()

    def consume(self, tokens: float = 1.0) -> None:
        while True:
            with _lock:
                now = time.monotonic()
                elapsed = now - self.timestamp
                # Refill tokens based on time passed since last check
                self.tokens = min(_CAPACITY, self.tokens + elapsed * _REFILL_RATE)
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self.timestamp = now
                    return
                # Not enough tokens; calculate wait time outside the lock
                need = tokens - self.tokens
                wait = need / _REFILL_RATE
            time.sleep(wait)


_buckets: Dict[str, _TokenBucket] = {}
_lock = threading.Lock()


def _get_bucket(host: str) -> _TokenBucket:
    with _lock:
        bucket = _buckets.get(host)
        if bucket is None:
            bucket = _TokenBucket()
            _buckets[host] = bucket
        return bucket


# ---------------------------------------------------------------------------
# Helpers for file paths
# ---------------------------------------------------------------------------


def _meta_path(url: str) -> Path:
    """Return the on-disk path for ``url``'s metadata file."""

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return _META_DIR / f"{digest}.json"


def _body_path(digest: str) -> Path:
    """Return the path for a cached response body."""

    return _OBJECT_DIR / digest


# ---------------------------------------------------------------------------
# Fetching logic with cache revalidation
# ---------------------------------------------------------------------------


logger = logging.getLogger(__name__)


def _fetch(url: str) -> bytes:
    """Fetch ``url`` obeying cache, conditional requests and rate limits."""

    meta_path = _meta_path(url)
    headers: Dict[str, str] = {}
    meta: Dict[str, Any] = {}

    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if etag := meta.get("etag"):
            headers["If-None-Match"] = etag
        if last_mod := meta.get("last_modified"):
            headers["If-Modified-Since"] = last_mod

    host = urlparse(url).netloc
    _get_bucket(host).consume()

    request = Request(url, headers=headers)

    try:
        with urlopen(request) as resp:  # pragma: no cover - network
            data = resp.read()
            etag = resp.headers.get("ETag")
            last_mod = resp.headers.get("Last-Modified")

        digest = hashlib.sha256(data).hexdigest()
        body_path = _body_path(digest)
        if not body_path.exists():
            body_path.write_bytes(data)

        meta_path.write_text(
            json.dumps({"etag": etag, "last_modified": last_mod, "digest": digest})
        )
        return data

    except HTTPError as exc:  # pragma: no cover - network
        if exc.code == 304 and meta:
            logger.info("304 Not Modified: %s", url)
            digest = meta.get("digest")
            if digest:
                return _body_path(digest).read_bytes()
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_html(url: str) -> str:
    """Return HTML text from ``url`` using the cache."""

    data = _fetch(url)
    return data.decode("utf-8", errors="ignore")


def fetch_pdf(url: str) -> bytes:
    """Return PDF bytes from ``url`` using the cache."""

    return _fetch(url)


def fetch_json(url: str) -> Dict[str, Any]:
    """Return parsed JSON from ``url`` using the cache."""

    data = _fetch(url)
    return json.loads(data.decode("utf-8"))


__all__ = ["fetch_html", "fetch_pdf", "fetch_json", "CACHE_DIR"]

