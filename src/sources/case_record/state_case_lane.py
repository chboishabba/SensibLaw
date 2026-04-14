"""Bounded state case-law surface built atop the normalized case follow contract."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .case_follow_contract import (
    case_record_follow_contract,
    normalize_case_record_follow_input,
)


STATE_CASES: dict[str, dict[str, Any]] = {
    "case:us:ca:supreme:2008:mitchell": {
        "case_id": "cl:us:ca:mitchell_v_state",
        "title": "Mitchell v. State",
        "citation": "42 Cal.4th 123 (2008)",
        "court": "Supreme Court of California",
        "date": "2008-03-04",
        "summary": "Clarified the threshold for federal preemption when state agencies rely on federal grants.",
        "state_authority": "California Constitution art. I, § 1",
        "domestic_overlay": ["calif:preemption_supremacy", "us-federal:grant-condition"],
        "crossrefs": ["art. I § 1", "42 U.S.C. § 1983"],
        "lineage_links": ["instrument:calconst:art1", "instrument:federal:1983"],
        "translation_notes": ["English text only; official version preserved."],
        "source_family": "courtlistener_state_cases",
    },
    "case:us:ny:appellate:2011:rivera": {
        "case_id": "cl:us:ny:rivera_v_department",
        "title": "Rivera v. Department of State",
        "citation": "82 A.D.3d 214 (2011)",
        "court": "New York Appellate Division",
        "date": "2011-06-21",
        "summary": "Reviewed the scope of state executive enforcement powers when parallel federal guidance exists.",
        "state_authority": "New York Executive Law § 8",
        "domestic_overlay": ["ny:executive_state_power"],
        "crossrefs": ["Executive Law § 8", "US Const. art. II"],
        "lineage_links": ["instrument:exec-law-§8"],
        "translation_notes": ["State-produced PDF is English text with embedded metadata."],
        "source_family": "courtlistener_state_cases",
    },
}


def build_state_case_follow(case_key: str) -> dict[str, Any]:
    """Return a normalized state case record conforming to the shared case follow contract."""

    case_data = STATE_CASES.get(case_key)
    if case_data is None:
        raise KeyError(f"Unknown state case key: {case_key}")

    follow_input_payload = {
        "case_id": case_data["case_id"],
        "court": case_data["court"],
        "title": case_data["title"],
        "summary_snippet": case_data["summary"],
        "crossrefs": case_data["crossrefs"],
        "lineage_links": case_data["lineage_links"],
        "translation_notes": case_data["translation_notes"],
    }
    normalized_input = normalize_case_record_follow_input(follow_input_payload)
    contract = case_record_follow_contract()

    return {
        "state_case_key": case_key,
        "state_case": dict(case_data),
        "follow_contract": contract,
        "normalized_follow_input": asdict(normalized_input),
        "source_family": case_data["source_family"],
        "domestic_overlays": list(case_data["domestic_overlay"]),
        "justification": (
            "State courts are surfaced through the same normalized case follow contract to keep "
            "the authority scope explicit and bounded within domestic authority layers."
        ),
    }


__all__ = ["STATE_CASES", "build_state_case_follow"]
