from __future__ import annotations

from io import StringIO

import requests

from src.ingestion.link_follow import bounded_follow, extract_html_links
from src.ingestion.web_fetch import FetchPolicy, fetch_web_document


class FakeResponse:
    def __init__(
        self,
        url: str,
        content: bytes,
        *,
        content_type: str = "text/html; charset=utf-8",
        status_code: int = 200,
    ) -> None:
        self.url = url
        self.content = content
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, rows: dict[str, FakeResponse]) -> None:
        self.rows = rows
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs):
        self.calls.append(url)
        row = self.rows.get(url)
        if row is None:
            raise requests.ConnectionError(f"missing fake response for {url}")
        return row


def test_html_fetch_uses_shared_canonical_text_and_reports_source_url() -> None:
    url = "https://example.test/page"
    html = b"<html><body><h1>George W. Bush</h1><script>PoisonActor</script></body></html>"
    stream = StringIO()
    result = fetch_web_document(
        url,
        policy=FetchPolicy(allowed_hosts=("example.test",)),
        session=FakeSession({url: FakeResponse(url, html)}),
        progress_stream=stream,
    )

    assert result.fetched is True
    assert result.raw_bytes == html
    assert "George W. Bush" in result.canonical_text
    assert "PoisonActor" not in result.canonical_text
    assert result.receipt.content_sha256
    assert result.receipt.canonical_text_sha256
    assert url in stream.getvalue()


def test_failure_receipt_prints_the_url_for_operator_recovery() -> None:
    url = "https://example.test/missing"
    stream = StringIO()
    result = fetch_web_document(
        url,
        policy=FetchPolicy(allowed_hosts=("example.test",)),
        session=FakeSession({url: FakeResponse(url, b"not found", status_code=404)}),
        progress_stream=stream,
    )

    assert result.fetched is False
    assert result.receipt.status == "network_error"
    assert url in stream.getvalue()


def test_link_parser_normalizes_relative_links_and_drops_non_http_targets() -> None:
    rows = extract_html_links(
        "https://example.test/a/index.html",
        """
        <a href="../case/1#part">Case one</a>
        <a href="mailto:test@example.test">mail</a>
        <script><a href="/poison">ignored</a></script>
        """,
    )

    assert [row.target_url for row in rows] == ["https://example.test/case/1"]
    assert rows[0].label == "Case one"
    assert rows[0].same_host is True


def test_bounded_follow_deduplicates_urls_and_respects_depth() -> None:
    first = "https://example.test/a"
    second = "https://example.test/b"
    session = FakeSession(
        {
            first: FakeResponse(first, b'<a href="/b">B</a><a href="/b#x">B again</a>'),
            second: FakeResponse(second, b"<p>Second</p>"),
        }
    )
    result = bounded_follow(
        [first],
        policy=FetchPolicy(allowed_hosts=("example.test",)),
        max_depth=1,
        max_documents=2,
        session=session,
        progress_stream=StringIO(),
    )

    assert [row.document.final_url for row in result.documents] == [first, second]
    assert result.discovered_urls == (first, second)
    assert result.truncated is False
