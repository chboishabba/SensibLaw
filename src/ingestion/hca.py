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

from dataclasses import dataclass, field
from datetime import datetime
import html
import io
import re
from typing import Dict, Iterable, List, Optional, Tuple

from .cache import fetch_html, fetch_pdf
from src.graph.hierarchy import COURT_RANKS, court_weight
from src.graph.models import EdgeType, NodeType

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class HCACase:
    """Representation of a single High Court judgment entry."""

    citation: str
    pdf_url: Optional[str]
    parties: str
    catchwords: List[str]
    statutes: List[str]
    cases_cited: List[str]
    final_orders: List[str] = field(default_factory=list)
    panel_opinions: List[Dict[str, str]] = field(default_factory=list)


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
_CASES_CITED_RE = re.compile(
    r"Cases\s+cited\s*:?(?P<txt>.*?)(?:\n[A-Z][^\n]*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_LEGIS_CITED_RE = re.compile(
    r"(?:Legislation|Statutes?)\s*(?:cited|referred to)?\s*:?(?P<txt>.*?)(?:\n[A-Z][^\n]*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Base URL for the index pages.  ``{year}`` is interpolated by
# :func:`crawl_year` when network access is permitted.
_INDEX_URL = "https://eresources.hcourt.gov.au/showbyYear.php?year={year}"


# Mapping of common court abbreviations to a relative rank used when assigning
# weights to treatment edges.  Higher courts receive a larger value.
_COURT_RANK: Dict[str, float] = {
    "HCA": 5.0,  # High Court of Australia
    "FCA": 4.0,  # Federal Court of Australia
    "FCAFC": 4.0,  # Full Court of the Federal Court
    "NSWCA": 3.0,  # New South Wales Court of Appeal
    "NSWSC": 2.0,  # New South Wales Supreme Court
}

# Regular expression for extracting the court abbreviation from a citation.
_CITED_COURT_RE = re.compile(r"\[(?P<year>\d{4})\]\s*(?P<court>[A-Z]+)\s*\d+")


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
    """Parse a single ``<li>`` block representing a case from the index."""

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

    parties = plain.split(citation)[0].strip() if cit_match else plain.strip()

    return HCACase(
        citation=citation,
        pdf_url=pdf_url,
        parties=parties,
        catchwords=catchwords,
        statutes=statutes,
        cases_cited=[],
    )


def _extract_pdf_text(data: bytes) -> str:
    """Best effort conversion of PDF bytes to plain text."""

    try:  # pragma: no cover - pdfminer not guaranteed
        from pdfminer.high_level import extract_text

        return extract_text(io.BytesIO(data))
    except Exception:  # pragma: no cover - fallback
        try:
            return data.decode("utf-8")
        except Exception:
            return data.decode("latin-1", errors="ignore")


def _parse_pdf(
    data: bytes,
) -> Tuple[str, List[str], List[str], List[str], List[Dict[str, str]]]:
    """Parse parties, citations, legislation, orders and opinions from PDF bytes."""

    text = _extract_pdf_text(data)
    text = text.replace("\r", "")

    parties = ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for idx, line in enumerate(lines):
        if parties:
            break
        if " v " in line.lower() or " v." in line.lower():
            parties = line.strip()
            break
        if _CITATION_RE.search(line) and idx > 0:
            parties = lines[idx - 1]
            break

    cases: List[str] = []
    m = _CASES_CITED_RE.search(text)
    if m:
        section = re.sub(r"\s+", " ", m.group("txt"))
        cases = _split_list(section)

    statutes: List[str] = []
    m2 = _LEGIS_CITED_RE.search(text)
    if m2:
        section = re.sub(r"\s+", " ", m2.group("txt"))
        statutes = _split_list(section)

    final_orders: List[str] = []
    order_heading_re = re.compile(r"^(?:final\s+)?orders?\b", re.IGNORECASE)
    order_number_re = re.compile(
        r"^(?:\(?\d+\)?\.?|\(?[ivxlcdm]+\)|[a-z]\))\s*(?P<order>.+)",
        re.IGNORECASE,
    )
    heading_idx: Optional[int] = None
    for idx, line in enumerate(lines):
        if order_heading_re.match(line):
            heading_idx = idx
            break

    if heading_idx is not None:
        for line in lines[heading_idx + 1 :]:
            if not line:
                break
            if order_heading_re.match(line):
                break
            if re.fullmatch(r"[A-Z][A-Z\s\-&]+", line) and len(line) <= 80:
                break
            if re.match(r"^[A-Z][A-Za-z\s]+:$", line):
                break
            number_match = order_number_re.match(line)
            if number_match:
                final_orders.append(number_match.group("order").strip())
            else:
                final_orders.append(line.strip())

    panel_opinions: List[Dict[str, str]] = []
    opinion_pattern = re.compile(
        r"(?P<judge>[A-Z][A-Za-z'.-]*(?:[ \t]+[A-Z][A-Za-z'.-]*)*\s+(?:CJ|J|JJ))\s+(?P<stance>dissent(?:ed|ing)?|concurr(?:ed|ing)|agreed with|in the majority|for the majority)",
        re.IGNORECASE,
    )
    seen_judges: set[str] = set()
    for line in lines:
        lowered = line.lower()
        if not any(keyword in lowered for keyword in ("dissent", "concurr", "agreed with", "in the majority", "for the majority")):
            continue
        for match in opinion_pattern.finditer(line):
            judge_text = match.group("judge").strip()
            stance_raw = match.group("stance").lower()
            if judge_text.endswith("JJ"):
                judge_names = re.split(r",| and ", judge_text[:-2])
                judge_names = [n.strip() for n in judge_names if n.strip()]
                judge_list = [f"{name} J" if not name.endswith("J") else name for name in judge_names]
            else:
                judge_list = [judge_text]

            if "dissent" in stance_raw:
                stance = "dissenting"
            elif "concur" in stance_raw:
                stance = "concurring"
            else:
                stance = "majority"

            for judge_name in judge_list:
                if judge_name not in seen_judges:
                    panel_opinions.append({"judge": judge_name, "opinion": stance})
                    seen_judges.add(judge_name)

    return parties, cases, statutes, final_orders, panel_opinions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_index(html_text: str) -> Iterable[HCACase]:
    """Yield :class:`HCACase` objects from a yearly index HTML page."""

    for match in _CASE_BLOCK_RE.finditer(html_text):
        block = match.group("block")
        yield _parse_case(block)


def parse_cases_cited(section_text: str, *, source: str) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Parse a 'Cases cited' section into nodes and edges.

    Parameters
    ----------
    section_text:
        Raw text of the section.  Each line following the heading should be of
        the form ``"Follows: Some Case [1992] HCA 23"``.
    source:
        Identifier for the case that is citing the others.
    """

    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []

    for line in section_text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("cases cited"):
            continue
        match = re.match(r"(?P<treatment>\w+):\s*(?P<cite>.+)", line)
        if not match:
            continue
        treatment = match.group("treatment").lower()
        citation_text = match.group("cite").strip()
        court_match = _CITED_COURT_RE.search(citation_text)
        court = court_match.group("court") if court_match else ""
        rank = _COURT_RANK.get(court, 1.0)
        nodes.append({
            "id": citation_text,
            "type": NodeType.CASE.value,
            "court_rank": rank,
        })
        try:
            edge_type = EdgeType[treatment.upper()].value
        except KeyError:
            edge_type = treatment
        edges.append({
            "from": source,
            "to": citation_text,
            "type": edge_type,
            "weight": rank,
        })

    return nodes, edges

def crawl_year(
    year: Optional[int] = None,
    *,
    html_text: Optional[str] = None,
    panel_size: int = 1,
    pdfs: Optional[Dict[str, bytes]] = None,
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
    seen_nodes: Dict[str, str] = {}

    court = "HCA"
    rank = COURT_RANKS.get(court, 0)
    weight = court_weight(court, panel_size)

    for case in parse_index(html_text):
        pdf_bytes: Optional[bytes] = None
        if pdfs and case.citation in pdfs:
            pdf_bytes = pdfs[case.citation]
        elif case.pdf_url:
            try:  # pragma: no cover - network
                pdf_bytes = fetch_pdf(case.pdf_url)
            except Exception:
                pdf_bytes = None

        if pdf_bytes:
            (
                parties,
                cited_cases,
                cited_stats,
                final_orders,
                panel_opinions,
            ) = _parse_pdf(pdf_bytes)
            if parties:
                case.parties = parties
            if cited_cases:
                case.cases_cited.extend(cited_cases)
            if cited_stats:
                for s in cited_stats:
                    if s not in case.statutes:
                        case.statutes.append(s)
            if final_orders:
                case.final_orders = final_orders
            if panel_opinions:
                case.panel_opinions = panel_opinions

        def add_node(ident: str, ntype: str, **metadata: object) -> None:
            if ident not in seen_nodes:
                nodes.append({"id": ident, "type": ntype, **metadata})
                seen_nodes[ident] = ntype

        case_id = case.citation
        nodes.append(
            {
                "id": case_id,
                "type": NodeType.CASE.value,
                "catchwords": case.catchwords,
                "pdf": case.pdf_url,
                "court_rank": _COURT_RANK.get("HCA", 1.0),
                "final_orders": case.final_orders,
                "panel_opinions": case.panel_opinions,
            }
        )
        for statute in case.statutes:
            nodes.append({"id": statute, "type": NodeType.CONCEPT.value})
            edges.append(
                {
                    "from": case_id,
                    "to": statute,
                    "type": EdgeType.CITES.value,
                }
            )

        add_node(
            case_id,
            "case",
            parties=case.parties,
            catchwords=case.catchwords,
            pdf=case.pdf_url,
            final_orders=case.final_orders,
            panel_opinions=case.panel_opinions,
        )

        for statute in case.statutes:
            add_node(statute, "statute")
            edges.append({"from": case_id, "to": statute, "type": "cites"})

        for cited in case.cases_cited:
            add_node(cited, "case")
            edges.append({"from": case_id, "to": cited, "type": "cites"})

    return nodes, edges


__all__ = ["HCACase", "parse_index", "crawl_year", "parse_cases_cited"]
