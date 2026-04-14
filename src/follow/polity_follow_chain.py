from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolityFollowInput:
    seed_id: str
    seed_source_family: str
    parent_authority: str
    child_implementation: str
    adjudication_jurisdiction: str
    adjudication_outcome: str


def build_polity_follow_chain(input_data: PolityFollowInput) -> dict[str, object]:
    return {
        "seed": {
            "id": input_data.seed_id,
            "source_family": input_data.seed_source_family,
            "scope": "normalized seed",
        },
        "graph": {
            "parent_authority": {
                "name": input_data.parent_authority,
                "role": "parent",
                "signal": "authority_reference",
            },
            "child_implementation": {
                "name": input_data.child_implementation,
                "role": "implementation",
                "signal": "child_normative_action",
            },
            "adjudication": {
                "jurisdiction": input_data.adjudication_jurisdiction,
                "outcome": input_data.adjudication_outcome,
                "signal": "adjudicative_resolve",
            },
        },
        "polity_alignment": "tracked",
    }
