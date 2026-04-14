from types import SimpleNamespace

import pytest

from src.sources.austlii_fetch import AustLiiFetchAdapter


def test_austlii_fetch_rejects_non_austlii():
    adapter = AustLiiFetchAdapter(session=SimpleNamespace(get=None))  # session unused
    with pytest.raises(ValueError):
        adapter.fetch("https://example.com/not-austlii")


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, headers, timeout, stream=True):
        self.calls += 1
        return SimpleNamespace(
            status_code=200,
            content=b"<html>ok</html>",
            headers={"Content-Type": "text/html"},
            raise_for_status=lambda: None,
            iter_content=lambda chunk_size=65536: [b"<html>", b"ok</html>"],
        )


def test_austlii_fetch_returns_provenance():
    session = FakeSession()
    adapter = AustLiiFetchAdapter(session=session)
    result = adapter.fetch("https://www.austlii.edu.au/au/cases/cth/HCA/1992/23.html")
    assert result.content.startswith(b"<html>")
    assert result.metadata["source"] == "austlii"
    assert session.calls == 1


def test_austlii_fetch_reports_progress_metadata():
    seen = []
    session = FakeSession()
    adapter = AustLiiFetchAdapter(
        session=session,
        progress_callback=lambda stage, details: seen.append((stage, dict(details))),
        progress_enabled=True,
    )
    result = adapter.fetch("https://www.austlii.edu.au/au/cases/cth/HCA/1992/23.html")
    assert result.metadata["downloaded_bytes"] == len(result.content)
    assert result.metadata["elapsed_s"] >= 0
    assert result.metadata["speed_bytes_per_s"] >= 0
    assert seen[0][0] == "starting"
    assert seen[-1][0] == "complete"
