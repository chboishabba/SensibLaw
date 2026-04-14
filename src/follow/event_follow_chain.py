from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventFollowInput:
    event_id: str
    event_summary: str
    un_charter_article: str
    icj_case_id: str
    domestic_permission_source: str
    domestic_permission_scope: str


def build_event_follow_unit(input_data: EventFollowInput) -> dict[str, Any]:
    return {
        "scope": "bounded event -> UN Charter -> ICJ interpretation follow unit",
        "chain": {
            "event": {
                "id": input_data.event_id,
                "summary": input_data.event_summary,
                "source_family": "domestic_event_log",
            },
            "un_charter": {
                "article": input_data.un_charter_article,
                "source_family": "un_charter",
                "authority_type": "treaty",
            },
            "icj": {
                "case_id": input_data.icj_case_id,
                "source_family": "icj_cases",
                "authority_type": "international_judgment",
            },
            "domestic_permission": {
                "source": input_data.domestic_permission_source,
                "scope": input_data.domestic_permission_scope,
                "international_validity": False,
            },
        },
        "separation": {
            "international_validity": True,
            "domestic_permission_isolated": True,
        },
    }
