"""Consumer gate from SensibLaw residuals into Lee-style proof-search work.

The gate is intentionally small and runtime-neutral. It does not perform search.
It decides whether a reviewed PredicatePNF comparison leaves a live controversy
coordinate that may be compiled into downstream evidence-search work.

Exact common ground is zero search work. Partial, no-typed-meet and contradiction
remain distinct residual classes; none is silently converted into a factual
conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


_LIVE_RESIDUALS = frozenset({"partial", "no_typed_meet", "contradiction"})


@dataclass(frozen=True, slots=True)
class LeeResidualSearchDecision:
    residual_level: str
    shared_coordinate: bool
    live_controversy: bool
    evidence_search_authorised: bool
    search_reason: str
    world_truth_claimed: bool = False
    party_admission_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "residual_level": self.residual_level,
            "shared_coordinate": self.shared_coordinate,
            "live_controversy": self.live_controversy,
            "evidence_search_authorised": self.evidence_search_authorised,
            "search_reason": self.search_reason,
            "world_truth_claimed": self.world_truth_claimed,
            "party_admission_claimed": self.party_admission_claimed,
        }


def lee_search_decision_for_residual(
    residual: Mapping[str, Any],
) -> LeeResidualSearchDecision:
    level = str(residual.get("level") or "").strip().lower()
    if level not in {"exact", *_LIVE_RESIDUALS}:
        raise ValueError(f"unsupported residual level: {level!r}")

    if level == "exact":
        return LeeResidualSearchDecision(
            residual_level=level,
            shared_coordinate=True,
            live_controversy=False,
            evidence_search_authorised=False,
            search_reason="typed coordinate already shared; no controversy probe required",
        )

    reason = {
        "partial": "typed coordinate is incompletely supported; acquire the missing coordinate",
        "no_typed_meet": "sources do not yet share a typed comparison fibre; acquire a discriminator before alignment",
        "contradiction": "explicit typed conflict remains; acquire evidence directed at the conflicting coordinate",
    }[level]
    return LeeResidualSearchDecision(
        residual_level=level,
        shared_coordinate=False,
        live_controversy=True,
        evidence_search_authorised=True,
        search_reason=reason,
    )


def project_fact_probe_to_lee_search(
    probe: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a fact-intake probe into shared coordinates and live residual work."""

    decisions: list[dict[str, Any]] = []
    for case in probe.get("cases") or ():
        if not isinstance(case, Mapping):
            continue
        level = str(case.get("aggregate_residual") or "").strip().lower()
        decision = lee_search_decision_for_residual({"level": level})
        decisions.append(
            {
                "case_id": str(case.get("case_id") or ""),
                "fact_id": str(
                    (case.get("fact_candidate") or {}).get("fact_id")
                    if isinstance(case.get("fact_candidate"), Mapping)
                    else ""
                ),
                **decision.to_dict(),
            }
        )

    live = [row for row in decisions if row["live_controversy"]]
    shared = [row for row in decisions if row["shared_coordinate"]]
    return {
        "schema_version": "sl.lee_residual_search_gate.v0_1",
        "decisions": decisions,
        "shared_coordinate_count": len(shared),
        "live_controversy_count": len(live),
        "evidence_search_work_count": sum(
            1 for row in decisions if row["evidence_search_authorised"]
        ),
        "authority_boundary": {
            "exact_meet_implies_world_truth": False,
            "exact_meet_implies_party_admission": False,
            "exact_meet_generates_search_work": False,
            "non_exact_residual_generates_fact": False,
            "search_is_residual_indexed": True,
        },
    }


__all__ = [
    "LeeResidualSearchDecision",
    "lee_search_decision_for_residual",
    "project_fact_probe_to_lee_search",
]
