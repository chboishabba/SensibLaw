"""Typed, candidate-only reconciliation over external PNF enrichment results.

This module converts provider candidates into structured compatibility vectors,
pressure-aware review packets, and cross-demand overlap signals. It never closes
identity, merges local referents, promotes world entities, or treats provider
scores as authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import canonical_sha256, normalize_lookup_surface


EXTERNAL_RECONCILIATION_CONTRACT = "external-pnf-reconciliation:v0_1"


@dataclass(frozen=True)
class TypedCompatibilityVector:
    surface: str
    coarse_type: str
    temporal: str
    jurisdiction: str
    role_or_occupation: str
    relation_neighbourhood: str
    source_independence: str
    claim_completeness: str
    contradiction: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateMeet:
    demand_ref: str
    subject_ref: str
    candidate_set_ref: str
    candidate_ref: str
    provider_ref: str
    external_id: str
    vector: TypedCompatibilityVector
    evidence_refs: tuple[str, ...]
    residuals: tuple[str, ...]

    @property
    def meet_ref(self) -> str:
        return "external-typed-meet:" + canonical_sha256(
            {
                "contract": EXTERNAL_RECONCILIATION_CONTRACT,
                "demand_ref": self.demand_ref,
                "candidate_set_ref": self.candidate_set_ref,
                "candidate_ref": self.candidate_ref,
                "vector": self.vector.to_dict(),
                "evidence_refs": sorted(set(self.evidence_refs)),
                "residuals": sorted(set(self.residuals)),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "meet_ref": self.meet_ref,
            "demand_ref": self.demand_ref,
            "subject_ref": self.subject_ref,
            "candidate_set_ref": self.candidate_set_ref,
            "candidate_ref": self.candidate_ref,
            "provider_ref": self.provider_ref,
            "external_id": self.external_id,
            "compatibility": self.vector.to_dict(),
            "evidence_refs": list(self.evidence_refs),
            "residuals": list(self.residuals),
            "authority": "compatibility_only",
            "identity_closed": False,
        }


@dataclass(frozen=True)
class CandidateOverlapSignal:
    provider_ref: str
    external_id: str
    candidate_ref: str
    demand_refs: tuple[str, ...]
    subject_refs: tuple[str, ...]
    surfaces: tuple[str, ...]
    signal_kind: str
    residuals: tuple[str, ...]

    @property
    def signal_ref(self) -> str:
        return "external-overlap-signal:" + canonical_sha256(
            {
                "provider_ref": self.provider_ref,
                "external_id": self.external_id,
                "demand_refs": list(self.demand_refs),
                "subject_refs": list(self.subject_refs),
                "surfaces": list(self.surfaces),
                "signal_kind": self.signal_kind,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_ref": self.signal_ref,
            "provider_ref": self.provider_ref,
            "external_id": self.external_id,
            "candidate_ref": self.candidate_ref,
            "demand_refs": list(self.demand_refs),
            "subject_refs": list(self.subject_refs),
            "surfaces": list(self.surfaces),
            "signal_kind": self.signal_kind,
            "residuals": list(self.residuals),
            "authority": "braid_candidate_signal_only",
            "same_entity_closed": False,
        }


@dataclass(frozen=True)
class ExternalReviewPacket:
    demand_ref: str
    subject_ref: str
    surface: str
    demand_kind: str
    local_type_refs: tuple[str, ...]
    context_terms: tuple[str, ...]
    candidate_sets: tuple[Mapping[str, Any], ...]
    typed_meets: tuple[CandidateMeet, ...]
    pressure_receipts: tuple[Mapping[str, Any], ...]
    overlap_signal_refs: tuple[str, ...]
    remaining_residuals: tuple[str, ...]

    @property
    def review_packet_ref(self) -> str:
        return "external-review-packet:" + canonical_sha256(
            {
                "contract": EXTERNAL_RECONCILIATION_CONTRACT,
                "demand_ref": self.demand_ref,
                "candidate_set_refs": [
                    row.get("candidate_set_ref") for row in self.candidate_sets
                ],
                "typed_meet_refs": [row.meet_ref for row in self.typed_meets],
                "pressure_refs": [
                    row.get("pressure_ref") for row in self.pressure_receipts
                ],
                "overlap_signal_refs": list(self.overlap_signal_refs),
                "remaining_residuals": list(self.remaining_residuals),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_packet_ref": self.review_packet_ref,
            "demand_ref": self.demand_ref,
            "subject_ref": self.subject_ref,
            "surface": self.surface,
            "demand_kind": self.demand_kind,
            "local_type_refs": list(self.local_type_refs),
            "context_terms": list(self.context_terms),
            "candidate_sets": [dict(row) for row in self.candidate_sets],
            "typed_meets": [row.to_dict() for row in self.typed_meets],
            "pressure_receipts": [dict(row) for row in self.pressure_receipts],
            "overlap_signal_refs": list(self.overlap_signal_refs),
            "remaining_residuals": list(self.remaining_residuals),
            "available_actions": [
                "promote_equivalence",
                "retain_ambiguity",
                "reject_candidate",
                "request_more_evidence",
                "abstain",
            ],
            "authority": "review_required",
            "identity_closed": False,
        }


def _state(value: float | None, *, mismatch: bool = False) -> str:
    if mismatch:
        return "incompatible"
    if value is None:
        return "not_observed"
    if value >= 0.999:
        return "compatible"
    if value > 0:
        return "partially_compatible"
    return "incompatible"


def _meet_for(
    demand: Mapping[str, Any],
    candidate_set: Mapping[str, Any],
    candidate: Mapping[str, Any],
    assessment: Mapping[str, Any],
) -> CandidateMeet:
    reasons = {str(row) for row in assessment.get("reasons") or ()}
    surface_score = assessment.get("surface_score")
    type_score = assessment.get("type_score")
    vector = TypedCompatibilityVector(
        surface=_state(float(surface_score) if surface_score is not None else None),
        coarse_type=_state(
            float(type_score) if type_score is not None else None,
            mismatch="local_type_mismatch" in reasons,
        ),
        temporal="not_observed",
        jurisdiction="not_observed",
        role_or_occupation="not_observed",
        relation_neighbourhood=(
            "partially_compatible"
            if float(assessment.get("context_score") or 0.0) > 0
            else "not_observed"
        ),
        source_independence="not_evaluated",
        claim_completeness=(
            "partially_observed"
            if candidate.get("description") or candidate.get("type_refs")
            else "insufficient"
        ),
        contradiction=(
            "observed" if assessment.get("compatibility_state") == "held_incompatible" else "not_observed"
        ),
    )
    residuals = {
        "candidate_discrimination_unresolved",
        *[str(row) for row in candidate_set.get("residuals") or ()],
    }
    return CandidateMeet(
        demand_ref=str(demand["demand_ref"]),
        subject_ref=str(demand["subject_ref"]),
        candidate_set_ref=str(candidate_set["candidate_set_ref"]),
        candidate_ref=str(candidate["candidate_ref"]),
        provider_ref=str(candidate["provider_ref"]),
        external_id=str(candidate["external_id"]),
        vector=vector,
        evidence_refs=tuple(
            sorted(
                {
                    *[str(row) for row in candidate.get("evidence_refs") or ()],
                    *[str(row) for row in candidate_set.get("snapshot_refs") or ()],
                }
            )
        ),
        residuals=tuple(sorted(residuals)),
    )


def build_candidate_meets(result: Mapping[str, Any]) -> tuple[CandidateMeet, ...]:
    demand = result["demand"]
    rows: list[CandidateMeet] = []
    for candidate_set in result.get("candidate_sets") or ():
        assessments = {
            str(row["candidate_ref"]): row
            for row in candidate_set.get("assessments") or ()
        }
        for candidate in candidate_set.get("candidates") or ():
            assessment = assessments.get(str(candidate["candidate_ref"]), {})
            rows.append(_meet_for(demand, candidate_set, candidate, assessment))
    return tuple(sorted(rows, key=lambda row: row.meet_ref))


def build_overlap_signals(
    results: Sequence[Mapping[str, Any]],
) -> tuple[CandidateOverlapSignal, ...]:
    grouped: dict[tuple[str, str], list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    for result in results:
        demand = result["demand"]
        for candidate_set in result.get("candidate_sets") or ():
            for candidate in candidate_set.get("candidates") or ():
                key = (str(candidate["provider_ref"]), str(candidate["external_id"]))
                grouped.setdefault(key, []).append((demand, candidate))
    signals: list[CandidateOverlapSignal] = []
    for (provider_ref, external_id), rows in sorted(grouped.items()):
        demand_refs = tuple(sorted({str(row[0]["demand_ref"]) for row in rows}))
        subject_refs = tuple(sorted({str(row[0]["subject_ref"]) for row in rows}))
        if len(demand_refs) < 2 or len(subject_refs) < 2:
            continue
        surfaces = tuple(sorted({str(row[0]["surface"]) for row in rows}))
        normalized = {normalize_lookup_surface(row) for row in surfaces}
        signal_kind = (
            "candidate_external_identity_overlap"
            if len(normalized) > 1
            else "recurrent_surface_candidate_overlap"
        )
        candidate_ref = str(rows[0][1]["candidate_ref"])
        signals.append(
            CandidateOverlapSignal(
                provider_ref=provider_ref,
                external_id=external_id,
                candidate_ref=candidate_ref,
                demand_refs=demand_refs,
                subject_refs=subject_refs,
                surfaces=surfaces,
                signal_kind=signal_kind,
                residuals=(
                    "cross_document_equivalence_unresolved",
                    "metonymy_or_polysemy_unresolved",
                ),
            )
        )
    return tuple(signals)


def build_review_packets(
    results: Sequence[Mapping[str, Any]],
    overlaps: Sequence[CandidateOverlapSignal],
) -> tuple[ExternalReviewPacket, ...]:
    signals_by_demand: dict[str, list[str]] = {}
    for signal in overlaps:
        for demand_ref in signal.demand_refs:
            signals_by_demand.setdefault(demand_ref, []).append(signal.signal_ref)
    packets: list[ExternalReviewPacket] = []
    for result in results:
        demand = result["demand"]
        meets = build_candidate_meets(result)
        residuals = {
            *[row for candidate_set in result.get("candidate_sets") or () for row in candidate_set.get("residuals") or ()],
            "review_decision_unresolved",
        }
        packets.append(
            ExternalReviewPacket(
                demand_ref=str(demand["demand_ref"]),
                subject_ref=str(demand["subject_ref"]),
                surface=str(demand["surface"]),
                demand_kind=str(demand.get("demand_kind") or "entity_identity"),
                local_type_refs=tuple(demand.get("local_type_refs") or ()),
                context_terms=tuple(demand.get("context_terms") or ()),
                candidate_sets=tuple(result.get("candidate_sets") or ()),
                typed_meets=meets,
                pressure_receipts=tuple(result.get("pressure_receipts") or ()),
                overlap_signal_refs=tuple(sorted(signals_by_demand.get(str(demand["demand_ref"]), ()))),
                remaining_residuals=tuple(sorted(residuals)),
            )
        )
    return tuple(sorted(packets, key=lambda row: row.review_packet_ref))


def build_reconciliation_checkpoint(
    enrichment_run: Mapping[str, Any],
) -> dict[str, Any]:
    results = tuple(enrichment_run.get("results") or ())
    overlaps = build_overlap_signals(results)
    packets = build_review_packets(results, overlaps)
    meets = tuple(meet for result in results for meet in build_candidate_meets(result))
    return {
        "schema_version": "sl.external_reconciliation_checkpoint.v0_1",
        "contract_ref": EXTERNAL_RECONCILIATION_CONTRACT,
        "typed_meets": [row.to_dict() for row in meets],
        "candidate_overlap_signals": [row.to_dict() for row in overlaps],
        "review_packets": [row.to_dict() for row in packets],
        "summary": {
            "result_count": len(results),
            "typed_meet_count": len(meets),
            "candidate_overlap_signal_count": len(overlaps),
            "review_packet_count": len(packets),
            "identity_closure_count": 0,
            "world_entity_promotion_count": 0,
        },
        "authority": "review_required",
    }


__all__ = [
    "CandidateMeet",
    "CandidateOverlapSignal",
    "EXTERNAL_RECONCILIATION_CONTRACT",
    "ExternalReviewPacket",
    "TypedCompatibilityVector",
    "build_candidate_meets",
    "build_overlap_signals",
    "build_reconciliation_checkpoint",
    "build_review_packets",
]
