from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PolityEdge:
    parent: str
    child: str
    adjudication: str


POLITY_GRAPH: Mapping[str, Mapping[str, PolityEdge]] = {
    "EU": {
        "national_gov": PolityEdge(
            parent="EU",
            child="national_gov",
            adjudication="CJEU opinion",
        )
    },
    "RU": {
        "regional_federal_subject": PolityEdge(
            parent="Russian Federation",
            child="regional_federal_subject",
            adjudication="Supreme Court of Russian Federation",
        )
    },
    "PIF": {
        "member_state": PolityEdge(
            parent="Pacific Islands Forum",
            child="member_state",
            adjudication="PIF Council decision",
        )
    },
    "GCC": {
        "member_state": PolityEdge(
            parent="Gulf Cooperation Council",
            child="member_state",
            adjudication="GCC Ministerial Council",
        )
    },
    "US": {
        "state": PolityEdge(
            parent="United States Federal",
            child="state",
            adjudication="US Supreme Court",
        )
    },
    "AU": {
        "state_territory": PolityEdge(
            parent="Australian Commonwealth",
            child="state_territory",
            adjudication="High Court of Australia",
        ),
    },
}
