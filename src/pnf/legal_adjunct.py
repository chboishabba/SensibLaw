"""PNF-driven legal adjunct demand, Legal IR, and typed-meet algebra.

There is no legal parser in this module. Every input is already a span-grounded
PNF row produced by the one canonical parser spine. Legal IR is a downstream
projection of those PNF rows, and acquisition plans are emitted only from
explicit legal facets or explicit operator demands.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import canonical_sha256

LEGAL_ADJUNCT_CONTRACT = "pnf-legal-adjunct:v0_1"
LEGAL_IR_PROJECTION_CONTRACT = "legal-ir-from-pnf:v0_1"

_LEGAL_TRIGGER_FACETS = frozenset(
    {
        "legal.relevance_unresolved",
        "legal.authority_absent",
        "legal.applicability_unresolved",
        "legal.interpretation_unresolved",
    }
)
_LEGAL_PNF_TYPES = frozenset(
    {
        "semantic.normative_relation",
        "semantic.legal_condition",
        "semantic.legal_exception",
        "semantic.legal_burden",
        "semantic.legal_authority",
        "semantic.legal_transition",
        "semantic.judicial_treatment",
    }
)


def _values_with_prefix(values: Iterable[str], prefix: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                value[len(prefix) :]
                for value in values
                if value.startswith(prefix) and value[len(prefix) :]
            }
        )
    )


@dataclass(frozen=True)
class NormativeInteractionDemand:
    """Typed request for legal evidence derived from PNF or an explicit call."""

    demand_ref: str
    origin_pnf_ref: str
    interaction_signature_ref: str
    jurisdiction_refs: tuple[str, ...]
    temporal_refs: tuple[str, ...]
    source_role_refs: tuple[str, ...]
    authority_level_refs: tuple[str, ...]
    requested_legal_facets: tuple[str, ...]
    provider_profile_refs: tuple[str, ...]
    open_slots: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    priority: int = 50
    explicit: bool = False

    @property
    def acquisition_ready(self) -> bool:
        return bool(
            self.jurisdiction_refs
            and self.source_role_refs
            and self.authority_level_refs
            and not self.open_slots
        )

    @property
    def plan_key(self) -> str:
        return canonical_sha256(
            {
                "contract": LEGAL_ADJUNCT_CONTRACT,
                "interaction_signature_ref": self.interaction_signature_ref,
                "jurisdiction_refs": self.jurisdiction_refs,
                "temporal_refs": self.temporal_refs,
                "source_role_refs": self.source_role_refs,
                "authority_level_refs": self.authority_level_refs,
                "requested_legal_facets": self.requested_legal_facets,
                "provider_profile_refs": self.provider_profile_refs,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "acquisition_ready": self.acquisition_ready,
            "plan_key": self.plan_key,
            "authority": "demand_only",
        }


@dataclass(frozen=True)
class LegalSourcePlan:
    demand_ref: str
    plan_key: str
    jurisdiction_ref: str
    source_role_refs: tuple[str, ...]
    authority_level_refs: tuple[str, ...]
    provider_profile_refs: tuple[str, ...]
    requested_legal_facets: tuple[str, ...]
    temporal_refs: tuple[str, ...]
    state: str
    blocked_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "authority": "acquisition_plan_only"}


@dataclass(frozen=True)
class LegalIRObservation:
    """Operational Legal IR row projected from one PNF revision."""

    observation_ref: str
    pnf_factor_ref: str
    pnf_revision_ref: str
    structural_signature_ref: str
    predicate_ref: str
    role_bindings: Mapping[str, str]
    qualifier_state: Mapping[str, Any]
    wrapper_state: Mapping[str, Any]
    provenance_refs: tuple[str, ...]
    residual_refs: tuple[str, ...]
    projection_state: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "role_bindings": dict(self.role_bindings),
            "qualifier_state": dict(self.qualifier_state),
            "wrapper_state": dict(self.wrapper_state),
            "authority": "pnf_projection_only",
        }


@dataclass(frozen=True)
class LegalTypedMeet:
    world_pnf_ref: str
    legal_ir_ref: str
    structural_state: str
    jurisdiction_state: str
    temporal_state: str
    actor_state: str
    conduct_state: str
    object_state: str
    circumstance_state: str
    exception_state: str
    burden_state: str
    residual_refs: tuple[str, ...]

    @property
    def applicability_closed(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "applicability_closed": False,
            "violation_closed": False,
            "liability_closed": False,
            "authority": "typed_comparison_only",
        }


def project_normative_interaction_demands(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[NormativeInteractionDemand, ...]:
    """Project legal work only from explicit normalized legal facets.

    A predicate lemma such as ``drive`` is insufficient. The source row must
    carry a legal trigger facet, or be marked as an explicit operator request.
    Namespaced facets supply jurisdiction, time, source role, authority level,
    provider profile, and requested legal work without a hard-coded action map.
    """

    projected: dict[tuple[str, str], NormativeInteractionDemand] = {}
    for row in rows:
        facets = tuple(sorted({str(value) for value in row.get("requested_facets") or ()}))
        explicit = bool(row.get("explicit_legal_request"))
        if not explicit and not _LEGAL_TRIGGER_FACETS.intersection(facets):
            continue
        demand_ref = str(row.get("demand_ref") or "")
        origin_ref = str(
            row.get("factor_revision_ref")
            or row.get("origin_pnf_ref")
            or row.get("factor_ref")
            or ""
        )
        signature_ref = str(row.get("structural_signature_ref") or "")
        if not demand_ref or not origin_ref or not signature_ref:
            continue
        jurisdictions = _values_with_prefix(facets, "legal.jurisdiction:")
        temporal_refs = _values_with_prefix(facets, "legal.time:")
        source_roles = _values_with_prefix(facets, "legal.source_role:")
        authority_levels = _values_with_prefix(facets, "legal.authority_level:")
        providers = _values_with_prefix(facets, "legal.provider_profile:")
        requested = tuple(
            sorted(
                _LEGAL_TRIGGER_FACETS.intersection(facets)
                | set(_values_with_prefix(facets, "legal.request:"))
            )
        )
        open_slots: list[str] = []
        if not jurisdictions:
            open_slots.append("jurisdiction_unresolved")
        if not source_roles:
            open_slots.append("source_role_unresolved")
        if not authority_levels:
            open_slots.append("authority_level_unresolved")
        demand = NormativeInteractionDemand(
            demand_ref=demand_ref,
            origin_pnf_ref=origin_ref,
            interaction_signature_ref=signature_ref,
            jurisdiction_refs=jurisdictions,
            temporal_refs=temporal_refs,
            source_role_refs=source_roles,
            authority_level_refs=authority_levels,
            requested_legal_facets=requested,
            provider_profile_refs=providers,
            open_slots=tuple(open_slots),
            provenance_refs=tuple(
                sorted(
                    {
                        origin_ref,
                        LEGAL_ADJUNCT_CONTRACT,
                        *(str(value) for value in row.get("provenance_refs") or ()),
                    }
                )
            ),
            priority=int(row.get("priority") or (100 if explicit else 50)),
            explicit=explicit,
        )
        projected[(demand.demand_ref, demand.plan_key)] = demand
    return tuple(
        sorted(
            projected.values(),
            key=lambda item: (-item.priority, item.demand_ref, item.plan_key),
        )
    )


def plan_legal_sources(
    demands: Iterable[NormativeInteractionDemand],
) -> tuple[LegalSourcePlan, ...]:
    plans: list[LegalSourcePlan] = []
    for demand in demands:
        blocked = demand.open_slots
        plans.append(
            LegalSourcePlan(
                demand_ref=demand.demand_ref,
                plan_key=demand.plan_key,
                jurisdiction_ref=demand.jurisdiction_refs[0] if demand.jurisdiction_refs else "",
                source_role_refs=demand.source_role_refs,
                authority_level_refs=demand.authority_level_refs,
                provider_profile_refs=demand.provider_profile_refs,
                requested_legal_facets=demand.requested_legal_facets,
                temporal_refs=demand.temporal_refs,
                state="ready" if demand.acquisition_ready else "blocked_missing_context",
                blocked_reasons=blocked,
            )
        )
    return tuple(plans)


def project_legal_ir(rows: Iterable[Mapping[str, Any]]) -> tuple[LegalIRObservation, ...]:
    """Project Legal IR from already-constructed PNF rows.

    Rows without a legal PNF factor type are ignored. This deliberately refuses
    to infer legal meaning from source family, filename, or isolated lemmas.
    """

    projected: dict[str, LegalIRObservation] = {}
    for row in rows:
        factor_type = str(row.get("factor_type_ref") or "")
        if factor_type not in _LEGAL_PNF_TYPES and not factor_type.startswith("semantic.legal."):
            continue
        factor_ref = str(row.get("factor_ref") or "")
        revision_ref = str(row.get("factor_revision_ref") or "")
        signature_ref = str(row.get("structural_signature_ref") or "")
        predicate_ref = str(row.get("predicate_ref") or factor_type)
        if not factor_ref or not revision_ref or not signature_ref:
            continue
        identity = {
            "contract": LEGAL_IR_PROJECTION_CONTRACT,
            "factor_ref": factor_ref,
            "factor_revision_ref": revision_ref,
            "structural_signature_ref": signature_ref,
        }
        observation_ref = "legal-ir-observation:" + canonical_sha256(identity)
        projected[observation_ref] = LegalIRObservation(
            observation_ref=observation_ref,
            pnf_factor_ref=factor_ref,
            pnf_revision_ref=revision_ref,
            structural_signature_ref=signature_ref,
            predicate_ref=predicate_ref,
            role_bindings=dict(row.get("role_bindings") or {}),
            qualifier_state=dict(row.get("qualifier_state") or {}),
            wrapper_state=dict(row.get("wrapper_state") or {}),
            provenance_refs=tuple(sorted(str(value) for value in row.get("provenance_refs") or ())),
            residual_refs=tuple(sorted(str(value) for value in row.get("residual_refs") or ())),
        )
    return tuple(sorted(projected.values(), key=lambda item: item.observation_ref))


def typed_legal_meet(
    world_row: Mapping[str, Any],
    legal_observation: LegalIRObservation,
) -> LegalTypedMeet:
    world_signature = str(world_row.get("structural_signature_ref") or "")
    if not world_signature or world_signature != legal_observation.structural_signature_ref:
        return LegalTypedMeet(
            world_pnf_ref=str(world_row.get("factor_revision_ref") or world_row.get("factor_ref") or ""),
            legal_ir_ref=legal_observation.observation_ref,
            structural_state="NO_TYPED_MEET",
            jurisdiction_state="not_evaluated",
            temporal_state="not_evaluated",
            actor_state="not_evaluated",
            conduct_state="not_evaluated",
            object_state="not_evaluated",
            circumstance_state="not_evaluated",
            exception_state="not_evaluated",
            burden_state="not_evaluated",
            residual_refs=("cross_fibre_incommensurable",),
        )
    coordinates = dict(world_row.get("legal_coordinates") or {})
    return LegalTypedMeet(
        world_pnf_ref=str(world_row.get("factor_revision_ref") or world_row.get("factor_ref") or ""),
        legal_ir_ref=legal_observation.observation_ref,
        structural_state="same_fibre_candidate",
        jurisdiction_state=str(coordinates.get("jurisdiction_state") or "unresolved"),
        temporal_state=str(coordinates.get("temporal_state") or "unresolved"),
        actor_state=str(coordinates.get("actor_state") or "unresolved"),
        conduct_state=str(coordinates.get("conduct_state") or "unresolved"),
        object_state=str(coordinates.get("object_state") or "unresolved"),
        circumstance_state=str(coordinates.get("circumstance_state") or "unresolved"),
        exception_state=str(coordinates.get("exception_state") or "unresolved"),
        burden_state=str(coordinates.get("burden_state") or "unresolved"),
        residual_refs=tuple(
            sorted(
                {
                    "legal_applicability_unresolved",
                    "exception_status_unresolved",
                    "burden_status_unresolved",
                }
            )
        ),
    )


__all__ = [
    "LEGAL_ADJUNCT_CONTRACT",
    "LEGAL_IR_PROJECTION_CONTRACT",
    "LegalIRObservation",
    "LegalSourcePlan",
    "LegalTypedMeet",
    "NormativeInteractionDemand",
    "plan_legal_sources",
    "project_legal_ir",
    "project_normative_interaction_demands",
    "typed_legal_meet",
]
