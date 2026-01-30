from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
from urllib.parse import urlencode

from .rate_limit import RateLimit, TokenBucketRateLimiter

DEFAULT_SINO_ENDPOINT = "https://www.austlii.edu.au/cgi-bin/sinosrch.cgi"
ALLOWED_METHODS = {"any", "or", "all", "near", "phrase", "legis", "title", "boolean"}


@dataclass(frozen=True)
class SinoQuery:
    meta: str  # VC, e.g. "/au" or "/austlii"
    query: str
    method: str = "any"
    rank: str | None = None  # "on"|"off"|None
    results: int = 50
    offset: int = 0
    callback: str | None = None  # "on"|"off"|None
    mask_path: List[str] | None = None
    mask_by_phc: Dict[str, List[str]] | None = None  # mask_au, mask_nz, etc.


def build_sino_url(endpoint: str, q: SinoQuery) -> str:
    if q.method not in ALLOWED_METHODS:
        raise ValueError(f"Unsupported method {q.method!r}")

    params: List[Tuple[str, str]] = [
        ("meta", q.meta),
        ("method", q.method),
        ("query", q.query),
        ("results", str(int(q.results))),
        ("offset", str(int(q.offset))),
    ]
    if q.rank:
        params.append(("rank", q.rank))
    if q.callback:
        params.append(("callback", q.callback))

    if q.mask_path:
        for p in q.mask_path:
            params.append(("mask_path", p))

    if q.mask_by_phc:
        for alias, paths in q.mask_by_phc.items():
            for p in paths:
                params.append((f"mask_{alias}", p))

    qs = urlencode(params)
    sep = "&" if "?" in endpoint else "?"
    return f"{endpoint}{sep}{qs}"


# Light wrapper class for politeness; parsing lives elsewhere.
class AustLiiSearchAdapter:
    source_name = "austlii.search"

    def __init__(
        self,
        endpoint: str = DEFAULT_SINO_ENDPOINT,
        limiter: TokenBucketRateLimiter | None = None,
        session=None,
        user_agent: str | None = None,
        referer: str | None = None,
        timeout_s: float = 30.0,
    ):
        import requests  # lazy import to avoid hard dependency for pure tests

        self.endpoint = endpoint
        self.limiter = limiter or TokenBucketRateLimiter(RateLimit(rps=0.5, burst=1))
        self.session = session or requests.Session()
        # NOTE:
        # AustLII returns HTTP 410 to generic/bot User-Agents. We intentionally send a
        # browser-like User-Agent and Referer to access the public SINO search form,
        # while remaining rate-limited and citation-driven. See docs/sources_contract.md.
        self.user_agent = user_agent or (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.referer = referer or "https://www.austlii.edu.au/"
        self.timeout_s = timeout_s

    def search(self, q: SinoQuery) -> str:
        """Return raw HTML search results (parsing handled separately)."""

        self.limiter.acquire()
        url = build_sino_url(self.endpoint, q)
        resp = self.session.get(
            url,
            headers={"User-Agent": self.user_agent, "Referer": self.referer},
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        return resp.text
