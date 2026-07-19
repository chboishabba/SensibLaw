"""Candidate-only external enrichment over unresolved local PNF demands.

External candidates may reduce lookup absence pressure.  They never close
identity, truth, occurrence, semantic-role, or Wikidata-edit obligations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import unicodedata
from typing import Any, Iterable, Mapping, Sequence


EXTERNAL_ENRICHMENT_CONTRACT = "external-pnf-enrichment:v0_1"
EXTERNAL_CANDIDATE_AUTHORITY = "candidate_only"


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_lookup_surface(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


@dataclass(frozen=True)
class ExternalLookupDemand:
    demand_ref: str
    subject_ref: str
    surface: str
    demand_kind: str = "entity_identity"
    language: str = "en"
    local_type_refs: tuple[str, ...] = ()
    context_terms: tuple[str, ...] = ()
    priority: int = 0
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.demand_ref or not self.subject_ref or not self.surface.strip():
            raise ValueError("external lookup demand requires refs and non-empty surface")
        if self.demand_kind not in {"entity_identity", "lexical_sense"}:
            raise ValueError("unsupported external lookup demand kind")

    @property
    def lookup_key(self) -> str:
        return canonical_sha256(
            {
                "contract": EXTERNAL_ENRICHMENT_CONTRACT,
                "kind": self.demand_kind,
                "language": self.language,
                "surface": normalize_lookup_surface(self.surface),
                "local_type_refs": sorted(set(self.local_type_refs)),
                "context_terms": sorted(
                    {normalize_lookup_surface(term) for term in self.context_terms if term}
                ),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "lookup_key": self.lookup_key,
            "authority": "lookup_request_only",
        }


@dataclass(frozen=True)
class ExternalCandidate:
    provider_ref: str
    external_id: str
    label: str
    candidate_kind: str
    description: str | None = None
    aliases: tuple[str, ...] = ()
    type_refs: tuple[str, ...] = ()
    source_url: str | None = None
    provider_score: float | None = None
    snapshot_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()

    @property
    def candidate_ref(self) -> str:
        return "external-candidate:" + canonical_sha256(
            {
                "provider_ref": self.provider_ref,
                "external_id": self.external_id,
                "label": self.label,
                "candidate_kind": self.candidate_kind,
                "aliases": sorted(set(self.aliases)),
                "type_refs": sorted(set(self.type_refs)),
                "snapshot_ref": self.snapshot_ref,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            **asdict(self),
            "candidate_ref": self.candidate_ref,
            "authority": EXTERNAL_CANDIDATE_AUTHORITY,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


@dataclass(frozen=True)
class ExternalCandidateAssessment:
    candidate_ref: str
    compatibility_state: str
    surface_score: float
    type_score: float
    context_score: float
    reasons: tuple[str, ...] = ()

    @property
    def combined_score(self) -> float:
        return round(
            0.55 * self.surface_score + 0.30 * self.type_score + 0.15 * self.context_score,
            6,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "combined_score": self.combined_score,
            "authority": "compatibility_only",
        }


@dataclass(frozen=True)
class ExternalCandidateSet:
    demand_ref: str
    subject_ref: str
    lookup_key: str
    provider_ref: str
    candidates: tuple[ExternalCandidate, ...]
    assessments: tuple[ExternalCandidateAssessment, ...]
    residuals: tuple[str, ...]
    snapshot_refs: tuple[str, ...] = ()

    @property
    def candidate_set_ref(self) -> str:
        return "external-candidate-set:" + canonical_sha256(
            {
                "contract": EXTERNAL_ENRICHMENT_CONTRACT,
                "demand_ref": self.demand_ref,
                "subject_ref": self.subject_ref,
                "lookup_key": self.lookup_key,
                "provider_ref": self.provider_ref,
                "candidate_refs": [row.candidate_ref for row in self.candidates],
                "assessment_states": [row.to_dict() for row in self.assessments],
                "residuals": sorted(set(self.residuals)),
                "snapshot_refs": sorted(set(self.snapshot_refs)),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_set_ref": self.candidate_set_ref,
            "demand_ref": self.demand_ref,
            "subject_ref": self.subject_ref,
            "lookup_key": self.lookup_key,
            "provider_ref": self.provider_ref,
            "candidates": [row.to_dict() for row in self.candidates],
            "assessments": [row.to_dict() for row in self.assessments],
            "residuals": list(self.residuals),
            "snapshot_refs": list(self.snapshot_refs),
            "authority": EXTERNAL_CANDIDATE_AUTHORITY,
            "identity_closed": False,
        }


@dataclass(frozen=True)
class PressureVector:
    lookup_absence: float
    candidate_ambiguity: float
    local_type_mismatch: float
    external_identity_unresolved: float
    lexical_sense_unresolved: float

    @property
    def total(self) -> float:
        return round(sum(asdict(self).values()), 6)

    def to_dict(self) -> dict[str, float]:
        return {**asdict(self), "total": self.total}


@dataclass(frozen=True)
class EnrichmentPressureReceipt:
    demand_ref: str
    candidate_set_ref: str
    before: PressureVector
    after: PressureVector
    residual_transitions: tuple[Mapping[str, str], ...]
    monotone: bool
    authority: str = "diagnostic_only"

    @property
    def pressure_ref(self) -> str:
        return "external-pressure:" + canonical_sha256(
            {
                "demand_ref": self.demand_ref,
                "candidate_set_ref": self.candidate_set_ref,
                "before": self.before.to_dict(),
                "after": self.after.to_dict(),
                "residual_transitions": list(self.residual_transitions),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pressure_ref": self.pressure_ref,
            "demand_ref": self.demand_ref,
            "candidate_set_ref": self.candidate_set_ref,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "residual_transitions": [dict(row) for row in self.residual_transitions],
            "monotone": self.monotone,
            "authority": self.authority,
            "demand_closed": False,
            "identity_closed": False,
        }


@dataclass(frozen=True)
class EnrichmentResult:
    demand: ExternalLookupDemand
    candidate_sets: tuple[ExternalCandidateSet, ...]
    pressure_receipts: tuple[EnrichmentPressureReceipt, ...]
    request_receipts: tuple[Mapping[str, Any], ...] = ()
    cache_state: str = "fresh"
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": EXTERNAL_ENRICHMENT_CONTRACT,
            "demand": self.demand.to_dict(),
            "candidate_sets": [row.to_dict() for row in self.candidate_sets],
            "pressure_receipts": [row.to_dict() for row in self.pressure_receipts],
            "request_receipts": [dict(row) for row in self.request_receipts],
            "cache_state": self.cache_state,
            "warnings": list(self.warnings),
            "authority": EXTERNAL_CANDIDATE_AUTHORITY,
        }


def _surface_score(surface: str, candidate: ExternalCandidate) -> float:
    target = normalize_lookup_surface(surface)
    forms = {
        normalize_lookup_surface(candidate.label),
        *(normalize_lookup_surface(alias) for alias in candidate.aliases),
    }
    if target in forms:
        return 1.0
    target_terms = set(target.split())
    best = 0.0
    for form in forms:
        terms = set(form.split())
        if not target_terms or not terms:
            continue
        best = max(best, len(target_terms & terms) / len(target_terms | terms))
    return round(best, 6)


def _type_score(demand: ExternalLookupDemand, candidate: ExternalCandidate) -> float:
    if not demand.local_type_refs or not candidate.type_refs:
        return 0.5
    expected = set(demand.local_type_refs)
    observed = set(candidate.type_refs)
    return 1.0 if expected & observed else 0.0


def _context_score(demand: ExternalLookupDemand, candidate: ExternalCandidate) -> float:
    if not demand.context_terms:
        return 0.5
    text = normalize_lookup_surface(
        " ".join(
            [candidate.label, candidate.description or "", *candidate.aliases]
        )
    )
    matched = sum(
        1
        for term in demand.context_terms
        if normalize_lookup_surface(term) in text
    )
    return round(matched / len(demand.context_terms), 6)


def assess_candidates(
    demand: ExternalLookupDemand,
    candidates: Sequence[ExternalCandidate],
) -> tuple[ExternalCandidateAssessment, ...]:
    rows: list[ExternalCandidateAssessment] = []
    for candidate in candidates:
        surface = _surface_score(demand.surface, candidate)
        type_score = _type_score(demand, candidate)
        context = _context_score(demand, candidate)
        reasons: list[str] = []
        if surface == 1.0:
            reasons.append("exact_label_or_alias")
        elif surface > 0:
            reasons.append("partial_surface_overlap")
        else:
            reasons.append("surface_mismatch")
        if type_score == 0:
            reasons.append("local_type_mismatch")
        elif type_score == 0.5:
            reasons.append("type_evidence_incomplete")
        state = "compatible_candidate" if surface > 0 and type_score > 0 else "held_incompatible"
        rows.append(
            ExternalCandidateAssessment(
                candidate_ref=candidate.candidate_ref,
                compatibility_state=state,
                surface_score=surface,
                type_score=type_score,
                context_score=context,
                reasons=tuple(reasons),
            )
        )
    return tuple(
        sorted(rows, key=lambda row: (-row.combined_score, row.candidate_ref))
    )


def build_external_candidate_set(
    demand: ExternalLookupDemand,
    *,
    provider_ref: str,
    candidates: Iterable[ExternalCandidate],
    snapshot_refs: Iterable[str] = (),
) -> tuple[ExternalCandidateSet, EnrichmentPressureReceipt]:
    ordered = tuple(
        sorted(
            {row.candidate_ref: row for row in candidates}.values(),
            key=lambda row: (normalize_lookup_surface(row.label), row.external_id),
        )
    )
    assessments = assess_candidates(demand, ordered)
    compatible_count = sum(
        row.compatibility_state == "compatible_candidate" for row in assessments
    )
    mismatch_count = sum(
        row.compatibility_state == "held_incompatible" for row in assessments
    )
    residuals = [
        "external_identity_unresolved"
        if demand.demand_kind == "entity_identity"
        else "lexical_sense_unresolved"
    ]
    residuals.append(
        "external_candidates_available" if compatible_count else "external_candidate_absent"
    )
    if compatible_count > 1:
        residuals.append("external_candidate_ambiguity")
    if mismatch_count:
        residuals.append("external_candidate_type_mismatch")
    candidate_set = ExternalCandidateSet(
        demand_ref=demand.demand_ref,
        subject_ref=demand.subject_ref,
        lookup_key=demand.lookup_key,
        provider_ref=provider_ref,
        candidates=ordered,
        assessments=assessments,
        residuals=tuple(sorted(set(residuals))),
        snapshot_refs=tuple(sorted(set(snapshot_refs))),
    )
    before = PressureVector(
        lookup_absence=1.0,
        candidate_ambiguity=0.0,
        local_type_mismatch=0.0,
        external_identity_unresolved=(1.0 if demand.demand_kind == "entity_identity" else 0.0),
        lexical_sense_unresolved=(1.0 if demand.demand_kind == "lexical_sense" else 0.0),
    )
    after = PressureVector(
        lookup_absence=(0.0 if compatible_count else 1.0),
        candidate_ambiguity=(
            round(math.log2(compatible_count), 6) if compatible_count > 1 else 0.0
        ),
        local_type_mismatch=(mismatch_count / len(assessments) if assessments else 0.0),
        external_identity_unresolved=before.external_identity_unresolved,
        lexical_sense_unresolved=before.lexical_sense_unresolved,
    )
    transitions: list[Mapping[str, str]] = []
    if compatible_count:
        transitions.append(
            {
                "residual_ref": "external_candidate_absent",
                "prior_state_ref": "open",
                "resulting_state_ref": "external_candidates_available",
            }
        )
    transitions.append(
        {
            "residual_ref": (
                "external_identity_unresolved"
                if demand.demand_kind == "entity_identity"
                else "lexical_sense_unresolved"
            ),
            "prior_state_ref": "open",
            "resulting_state_ref": "open",
        }
    )
    receipt = EnrichmentPressureReceipt(
        demand_ref=demand.demand_ref,
        candidate_set_ref=candidate_set.candidate_set_ref,
        before=before,
        after=after,
        residual_transitions=tuple(transitions),
        monotone=after.lookup_absence <= before.lookup_absence,
    )
    return candidate_set, receipt


def group_lookup_demands(
    demands: Iterable[ExternalLookupDemand],
) -> tuple[tuple[str, tuple[ExternalLookupDemand, ...]], ...]:
    grouped: dict[str, list[ExternalLookupDemand]] = {}
    for demand in demands:
        grouped.setdefault(demand.lookup_key, []).append(demand)
    return tuple(
        (key, tuple(sorted(rows, key=lambda row: row.demand_ref)))
        for key, rows in sorted(grouped.items())
    )


__all__ = [
    "EXTERNAL_CANDIDATE_AUTHORITY",
    "EXTERNAL_ENRICHMENT_CONTRACT",
    "EnrichmentPressureReceipt",
    "EnrichmentResult",
    "ExternalCandidate",
    "ExternalCandidateAssessment",
    "ExternalCandidateSet",
    "ExternalLookupDemand",
    "PressureVector",
    "assess_candidates",
    "build_external_candidate_set",
    "canonical_sha256",
    "group_lookup_demands",
    "normalize_lookup_surface",
]
