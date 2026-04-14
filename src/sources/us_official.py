from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class OfficialDocMetadata:
    lane_id: str
    source_name: str
    doc_id: str
    title: str
    published_date: str
    doc_type: str
    policy_flags: tuple[str, ...]
    uri: str


def _validate_metadata(metadata: OfficialDocMetadata) -> None:
    if not metadata.doc_id:
        raise ValueError("Official document metadata requires doc_id")
    if not metadata.uri:
        raise ValueError("Official document metadata requires uri")


def build_congress_gov_doc() -> OfficialDocMetadata:
    return OfficialDocMetadata(
        lane_id="wikidata_nat_wdu_congress",
        source_name="Congress.gov",
        doc_id="congress-117-hr748",
        title="Infrastructure Investment and Jobs Act",
        published_date="2021-11-15",
        doc_type="public_law",
        policy_flags=("infrastructure", "budget"),
        uri="https://www.congress.gov/bill/117th-congress/house-bill/748",
    )


def build_govinfo_doc() -> OfficialDocMetadata:
    return OfficialDocMetadata(
        lane_id="gwb_govinfo_browse",
        source_name="GovInfo",
        doc_id="govinfo-PLAW-117publ58",
        title="Fiscal Responsibility Act of 2023",
        published_date="2023-05-11",
        doc_type="public_law",
        policy_flags=("budget", "debt_limit"),
        uri="https://www.govinfo.gov/content/pkg/PLAW-117publ58/html/PLAW-117publ58.htm",
    )


def build_grouped_official_packet(
    docs: Iterable[OfficialDocMetadata], *, packet_id: str
) -> dict[str, object]:
    doc_list = list(docs)
    if not doc_list:
        raise ValueError("Grouped packet requires at least one document")
    seen_docs: set[str] = set()
    lane_ids: set[str] = set()
    for meta in doc_list:
        _validate_metadata(meta)
        if meta.doc_id in seen_docs:
            raise ValueError(f"Duplicate official doc id: {meta.doc_id}")
        seen_docs.add(meta.doc_id)
        lane_ids.add(meta.lane_id)

    sorted_docs = [asdict(meta) for meta in doc_list]
    sorted_lane_ids = sorted(lane_ids)
    combined_flags = sorted({flag for meta in doc_list for flag in meta.policy_flags})

    return {
        "packet_id": packet_id,
        "lane_ids": sorted_lane_ids,
        "doc_count": len(sorted_docs),
        "docs": sorted_docs,
        "combined_policy_flags": combined_flags,
        "constraints": {
            "deterministic_ids": True,
            "official_sources": [meta.source_name for meta in doc_list],
        },
        "recommendation": (
            "Use this grouped packet to seed a narrow follow-up slice that supplies "
            "cross-lane context while keeping the normalized adapter contract fixed."
        ),
    }


def build_follow_contract(docs: Iterable[OfficialDocMetadata]) -> dict[str, object]:
    doc_list = list(docs)
    if not doc_list:
        raise ValueError("Follow contract requires at least one document metadata entry")
    requests = []
    for meta in doc_list:
        _validate_metadata(meta)
        requests.append(
            {
                "route": meta.lane_id,
                "source": meta.source_name,
                "doc_id": meta.doc_id,
                "uri": meta.uri,
                "policy_flags": sorted(meta.policy_flags),
            }
        )
    return {
        "strategy": "bounded_official_follow",
        "requests": requests,
        "adapter_constraints": {
            "deterministic_doc_id": True,
            "tie_policy_flags": True,
        },
    }
