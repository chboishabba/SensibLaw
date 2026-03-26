from __future__ import annotations

from typing import Any


NORMALIZED_PROFILE_BY_ID: dict[str, dict[str, Any]] = {
    "au": {
        "review_item_status_key": "coverage_status",
        "review_item_status_map": {
            "covered": "accepted",
            "partial": "review_required",
            "unsupported_affidavit": "review_required",
            "contested_source": "held",
            "abstained_source": "held",
        },
        "source_status_key": "review_status",
        "source_status_map": {
            "covered": "accepted",
            "missing_review": "review_required",
            "contested_source": "held",
            "abstained_source": "held",
        },
        "primary_workload_map": {
            "chronology_gap": "event_or_time_pressure",
            "event_extraction_gap": "event_or_time_pressure",
            "evidence_gap": "evidence_pressure",
            "normalization_gap": "normalization_pressure",
            "review_queue_only": "queue_pressure",
        },
        "presence_workload_map": {
            "chronology_gap": "event_or_time_pressure",
            "event_extraction_gap": "event_or_time_pressure",
            "evidence_gap": "evidence_pressure",
            "normalization_gap": "normalization_pressure",
            "review_queue_only": "queue_pressure",
        },
    },
    "wikidata": {
        "review_item_status_key": "review_status",
        "review_item_status_map": {
            "baseline": "accepted",
            "promoted": "accepted",
            "review_required": "review_required",
        },
        "source_status_key": "review_status",
        "source_status_map": {
            "baseline": "accepted",
            "promoted": "accepted",
            "review_required": "review_required",
        },
        "primary_workload_map": {
            "structural_contradiction": "structural_pressure",
            "qualifier_drift_gap": "structural_pressure",
            "governance_gap": "governance_pressure",
        },
        "presence_workload_map": {
            "structural_contradiction": "structural_pressure",
            "qualifier_drift_gap": "structural_pressure",
            "governance_gap": "governance_pressure",
        },
    },
    "gwb": {
        "review_item_status_key": "coverage_status",
        "review_item_status_map": {
            "covered": "accepted",
            "partial": "review_required",
            "unsupported": "review_required",
        },
        "source_status_key": "review_status",
        "source_status_map": {
            "covered": "accepted",
            "missing_review": "review_required",
        },
        "primary_workload_map": {
            "linkage_gap": "linkage_pressure",
            "surface_resolution_gap": "linkage_pressure",
            "event_extraction_gap": "event_or_time_pressure",
        },
        "presence_workload_map": {
            "linkage_gap": "linkage_pressure",
            "surface_resolution_gap": "linkage_pressure",
            "event_extraction_gap": "event_or_time_pressure",
        },
    },
}


def get_normalized_profile(profile_id: str) -> dict[str, Any]:
    try:
        return NORMALIZED_PROFILE_BY_ID[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown normalized review profile: {profile_id}") from exc
