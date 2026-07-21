"""Equal-capability bounded legal source follow profiles for AU, GB, and US.

This module is an acquisition backend, not a semantic classifier. Broad seeded
follow remains available for explicit corpus construction. PNF-driven follow
must supply a typed legal source plan and is restricted to endpoints matching
its declared jurisdiction, source roles, authority levels, and provider refs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, TextIO
from urllib.parse import urlparse

from src.ingestion.link_follow import FollowResult, LinkEdge, bounded_follow
from src.ingestion.web_fetch import FetchPolicy, SessionLike
from src.pnf.legal_adjunct import LegalSourcePlan


LEGAL_FOLLOW_CONTRACT = "legal-source-follow:v0_3"


@dataclass(frozen=True)
class LegalSourceEndpoint:
    endpoint_ref: str
    jurisdiction: str
    title: str
    url: str
    source_role: str
    authority_level: str
    access_mode: str = "html"
    api_key_environment: str | None = None
    licence_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value not in (None, "")
        }


@dataclass(frozen=True)
class LegalFollowProfile:
    jurisdiction: str
    endpoints: tuple[LegalSourceEndpoint, ...]
    max_depth: int = 1
    max_documents: int = 20

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        return _allowed_hosts(self.endpoints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": LEGAL_FOLLOW_CONTRACT,
            "jurisdiction": self.jurisdiction,
            "endpoints": [row.to_dict() for row in self.endpoints],
            "max_depth": self.max_depth,
            "max_documents": self.max_documents,
            "authority": "source-discovery-only",
        }


AU_PROFILE = LegalFollowProfile(
    jurisdiction="AU",
    endpoints=(
        LegalSourceEndpoint(
            "au:federal-register-api",
            "AU",
            "Federal Register of Legislation API",
            "https://api.prod.legislation.gov.au/v1/",
            "primary_legislation",
            "official",
            "json_api",
        ),
        LegalSourceEndpoint(
            "au:federal-register",
            "AU",
            "Federal Register of Legislation",
            "https://www.legislation.gov.au/",
            "primary_legislation",
            "official",
        ),
        LegalSourceEndpoint(
            "au:high-court",
            "AU",
            "High Court of Australia cases",
            "https://www.hcourt.gov.au/cases",
            "primary_case_law",
            "official",
        ),
        LegalSourceEndpoint(
            "au:fair-work-commission",
            "AU",
            "Fair Work Commission decisions",
            "https://www.fwc.gov.au/hearings-decisions",
            "primary_case_law",
            "official",
        ),
        LegalSourceEndpoint(
            "au:austlii",
            "AU",
            "AustLII",
            "https://www.austlii.edu.au/",
            "research_index",
            "supporting",
        ),
    ),
)


GB_PROFILE = LegalFollowProfile(
    jurisdiction="GB",
    endpoints=(
        LegalSourceEndpoint(
            "gb:legislation-api",
            "GB",
            "legislation.gov.uk data API",
            "https://www.legislation.gov.uk/data.feed",
            "primary_legislation",
            "official",
            "atom_api",
        ),
        LegalSourceEndpoint(
            "gb:find-case-law",
            "GB",
            "Find Case Law",
            "https://caselaw.nationalarchives.gov.uk/",
            "primary_case_law",
            "official",
            licence_note="Respect service terms, robots directives, and any separate computational-analysis licensing requirement.",
        ),
        LegalSourceEndpoint(
            "gb:supreme-court",
            "GB",
            "UK Supreme Court decided cases",
            "https://www.supremecourt.uk/decided-cases",
            "primary_case_law",
            "official",
        ),
        LegalSourceEndpoint(
            "gb:national-archives-discovery",
            "GB",
            "The National Archives Discovery",
            "https://discovery.nationalarchives.gov.uk/",
            "archive_catalogue",
            "official",
        ),
    ),
)


US_PROFILE = LegalFollowProfile(
    jurisdiction="US",
    endpoints=(
        LegalSourceEndpoint(
            "us:govinfo",
            "US",
            "GovInfo",
            "https://www.govinfo.gov/",
            "primary_legislation_and_records",
            "official",
        ),
        LegalSourceEndpoint(
            "us:govinfo-api",
            "US",
            "GovInfo API",
            "https://api.govinfo.gov/",
            "primary_legislation_and_records",
            "official",
            "json_api",
            api_key_environment="GOVINFO_API_KEY",
        ),
        LegalSourceEndpoint(
            "us:congress",
            "US",
            "Congress.gov",
            "https://www.congress.gov/",
            "primary_legislation",
            "official",
        ),
        LegalSourceEndpoint(
            "us:supreme-court",
            "US",
            "Supreme Court opinions",
            "https://www.supremecourt.gov/opinions/opinions.aspx",
            "primary_case_law",
            "official",
        ),
        LegalSourceEndpoint(
            "us:courtlistener",
            "US",
            "CourtListener",
            "https://www.courtlistener.com/",
            "research_index",
            "supporting",
            "json_api",
        ),
    ),
)


PROFILES: Mapping[str, LegalFollowProfile] = {
    "AU": AU_PROFILE,
    "GB": GB_PROFILE,
    "UK": GB_PROFILE,
    "US": US_PROFILE,
    "USA": US_PROFILE,
}


def profile_for(jurisdiction: str) -> LegalFollowProfile:
    key = jurisdiction.strip().upper()
    try:
        return PROFILES[key]
    except KeyError as error:
        raise ValueError(f"unsupported legal follow jurisdiction: {jurisdiction}") from error


def _allowed_hosts(endpoints: Iterable[LegalSourceEndpoint]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(urlparse(endpoint.url).hostname or "")
                for endpoint in endpoints
                if urlparse(endpoint.url).hostname
            }
        )
    )


def _profile_link_filter(allowed_hosts: Iterable[str], link: LinkEdge) -> bool:
    host = str(urlparse(link.target_url).hostname or "").casefold()
    allowed = {value.casefold() for value in allowed_hosts}
    return host in allowed or any(host.endswith("." + value) for value in allowed)


def select_legal_endpoints(
    plan: LegalSourcePlan,
) -> tuple[LegalSourceEndpoint, ...]:
    """Return exact endpoint matches for one ready PNF-derived plan."""

    if plan.state != "ready" or not plan.jurisdiction_ref:
        return ()
    profile = profile_for(plan.jurisdiction_ref)
    selected: list[LegalSourceEndpoint] = []
    requested_profiles = set(plan.provider_profile_refs)
    for endpoint in profile.endpoints:
        if endpoint.source_role not in set(plan.source_role_refs):
            continue
        if endpoint.authority_level not in set(plan.authority_level_refs):
            continue
        if requested_profiles and endpoint.endpoint_ref not in requested_profiles:
            continue
        selected.append(endpoint)
    return tuple(selected)


def _follow_endpoints(
    profile: LegalFollowProfile,
    endpoints: tuple[LegalSourceEndpoint, ...],
    *,
    seed_urls: Iterable[str] = (),
    max_depth: int | None = None,
    max_documents: int | None = None,
    session: SessionLike | None = None,
    progress_stream: TextIO | None = None,
) -> FollowResult:
    seeds = tuple(seed_urls) or tuple(
        endpoint.url
        for endpoint in endpoints
        if endpoint.access_mode in {"html", "atom_api"}
    )
    allowed_hosts = _allowed_hosts(endpoints)
    policy = FetchPolicy(
        allowed_hosts=allowed_hosts,
        allowed_content_types=(
            "text/html",
            "application/xhtml+xml",
            "text/plain",
            "application/atom+xml",
            "application/xml",
            "text/xml",
        ),
    )
    return bounded_follow(
        seeds,
        policy=policy,
        max_depth=profile.max_depth if max_depth is None else max_depth,
        max_documents=profile.max_documents if max_documents is None else max_documents,
        link_filter=lambda link: _profile_link_filter(allowed_hosts, link),
        session=session,
        progress_stream=progress_stream,
    )


def follow_legal_sources(
    jurisdiction: str,
    *,
    seed_urls: Iterable[str] = (),
    max_depth: int | None = None,
    max_documents: int | None = None,
    session: SessionLike | None = None,
    progress_stream: TextIO | None = None,
) -> FollowResult:
    """Run explicit broad bounded source discovery for one jurisdiction."""

    profile = profile_for(jurisdiction)
    return _follow_endpoints(
        profile,
        profile.endpoints,
        seed_urls=seed_urls,
        max_depth=max_depth,
        max_documents=max_documents,
        session=session,
        progress_stream=progress_stream,
    )


def follow_legal_source_plan(
    plan: LegalSourcePlan,
    *,
    max_depth: int | None = None,
    max_documents: int | None = None,
    session: SessionLike | None = None,
    progress_stream: TextIO | None = None,
) -> FollowResult | None:
    """Execute one typed PNF-derived acquisition plan without broadening it."""

    endpoints = select_legal_endpoints(plan)
    if not endpoints:
        return None
    profile = profile_for(plan.jurisdiction_ref)
    return _follow_endpoints(
        profile,
        endpoints,
        max_depth=max_depth,
        max_documents=max_documents,
        session=session,
        progress_stream=progress_stream,
    )


__all__ = [
    "AU_PROFILE",
    "GB_PROFILE",
    "LEGAL_FOLLOW_CONTRACT",
    "LegalFollowProfile",
    "LegalSourceEndpoint",
    "PROFILES",
    "US_PROFILE",
    "follow_legal_source_plan",
    "follow_legal_sources",
    "profile_for",
    "select_legal_endpoints",
]
