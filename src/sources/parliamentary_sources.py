from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class ParliamentarySource:
    name: str
    jurisdiction: str
    source_family: str
    base_url: str
    source_kind: str
    binding_nature: str
    proof_context: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical_parliamentary_sources() -> list[dict[str, str]]:
    sources: Iterable[ParliamentarySource] = (
        ParliamentarySource(
            name="UK House of Commons Hansard",
            jurisdiction="UK",
            source_family="uk_parliament",
            base_url="https://hansard.parliament.uk/commons",
            source_kind="debate_transcript",
            binding_nature="interpretive",
            proof_context="Iraq/Brexit debate framing feeds into statute review within the legal follow proof path",
        ),
        ParliamentarySource(
            name="UK House of Lords Hansard",
            jurisdiction="UK",
            source_family="uk_parliament",
            base_url="https://hansard.parliament.uk/lords",
            source_kind="debate_transcript",
            binding_nature="interpretive",
            proof_context="Iraq/Brexit debate narratives provide extrinsic context feeding into statutory proof arcs",
        ),
        ParliamentarySource(
            name="UK Select Committee Reports",
            jurisdiction="UK",
            source_family="uk_parliament",
            base_url="https://committees.parliament.uk/publications/",
            source_kind="committee_report",
            binding_nature="interpretive",
            proof_context="Iraq/Brexit committee outputs connect debate reasoning to statute and case evidence in the proof chain",
        ),
    )
    return [source.to_dict() for source in sources]
