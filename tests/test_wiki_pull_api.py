from __future__ import annotations

import io
import json
from email.message import Message
from urllib.error import HTTPError

from scripts import wiki_pull_api


def test_get_json_retries_http_429_then_succeeds(monkeypatch) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def _fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        def read(self) -> bytes:
            return self._payload

    def _fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        del req, timeout
        calls["count"] += 1
        if calls["count"] == 1:
            headers = Message()
            headers["Retry-After"] = "0"
            raise HTTPError(
                url="https://example.test",
                code=429,
                msg="Too Many Requests",
                hdrs=headers,
                fp=io.BytesIO(b""),
            )
        return _FakeResponse(json.dumps({"ok": True}).encode("utf-8"))

    monkeypatch.setattr(wiki_pull_api.time, "sleep", _fake_sleep)
    monkeypatch.setattr(wiki_pull_api.urllib.request, "urlopen", _fake_urlopen)

    payload = wiki_pull_api._get_json("https://example.test", timeout_s=5, pacer=None)

    assert payload == {"ok": True}
    assert calls["count"] == 2
    assert sleeps == [0.0]
