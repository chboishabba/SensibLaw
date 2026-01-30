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

    def get(self, url, headers, timeout):
        self.calls += 1
        return SimpleNamespace(
            status_code=200,
            content=b"<html>ok</html>",
            headers={"Content-Type": "text/html"},
            raise_for_status=lambda: None,
        )


def test_austlii_fetch_returns_provenance():
    session = FakeSession()
    adapter = AustLiiFetchAdapter(session=session)
    result = adapter.fetch("https://www.austlii.edu.au/au/cases/cth/HCA/1992/23.html")
    assert result.content.startswith(b"<html>")
    assert result.metadata["source"] == "austlii"
    assert session.calls == 1
