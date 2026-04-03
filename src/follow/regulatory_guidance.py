from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RegulatoryGuidanceUnit:
    source_id: str
    title: str
    regulator: str
    policy_framework: str
    compliance_influence: str
    binding_law_reference: str | None = None
    interpretive_note: str | None = None


def build_regulatory_guidance_unit(input_data: RegulatoryGuidanceUnit) -> Mapping[str, object]:
    return {
        "source_id": input_data.source_id,
        "title": input_data.title,
        "source_family": "regulator_guidance",
        "normative_influence": {
            "compliance": input_data.compliance_influence,
            "interpretive": input_data.interpretive_note or "soft guidance",
        },
        "policy_framework": input_data.policy_framework,
        "regulator": input_data.regulator,
        "binding_law_reference": input_data.binding_law_reference,
        "doc_type": "soft-law",
        "separation": {
            "binding_law": bool(input_data.binding_law_reference),
            "non_binding": True,
        },
    }
