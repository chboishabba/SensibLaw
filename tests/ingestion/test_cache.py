import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.cache import HTTPCache


class DummySession:
    def __init__(self):
        self.calls = 0
        self.etag = "etag123"
        self.last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
        self.last_headers = None

    def get(self, url, headers=None):
        self.calls += 1
        self.last_headers = headers or {}
        class Resp:
            headers: dict
            status_code: int
            _content: bytes

            def __init__(self):
                self.headers = {}
                self.status_code = 200
                self._content = b""

            def raise_for_status(self):
                return None

            @property
            def content(self):
                return self._content

        resp = Resp()
        if self.calls == 1:
            resp.status_code = 200
            resp._content = b"content"
            resp.headers["ETag"] = self.etag
            resp.headers["Last-Modified"] = self.last_modified
        else:
            # Ensure conditional headers were sent
            assert self.last_headers.get("If-None-Match") == self.etag
            assert self.last_headers.get("If-Modified-Since") == self.last_modified
            resp.status_code = 304
            resp._content = b""
        return resp


def test_cache_skips_network_within_delay(tmp_path: Path):
    session = DummySession()
    cache = HTTPCache(tmp_path, delay=60, session=session)
    url = "http://example.com/resource"
    first = cache.fetch(url)
    second = cache.fetch(url)
    assert first == second == b"content"
    # Second call should not hit network because of delay
    assert session.calls == 1


def test_cache_uses_conditional_headers_after_delay(tmp_path: Path):
    session = DummySession()
    cache = HTTPCache(tmp_path, delay=0, session=session)
    url = "http://example.com/resource"
    first = cache.fetch(url)
    assert first == b"content"
    # No delay -> will revalidate via conditional request
    second = cache.fetch(url)
    assert second == b"content"
    assert session.calls == 2
