from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class RegionalTreatyAuthority:
    authority_id: str
    authority_name: str
    treaty_label: str
    portal_label: str
    portal_url: str
    treaty_type: str
    signature_year: int
    canonical_query_keys: tuple[str, ...]
    description: str
    language: str = "en"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def build_follow_payload(self, focus_clause: str) -> dict[str, object]:
        return {
            "authority": self.authority_name,
            "treaty_label": self.treaty_label,
            "focus_clause": focus_clause,
            "portal": {
                "label": self.portal_label,
                "url": self.portal_url,
                "canonical_query_keys": list(self.canonical_query_keys),
            },
            "metadata": {
                "treaty_type": self.treaty_type,
                "signature_year": self.signature_year,
                "language": self.language,
            },
        }


def arab_regional_treaty_follow_contract() -> dict[str, object]:
    return {
        "scope": "bounded GCC/Arab League treaty follow",
        "constraints": [
            "limited to explicit Gulf Cooperation Council or League of Arab States treaties",
            "no additional regional families added without explicit lane alignment",
            "authority signal mapped to treaty anchor entries, not arbitrary gazette texts",
        ],
        "priority": "maintain deterministic treaty_id anchors",
        "justification": (
            "Captures regional Arab treaty authorities (GCC charter, League of Arab States defense protocol) "
            "via an existing normalized follow contract without implying wider coverage."
        ),
    }


def canonical_arab_regional_treaties() -> list[RegionalTreatyAuthority]:
    return [
        RegionalTreatyAuthority(
            authority_id="gulf-cooperation-council-charter",
            authority_name="Gulf Cooperation Council",
            treaty_label="Charter of the Gulf Cooperation Council",
            portal_label="arab_regional_treaty.gcc",
            portal_url="https://gulfcooperationcouncil.org/en/charter",
            treaty_type="regional_charter",
            signature_year=1981,
            canonical_query_keys=("article", "clause"),
            description="Official GCC charter portal with structured Articles/Clauses.",
        ),
        RegionalTreatyAuthority(
            authority_id="arab-league-collective-security",
            authority_name="League of Arab States",
            treaty_label="Treaty of Joint Arab Defense and Economic Cooperation",
            portal_label="arab_regional_treaty.league",
            portal_url="https://lasportal.org/en/treaties/joint-defense",
            treaty_type="collective_security",
            signature_year=1950,
            canonical_query_keys=("treaty_section", "annex"),
            description="League of Arab States treaty portal with signed instruments metadata.",
        ),
    ]


def canonical_arab_regional_follow_payloads(focus_clause: str) -> list[dict[str, object]]:
    return [treaty.build_follow_payload(focus_clause) for treaty in canonical_arab_regional_treaties()]
