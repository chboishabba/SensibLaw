from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class StateStatutePortal:
    state_code: str
    state_name: str
    source_label: str
    base_url: str
    search_path: str
    canonical_query_keys: tuple[str, ...]
    description: str
    language: str = "en"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def portal_url(self) -> str:
        trimmed_base = self.base_url.rstrip("/")
        return f"{trimmed_base}{self.search_path}"

    def build_search_payload(self, query_text: str) -> dict[str, object]:
        return {
            "source_label": self.source_label,
            "query_text": query_text,
            "language": self.language,
            "metadata": {
                "state_code": self.state_code,
                "state_name": self.state_name,
                "portal_url": self.portal_url(),
                "canonical_query_keys": list(self.canonical_query_keys),
                "description": self.description,
            },
        }


def canonical_state_statute_portals() -> list[StateStatutePortal]:
    """Return a bounded set of representative official state statute portals."""

    return [
        StateStatutePortal(
            state_code="CA",
            state_name="California",
            source_label="state_statutes.ca",
            base_url="https://leginfo.legislature.ca.gov",
            search_path="/faces/billSearchClient.xhtml",
            canonical_query_keys=("bill_number", "year"),
            description="California Legislative Information official interface for searching bills and statutes.",
        ),
        StateStatutePortal(
            state_code="NY",
            state_name="New York",
            source_label="state_statutes.ny",
            base_url="https://legislation.nysenate.gov",
            search_path="/search",
            canonical_query_keys=("text", "session"),
            description="New York State Senate legislation search and statute portal.",
        ),
        StateStatutePortal(
            state_code="TX",
            state_name="Texas",
            source_label="state_statutes.tx",
            base_url="https://statutes.capitol.texas.gov",
            search_path="/statutes",
            canonical_query_keys=("query",),
            description="Texas Statutes portal maintained by the Texas Legislature Online.",
        ),
        StateStatutePortal(
            state_code="FL",
            state_name="Florida",
            source_label="state_statutes.fl",
            base_url="https://www.flsenate.gov",
            search_path="/Session/Bills/BillText",
            canonical_query_keys=("bill_id", "year"),
            description="Florida Senate official bill text and statute search experience.",
        ),
    ]


def canonical_state_statute_queries(query_text: str) -> list[dict[str, object]]:
    """Produce a normalized payload for each canonical portal using the provided text."""

    return [portal.build_search_payload(query_text) for portal in canonical_state_statute_portals()]
