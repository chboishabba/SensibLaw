from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class NormSourceCategory:
    identifier: str
    label: str
    description: str
    enforcement_level: str
    influence_type: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical_norm_source_categories() -> list[dict[str, str]]:
    categories: Iterable[NormSourceCategory] = (
        NormSourceCategory(
            identifier="standard",
            label="Technical or industry standard",
            description="Norm-setting documents with formalized requirements but often delegated enforcement",
            enforcement_level="soft",
            influence_type="normative",
        ),
        NormSourceCategory(
            identifier="inquiry_report",
            label="Inquiry or commission report",
            description="Formal fact-finding outputs that shape policy discourse",
            enforcement_level="soft",
            influence_type="evidentiary",
        ),
        NormSourceCategory(
            identifier="regulatory_guidance",
            label="Regulatory guidance",
            description="Agency-issued procedural directions that accompany hard law but may not carry direct sanctions",
            enforcement_level="soft",
            influence_type="directive",
        ),
        NormSourceCategory(
            identifier="policy_framework",
            label="Policy or soft-law framework",
            description="High-level guidance articulating future intent without binding force",
            enforcement_level="soft",
            influence_type="strategic",
        ),
    )
    return [category.to_dict() for category in categories]
