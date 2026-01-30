from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CitationKey:
    year: int
    court: str
    number: int


_MNC_RE = re.compile(r"\[?(?P<year>\d{4})\]?\s+(?P<court>[A-Za-z]{2,10})\s+(?P<num>\d+)", re.IGNORECASE)


def normalize_mnc(text: str) -> CitationKey | None:
    if not text:
        return None
    m = _MNC_RE.search(text)
    if not m:
        return None
    return CitationKey(
        year=int(m.group("year")),
        court=m.group("court").upper(),
        number=int(m.group("num")),
    )


def jade_mnc_url(key: CitationKey, *, base: str = "https://jade.barnet.com.au") -> str:
    return f"{base}/mnc/{key.year}/{key.court}/{key.number}"


def jade_content_ext_url(key: CitationKey, *, base: str = "https://jade.barnet.com.au") -> str:
    return f"{base}/content/ext/mnc/{key.year}/{key.court.lower()}/{key.number}"


def austlii_case_url_guess(
    key: CitationKey, *, base: str = "https://www.austlii.edu.au", state: str = "cth"
) -> str:
    return f"{base}/au/cases/{state}/{key.court}/{key.year}/{key.number}.html"
