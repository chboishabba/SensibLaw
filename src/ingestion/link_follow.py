"""Bounded, lane-owned link traversal over policy-gated web fetch receipts."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, TextIO
from urllib.parse import urljoin, urlparse

from src.ingestion.web_fetch import (
    FetchPolicy,
    FetchReceipt,
    FetchedWebDocument,
    SessionLike,
    fetch_web_document,
    normalize_http_url,
)


LINK_FOLLOW_CONTRACT = "bounded-link-follow:v0_1"


@dataclass(frozen=True)
class LinkEdge:
    source_url: str
    target_url: str
    label: str
    rel: tuple[str, ...] = ()
    same_host: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FollowedDocument:
    document: FetchedWebDocument
    depth: int
    links: tuple[LinkEdge, ...]


@dataclass(frozen=True)
class FollowResult:
    documents: tuple[FollowedDocument, ...]
    receipts: tuple[FetchReceipt, ...]
    discovered_urls: tuple[str, ...]
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": LINK_FOLLOW_CONTRACT,
            "documents": [
                {
                    "requested_url": row.document.requested_url,
                    "final_url": row.document.final_url,
                    "depth": row.depth,
                    "canonical_text": row.document.canonical_text,
                    "media_type": row.document.media_type,
                    "links": [link.to_dict() for link in row.links],
                    "receipt": row.document.receipt.to_dict(),
                }
                for row in self.documents
            ],
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "discovered_urls": list(self.discovered_urls),
            "truncated": self.truncated,
        }


class _HtmlLinkParser(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self._href: str | None = None
        self._rel: tuple[str, ...] = ()
        self._label: list[str] = []
        self._suppressed_depth = 0
        self.links: list[LinkEdge] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized in {"script", "style", "template"}:
            self._suppressed_depth += 1
        if normalized != "a" or self._suppressed_depth:
            return
        values = {key.casefold(): value for key, value in attrs}
        href = str(values.get("href") or "").strip()
        if href:
            self._href = href
            self._rel = tuple(
                sorted({part for part in str(values.get("rel") or "").split() if part})
            )
            self._label = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized == "a" and self._href is not None:
            target = normalize_http_url(urljoin(self.source_url, self._href))
            if target is not None:
                self.links.append(
                    LinkEdge(
                        source_url=self.source_url,
                        target_url=target,
                        label=" ".join("".join(self._label).split()),
                        rel=self._rel,
                        same_host=(
                            urlparse(self.source_url).hostname
                            == urlparse(target).hostname
                        ),
                    )
                )
            self._href = None
            self._rel = ()
            self._label = []
        if normalized in {"script", "style", "template"} and self._suppressed_depth:
            self._suppressed_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._href is not None and not self._suppressed_depth:
            self._label.append(data)


def extract_html_links(source_url: str, html: str) -> tuple[LinkEdge, ...]:
    parser = _HtmlLinkParser(source_url)
    parser.feed(html)
    parser.close()
    by_target = {row.target_url: row for row in parser.links}
    return tuple(sorted(by_target.values(), key=lambda row: row.target_url))


def bounded_follow(
    seed_urls: Iterable[str],
    *,
    policy: FetchPolicy | None = None,
    max_depth: int = 1,
    max_documents: int = 20,
    link_filter: Callable[[LinkEdge], bool] | None = None,
    session: SessionLike | None = None,
    progress_stream: TextIO | None = None,
) -> FollowResult:
    """Follow links breadth-first with explicit depth/document bounds."""

    if max_depth < 0 or max_documents < 0:
        raise ValueError("follow bounds must be non-negative")
    queue: deque[tuple[str, int]] = deque()
    discovered: set[str] = set()
    for seed in seed_urls:
        normalized = normalize_http_url(seed)
        if normalized is not None and normalized not in discovered:
            discovered.add(normalized)
            queue.append((normalized, 0))
    documents: list[FollowedDocument] = []
    receipts: list[FetchReceipt] = []
    content_hashes: set[str] = set()
    while queue and len(documents) < max_documents:
        url, depth = queue.popleft()
        document = fetch_web_document(
            url,
            policy=policy,
            session=session,
            progress_stream=progress_stream,
        )
        receipts.append(document.receipt)
        if not document.fetched:
            continue
        content_sha = document.receipt.content_sha256 or ""
        if content_sha in content_hashes:
            continue
        content_hashes.add(content_sha)
        links: tuple[LinkEdge, ...] = ()
        if document.media_type in {"text/html", "application/xhtml+xml"}:
            links = extract_html_links(
                document.final_url or document.requested_url,
                document.raw_bytes.decode("utf-8", errors="replace"),
            )
        documents.append(FollowedDocument(document, depth, links))
        if depth >= max_depth:
            continue
        for link in links:
            if link_filter is not None and not link_filter(link):
                continue
            if link.target_url in discovered:
                continue
            discovered.add(link.target_url)
            queue.append((link.target_url, depth + 1))
    return FollowResult(
        documents=tuple(documents),
        receipts=tuple(receipts),
        discovered_urls=tuple(sorted(discovered)),
        truncated=bool(queue),
    )


__all__ = [
    "FollowResult",
    "FollowedDocument",
    "LINK_FOLLOW_CONTRACT",
    "LinkEdge",
    "bounded_follow",
    "extract_html_links",
]
