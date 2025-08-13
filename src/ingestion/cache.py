from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlparse
from urllib.request import urlopen

# Root directory for cached responses.  By default this lives inside the
# repository's ``data`` folder but can be overridden via the
# ``SENSIBLAW_CACHE`` environment variable.
CACHE_DIR = Path(os.environ.get("SENSIBLAW_CACHE", Path(__file__).resolve().parents[2] / "data" / "cache"))

# Ensure the cache directory exists so tests can pre-populate entries.
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Simple per-host rate limiting.  A one second delay is enforced between
# network requests to the same host.  This keeps the kata polite when it needs
# to talk to real services but still remains deterministic for tests.
_RATE_LIMIT_SECONDS = 1.0
_last_request: Dict[str, float] = {}
_lock = threading.Lock()


def _cache_path(url: str, suffix: str) -> Path:
    """Return the on-disk path for ``url`` with file extension ``suffix``."""

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.{suffix}"


def _throttle(host: str) -> None:
    """Sleep if necessary to respect the per-host rate limit."""

    with _lock:
        now = time.time()
        last = _last_request.get(host, 0.0)
        wait = _RATE_LIMIT_SECONDS - (now - last)
        if wait > 0:
            time.sleep(wait)
        _last_request[host] = time.time()


def _fetch(url: str, *, suffix: str) -> bytes:
    """Fetch ``url`` obeying cache and rate limits."""

    path = _cache_path(url, suffix)
    if path.exists():
        return path.read_bytes()

    host = urlparse(url).netloc
    _throttle(host)

    with urlopen(url) as resp:  # pragma: no cover - network
        data = resp.read()

    path.write_bytes(data)
    return data


def fetch_html(url: str) -> str:
    """Return HTML text from ``url`` using the cache."""

    data = _fetch(url, suffix="html")
    return data.decode("utf-8", errors="ignore")


def fetch_pdf(url: str) -> bytes:
    """Return PDF bytes from ``url`` using the cache."""

    return _fetch(url, suffix="pdf")


def fetch_json(url: str) -> Dict[str, Any]:
    """Return parsed JSON from ``url`` using the cache."""

    data = _fetch(url, suffix="json")
    return json.loads(data.decode("utf-8"))


__all__ = ["fetch_html", "fetch_pdf", "fetch_json", "CACHE_DIR"]
