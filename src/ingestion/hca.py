"""High Court of Australia (HCA) judgment index crawler.

This module provides a very small HTML crawler used in the tests to
illustrate how index pages from the official High Court of Australia web
site can be transformed into graph data.  The real site exposes yearly
index pages at ``https://eresources.hcourt.gov.au/showbyYear.php`` which
list each judgment together with catchwords, legislation citations and a
link to the judgment PDF.

The implementation below purposely avoids third‑party dependencies so
that it can operate in the execution environment used for the kata.  The
HTML on the live site is reasonably structured but for the sake of the
exercise the parser is deliberately forgiving and relies only on the
Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import html
import re
from typing import Iterable, List, Tuple, Dict, Optional

from .cache import fetch_html
from ..graph.hierarchy import COURT_RANKS, court_weight

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class HCACase:
    """Representation of a single High Court judgment entry."""

    citation: str
    pdf_url: Optional[str]
    catchwords: List[str]
    statutes: List[str]


# Regular expressions used to pull data out of the light weight HTML.  The
# layout used on the site is relatively stable so these expressions are
# sufficient for extracting the key pieces we need for tests.
_CASE_BLOCK_RE = re.compile(r"<li>(?P<block>.*?)</li>", re.DOTALL | re.IGNORECASE)
_PDF_RE = re.compile(r"href=\"(?P<pdf>[^\"]+\.pdf)\"", re.IGNORECASE)
_CATCH_RE = re.compile(r"Catchwords:\s*(?P<txt>[^<]*)", re.IGNORECASE)
_STAT_RE = re.compile(
    r"(?:Legislation|Statutes?\s*(?:referred\s*to)?)\s*:\s*(?P<txt>[^<]*)",
    re.IGNORECASE,
)
_CITATION_RE = re.compile(r"\[\d{4}\]\s*HCA\s*\d+", re.IGNORECASE)

# Base URL for the index pages.  ``{year}`` is interpolated by
# :func:`crawl_year` when network access is permitted.
_INDEX_URL = "https://eresources.hcourt.gov.au/showbyYear.php?year={year}"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _split_list(text: str) -> List[str]:
    """Split a semi‑structured string into a list of tokens.

    The catchwords and statute fields on the HCA site are simply separated
    by commas or semi‑colons.  Any surrounding whitespace is trimmed and
    empty items are ignored.
    """

    parts = re.split(r"[,;]", text)
    return [p.strip() for p in parts if p.strip()]


def _parse_case(block: str) -> HCACase:
    """Parse a single ``<li>`` block representing a case."""

    pdf_match = _PDF_RE.search(block)
    pdf_url = pdf_match.group("pdf") if pdf_match else None

    catch_match = _CATCH_RE.search(block)
    catchwords: List[str] = []
    if catch_match:
        catchwords = _split_list(html.unescape(catch_match.group("txt")))

    stat_match = _STAT_RE.search(block)
    statutes: List[str] = []
    if stat_match:
        statutes = _split_list(html.unescape(stat_match.group("txt")))

    # Remove all HTML tags to obtain plain text then search for the formal
    # citation (e.g. ``[1992] HCA 23``).  Fallback to the stripped text if a
    # citation is not found which keeps the function robust to slightly
    # different HTML structures used in the tests.
    plain = html.unescape(re.sub(r"<[^>]+>", " ", block))
    cit_match = _CITATION_RE.search(plain)
    citation = cit_match.group(0) if cit_match else plain.strip()

    return HCACase(citation=citation, pdf_url=pdf_url, catchwords=catchwords, statutes=statutes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_index(html_text: str) -> Iterable[HCACase]:
    """Yield :class:`HCACase` objects from a yearly index HTML page."""

    for match in _CASE_BLOCK_RE.finditer(html_text):
        block = match.group("block")
        yield _parse_case(block)


def crawl_year(
    year: Optional[int] = None,
    *,
    html_text: Optional[str] = None,
    panel_size: int = 1,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Crawl a yearly index page and return graph data.

    Parameters
    ----------
    year:
        The year to crawl.  Defaults to the current year when not supplied.
    html_text:
        Optional HTML content.  Supplying this allows unit tests to run
        without requiring network access.

    Returns
    -------
    ``(nodes, edges)``
        ``nodes`` is a list of dictionaries representing case and statute
        nodes.  ``edges`` links each case to the statutes it cites via a
        ``"cites"`` relationship.
    """

    if year is None:
        year = datetime.now().year

    if html_text is None:
        html_text = fetch_html(_INDEX_URL.format(year=year))

    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []

    court = "HCA"
    rank = COURT_RANKS.get(court, 0)
    weight = court_weight(court, panel_size)

    for case in parse_index(html_text):
        case_id = case.citation
        nodes.append(
            {
                "id": case_id,
                "type": "case",
                "catchwords": case.catchwords,
                "pdf": case.pdf_url,
                "court_rank": rank,
                "panel_size": panel_size,
            }
        )
        for statute in case.statutes:
            nodes.append({"id": statute, "type": "statute"})
            edges.append({"from": case_id, "to": statute, "type": "cites", "weight": weight})

    return nodes, edges


__all__ = ["HCACase", "parse_index", "crawl_year"]
