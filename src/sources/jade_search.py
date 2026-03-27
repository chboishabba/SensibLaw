from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import quote, urljoin

import requests

from src.citations.normalize import normalize_mnc

from .rate_limit import RateLimit, TokenBucketRateLimiter


_WS_RE = re.compile(r"\s+")
_CITE_RE = re.compile(r"\[\d{4}\]\s+[A-Z]{2,10}\s+\d+", re.IGNORECASE)
_MNC_URL_RE = re.compile(r"/mnc/(?P<year>\d{4})/(?P<court>[A-Za-z]{2,10})/(?P<num>\d+)")
_QUERY_MNC_RE = re.compile(r"\[?(?P<year>\d{4})\]?\s+(?P<court>[A-Za-z]{2,10})\s+(?P<num>\d+)", re.IGNORECASE)


def _collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", str(text or "")).strip()


def build_jade_search_url(base_url: str, query: str) -> str:
    base = str(base_url or "").rstrip("/")
    text = _collapse_ws(query)
    if not text:
        raise ValueError("query must be provided")
    return f"{base}/{quote(text, safe='')}"


@dataclass(frozen=True)
class JadeSearchHit:
    title: str
    url: str
    citation: str | None = None


def _citation_from_url(url: str) -> str | None:
    match = _MNC_URL_RE.search(url)
    if not match:
        return None
    return f"[{match.group('year')}] {match.group('court').upper()} {int(match.group('num'))}"


class _JadeSearchHTMLParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.hits: list[JadeSearchHit] = []
        self._seen_urls: set[str] = set()
        self._in_anchor = False
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        href = str(dict(attrs).get("href") or "").strip()
        if not href:
            return
        lower = href.lower()
        if "/article/" not in lower and "/mnc/" not in lower:
            return
        self._in_anchor = True
        self._href = href
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._in_anchor or not self._href:
            return
        url = urljoin(self.base_url, self._href)
        if url in self._seen_urls:
            self._reset()
            return
        title = _collapse_ws("".join(self._parts))
        citation = None
        match = _CITE_RE.search(title)
        if match:
            citation = match.group(0)
        else:
            citation = _citation_from_url(url)
        self.hits.append(JadeSearchHit(title=title or url, url=url, citation=citation))
        self._seen_urls.add(url)
        self._reset()

    def _reset(self) -> None:
        self._in_anchor = False
        self._href = None
        self._parts = []


def parse_jade_search_html(html: str, *, base_url: str = "https://jade.io/") -> list[JadeSearchHit]:
    parser = _JadeSearchHTMLParser(base_url=base_url)
    parser.feed(html)
    return parser.hits


def fallback_hit_for_query(query: str, *, base_url: str = "https://jade.barnet.com.au") -> JadeSearchHit | None:
    key = normalize_mnc(query)
    if key is None:
        return None
    match = _CITE_RE.search(query)
    url_match = _QUERY_MNC_RE.search(query)
    citation = _collapse_ws(match.group(0)) if match else f"[{key.year}] {key.court} {key.number}"
    court_token = url_match.group("court") if url_match else key.court
    url = f"{base_url.rstrip('/')}/mnc/{key.year}/{court_token}/{key.number}"
    return JadeSearchHit(title=citation, url=url, citation=citation)


class JadeSearchAdapter:
    source_name = "jade.search"

    def __init__(
        self,
        endpoint: str = "https://jade.io/search",
        limiter: TokenBucketRateLimiter | None = None,
        session: requests.Session | None = None,
        user_agent: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.limiter = limiter or TokenBucketRateLimiter(RateLimit(rps=0.25, burst=1))
        self.session = session or requests.Session()
        self.user_agent = user_agent or "SensibLaw/0.1 (+https://sensiblaw.local)"
        self.timeout_s = timeout_s

    def search(self, query: str) -> str:
        self.limiter.acquire()
        url = build_jade_search_url(self.endpoint, query)
        resp = self.session.get(
            url,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        return resp.text
