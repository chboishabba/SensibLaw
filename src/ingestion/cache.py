import json
import time
import hashlib
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - requests is optional in some environments
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore


class HTTPCache:
    """Simple persistent HTTP cache with conditional requests.

    The cache stores the response body along with the ``ETag`` and
    ``Last-Modified`` headers returned by the server.  Subsequent requests
    reuse this metadata to send ``If-None-Match`` and ``If-Modified-Since``
    headers.  A configurable delay avoids hitting the network when the cached
    copy is considered fresh.
    """

    def __init__(
        self,
        cache_dir: Path,
        *,
        delay: float = 0.0,
        session: Optional["requests.Session"] = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        if session is not None:
            self.session = session
        else:
            if requests is None:  # pragma: no cover - optional dependency
                raise RuntimeError("requests library required for network operations")
            self.session = requests.Session()

    # ------------------------------------------------------------------
    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = self._key(url)
        return self.cache_dir / f"{key}.bin", self.cache_dir / f"{key}.json"

    # ------------------------------------------------------------------
    def fetch(self, url: str) -> bytes:
        """Fetch *url* using a persistent cache.

        Parameters
        ----------
        url:
            The URL to download.

        Returns
        -------
        ``bytes``
            The body of the response, either from cache or the network.
        """

        body_path, meta_path = self._paths(url)
        meta = {}
        headers = {}
        now = time.time()

        if meta_path.exists() and body_path.exists():
            meta = json.loads(meta_path.read_text())
            fetched_at = meta.get("fetched_at", 0)
            if self.delay and (now - fetched_at) < self.delay:
                return body_path.read_bytes()
            if etag := meta.get("etag"):
                headers["If-None-Match"] = etag
            if lm := meta.get("last_modified"):
                headers["If-Modified-Since"] = lm

        response = self.session.get(url, headers=headers)
        if response.status_code == 304 and body_path.exists():
            meta["fetched_at"] = now
            meta_path.write_text(json.dumps(meta))
            return body_path.read_bytes()

        response.raise_for_status()
        body = response.content
        meta = {
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "fetched_at": now,
        }
        body_path.write_bytes(body)
        meta_path.write_text(json.dumps(meta))
        return body
