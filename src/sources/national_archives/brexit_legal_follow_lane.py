"""Brexit legal-source lane over real official publication surfaces.

This v2 lane supersedes the placeholder catalogue targets in the legacy
``brexit_national_archives_lane`` fetch path.  Failures remain explicit fetch
receipts; no synthetic fixture is substituted for an unavailable live page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TextIO

from src.ingestion.link_follow import FollowResult
from src.ingestion.web_fetch import SessionLike
from src.sources.legal_follow import follow_legal_sources


BREXIT_LEGAL_FOLLOW_CONTRACT = "brexit-legal-follow:v0_2"


@dataclass(frozen=True)
class BrexitLegalTarget:
    target_ref: str
    title: str
    url: str
    source_role: str

    def to_dict(self) -> dict[str, str]:
        return {
            "target_ref": self.target_ref,
            "title": self.title,
            "url": self.url,
            "source_role": self.source_role,
        }


TARGETS = (
    BrexitLegalTarget(
        "brexit:withdrawal-act-2018",
        "European Union (Withdrawal) Act 2018",
        "https://www.legislation.gov.uk/ukpga/2018/16/contents",
        "primary_legislation",
    ),
    BrexitLegalTarget(
        "brexit:withdrawal-agreement-act-2020",
        "European Union (Withdrawal Agreement) Act 2020",
        "https://www.legislation.gov.uk/ukpga/2020/1/contents",
        "primary_legislation",
    ),
    BrexitLegalTarget(
        "brexit:miller-2017",
        "R (Miller) v Secretary of State for Exiting the European Union",
        "https://caselaw.nationalarchives.gov.uk/uksc/2017/5",
        "primary_case_law",
    ),
    BrexitLegalTarget(
        "brexit:miller-cherry-2019",
        "R (Miller) v The Prime Minister; Cherry v Advocate General for Scotland",
        "https://caselaw.nationalarchives.gov.uk/uksc/2019/41",
        "primary_case_law",
    ),
)


def manifest() -> dict[str, Any]:
    return {
        "contract_ref": BREXIT_LEGAL_FOLLOW_CONTRACT,
        "jurisdiction": "GB",
        "targets": [row.to_dict() for row in TARGETS],
        "fetch_mode": "bounded_official_source_follow",
        "fixture_fallback": False,
        "network_failure_policy": "emit_failure_receipt_with_url",
        "authority": "source-discovery-only",
    }


def fetch_brexit_legal_sources(
    *,
    max_depth: int = 1,
    max_documents: int = 20,
    session: SessionLike | None = None,
    progress_stream: TextIO | None = None,
) -> FollowResult:
    return follow_legal_sources(
        "GB",
        seed_urls=tuple(row.url for row in TARGETS),
        max_depth=max_depth,
        max_documents=max_documents,
        session=session,
        progress_stream=progress_stream,
    )


__all__ = [
    "BREXIT_LEGAL_FOLLOW_CONTRACT",
    "BrexitLegalTarget",
    "TARGETS",
    "fetch_brexit_legal_sources",
    "manifest",
]
