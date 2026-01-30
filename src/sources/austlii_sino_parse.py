from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin


@dataclass(frozen=True)
class AustLiiSearchHit:
    title: str
    url: str
    database_heading: str | None = None
    citation: str | None = None


_CITE_RE = re.compile(r"\[\d{4}\]\s+[A-Z]{2,10}\s+\d+", re.IGNORECASE)


class _SinoHTMLParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.hits: list[AustLiiSearchHit] = []
        self._in_a = False
        self._a_href: str | None = None
        self._a_text_parts: list[str] = []
        self._current_db_heading: str | None = None
        self._heading_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self._in_a = True
                self._a_href = href
                self._a_text_parts = []
        if tag.lower() in {"h2", "h3"}:
            self._heading_buf = []

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t == "a" and self._in_a and self._a_href:
            title = " ".join("".join(self._a_text_parts).split()).strip()
            href = self._a_href.strip()
            if title and ("/au/" in href or href.startswith("http")):
                url = urljoin(self.base_url, href)
                cite = None
                m = _CITE_RE.search(title)
                if m:
                    cite = m.group(0)
                self.hits.append(
                    AustLiiSearchHit(
                        title=title,
                        url=url,
                        database_heading=self._current_db_heading,
                        citation=cite,
                    )
                )
            self._in_a = False
            self._a_href = None
            self._a_text_parts = []

        if t in {"h2", "h3"}:
            heading = " ".join("".join(self._heading_buf).split()).strip()
            if heading:
                self._current_db_heading = heading
            self._heading_buf = []

    def handle_data(self, data: str):
        if self._in_a:
            self._a_text_parts.append(data)
        if self._heading_buf is not None:
            self._heading_buf.append(data)


def parse_sino_search_html(html: str, *, base_url: str = "https://www.austlii.edu.au/") -> list[AustLiiSearchHit]:
    parser = _SinoHTMLParser(base_url=base_url)
    parser.feed(html)
    return parser.hits
