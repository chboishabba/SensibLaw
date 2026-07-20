"""Bounded differential probe for legal text through the universal PNF spine.

This module does not parse text and does not infer legal meaning from filenames,
source families, or a second legal grammar.  It consumes ordinary compiler
artifacts, projects Legal IR from already-constructed PNF, compares optional
legacy observations as a non-authoritative oracle, and plans candidate-only
entity enrichment when unresolved identity materially blocks a legal object.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import ExternalLookupDemand, canonical_sha256
from src.pnf.legal_adjunct import LegalIRObservation, project_legal_ir

LEGAL_PNF_PROBE_CONTRACT = "legal-pnf-probe:v0_1"
LEGAL_ENTITY_RESOLUTION_POLICY = "legal-entity-resolution-policy:v0_1"

_EXPECTED_COORDINATES = (
    "actor",
    "modality",
    "conduct",
    "object",
    "condition",
    "exception",
    "jurisdiction",
    "temporal_validity",
    "authority_wrapper",
)

_ENTITY_ROLE_KEYS = frozenset(
    {
        "actor",
        "bearer",
        "court",
        "decision_maker",
        "institution",
        "party",
        "subject",
        "jurisdiction",
        "authority",
    }
)


@dataclass(frozen=True)
class CoverageRow:
    coordinate: str
    pnf_present: bool
    legal_ir_present: bool
    legacy_present: bool
    state: str
    residual_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LegalEntityResolutionDecision:
    factor_ref: str
    factor_revision_ref: str
    surface: str
    state: str
    reasons: tuple[str, ...]
    blocking_legal_ir_refs: tuple[str, ...]
    requested_facets: tuple[str, ...]
    provenance_refs: tuple[str, ...]

    @property
    def should_lookup(self) -> bool:
        return self.state == "candidate_lookup_warranted"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "should_lookup": self.should_lookup,
            "authority": "planning_only",
            "identity_closed": False,
        }


def _factor_rows(artifacts: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    graph = artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {}
    return tuple(row for row in graph.get("factors") or () if isinstance(row, Mapping))


def _alternative_type_refs(factor: Mapping[str, Any]) -> tuple[str, ...]:
    refs: set[str] = set()
    for alternative in factor.get("alternatives") or ():
        if not isinstance(alternative, Mapping):
            continue
        type_ref = str(alternative.get("type_ref") or "")
        if type_ref:
            refs.add(type_ref)
        value = alternative.get("value")
        if isinstance(value, Mapping):
            family = str(value.get("semantic_family") or "")
            local_type = str(value.get("local_type") or "")
            if family:
                refs.add("semantic-family:" + family)
            if local_type:
                refs.add(local_type)
    return tuple(sorted(refs))


def _entity_shaped(factor: Mapping[str, Any]) -> bool:
    factor_type = str(factor.get("factor_type") or factor.get("factor_type_ref") or "")
    if factor_type == "semantic.mention_identity":
        return True
    refs = _alternative_type_refs(factor)
    return any(
        marker in ref.casefold()
        for ref in refs
        for marker in (
            "semantic-family:entity",
            "named_entity",
            "proper_noun",
            "person",
            "organization",
            "institution",
            "jurisdiction",
            "court",
        )
    )


def _surface(factor: Mapping[str, Any], artifacts: Mapping[str, Any]) -> str:
    metadata = factor.get("metadata") or {}
    if isinstance(metadata, Mapping):
        for key in ("canonical_surface", "surface", "text"):
            if metadata.get(key):
                return str(metadata[key]).strip()
        mention_ref = str(metadata.get("mention_ref") or "")
    else:
        mention_ref = ""
    mentions = (artifacts.get("licensing") or {}).get("mentions") or ()
    for mention in mentions:
        if not isinstance(mention, Mapping):
            continue
        if mention_ref and str(mention.get("mention_ref") or "") != mention_ref:
            continue
        value = str(mention.get("canonical_surface") or "").strip()
        if value:
            return value
    return ""


def _legal_role_references(
    legal_ir: Sequence[LegalIRObservation],
) -> dict[str, tuple[str, ...]]:
    references: dict[str, set[str]] = {}
    for observation in legal_ir:
        for role, factor_ref in observation.role_bindings.items():
            if role.casefold() not in _ENTITY_ROLE_KEYS:
                continue
            references.setdefault(str(factor_ref), set()).add(observation.observation_ref)
    return {key: tuple(sorted(value)) for key, value in references.items()}


def plan_legal_entity_resolution(
    artifacts: Mapping[str, Any],
    legal_ir: Sequence[LegalIRObservation],
) -> tuple[LegalEntityResolutionDecision, ...]:
    """Plan Wikidata work only when identity blocks a legal structure.

    A proper noun or entity-shaped factor is not sufficient.  The factor must
    retain external-identity pressure and be referenced by a legal PNF role, or
    carry an explicit legal identity blocking residual.  The output is a lookup
    proposal only and never closes identity.
    """

    role_refs = _legal_role_references(legal_ir)
    decisions: list[LegalEntityResolutionDecision] = []
    for factor in _factor_rows(artifacts):
        factor_ref = str(factor.get("factor_ref") or "")
        metadata = factor.get("metadata") or {}
        revision_ref = str(
            (metadata.get("factor_revision_ref") if isinstance(metadata, Mapping) else "")
            or factor.get("factor_revision_ref")
            or factor_ref
        )
        residuals = {str(value) for value in factor.get("residuals") or ()}
        blockers = role_refs.get(factor_ref, ())
        legal_blocker = bool(
            residuals.intersection(
                {
                    "legal_entity_identity_unresolved",
                    "legal_authority_identity_unresolved",
                    "jurisdiction_identity_unresolved",
                    "party_identity_unresolved",
                }
            )
        )
        reasons: list[str] = []
        state = "not_warranted"
        surface = _surface(factor, artifacts)
        if not _entity_shaped(factor):
            reasons.append("factor_not_entity_shaped")
        elif "external_identity_unresolved" not in residuals and not legal_blocker:
            reasons.append("external_identity_not_open")
        elif not blockers and not legal_blocker:
            reasons.append("identity_does_not_block_legal_structure")
        elif not surface:
            reasons.append("surface_unavailable")
            state = "blocked_missing_surface"
        else:
            reasons.extend(("entity_identity_open", "legal_coordinate_blocked"))
            state = "candidate_lookup_warranted"
        decisions.append(
            LegalEntityResolutionDecision(
                factor_ref=factor_ref,
                factor_revision_ref=revision_ref,
                surface=surface,
                state=state,
                reasons=tuple(reasons),
                blocking_legal_ir_refs=blockers,
                requested_facets=("external_identity_unresolved",),
                provenance_refs=(revision_ref, LEGAL_ENTITY_RESOLUTION_POLICY),
            )
        )
    return tuple(sorted(decisions, key=lambda row: (row.state, row.factor_ref)))


def legal_entity_lookup_demands(
    decisions: Iterable[LegalEntityResolutionDecision],
) -> tuple[ExternalLookupDemand, ...]:
    demands: list[ExternalLookupDemand] = []
    for decision in decisions:
        if not decision.should_lookup:
            continue
        demand_ref = "legal-entity-demand:" + canonical_sha256(decision.to_dict())
        demands.append(
            ExternalLookupDemand(
                demand_ref=demand_ref,
                subject_ref=decision.factor_ref,
                surface=decision.surface,
                demand_kind="entity_identity",
                local_type_refs=("semantic.legal_role_entity",),
                context_terms=("legal_role",),
                priority=90,
                provenance_refs=decision.provenance_refs,
            )
        )
    return tuple(sorted(demands, key=lambda row: (-row.priority, row.demand_ref)))


def _legacy_features(legacy_rows: Sequence[Mapping[str, Any]]) -> set[str]:
    features: set[str] = set()
    for row in legacy_rows:
        if row.get("actor"):
            features.add("actor")
        if row.get("modality") or row.get("type"):
            features.add("modality")
        if row.get("action"):
            features.add("conduct")
        if row.get("object") or row.get("obj"):
            features.add("object")
        if row.get("conditions"):
            features.add("condition")
        if any(
            str(item.get("type") or "") in {"unless", "except", "exception"}
            for item in row.get("conditions") or ()
            if isinstance(item, Mapping)
        ):
            features.add("exception")
        if row.get("scopes"):
            features.add("jurisdiction")
        if row.get("lifecycle"):
            features.add("temporal_validity")
        if row.get("references") or row.get("reference_identities"):
            features.add("authority_wrapper")
    return features


def _pnf_features(factors: Sequence[Mapping[str, Any]]) -> set[str]:
    features: set[str] = set()
    for factor in factors:
        factor_type = str(factor.get("factor_type") or factor.get("factor_type_ref") or "")
        metadata = factor.get("metadata") or {}
        role = str(metadata.get("role") or "") if isinstance(metadata, Mapping) else ""
        if role in {"subject", "actor", "agent", "bearer"}:
            features.add("actor")
        if factor_type == "semantic.eventuality" or "conduct" in factor_type:
            features.add("conduct")
        if role in {"object", "patient", "theme"}:
            features.add("object")
        if factor_type == "semantic.normative_relation":
            features.add("modality")
        if factor_type == "semantic.legal_condition":
            features.add("condition")
        if factor_type == "semantic.legal_exception":
            features.add("exception")
        if factor_type in {"semantic.legal_authority", "semantic.judicial_treatment"}:
            features.add("authority_wrapper")
        if factor_type == "semantic.legal_transition":
            features.add("temporal_validity")
        if "jurisdiction" in factor_type or role == "jurisdiction":
            features.add("jurisdiction")
    return features


def _legal_ir_features(rows: Sequence[LegalIRObservation]) -> set[str]:
    features: set[str] = set()
    for row in rows:
        roles = {key.casefold() for key in row.role_bindings}
        if roles.intersection({"actor", "bearer", "court", "party"}):
            features.add("actor")
        if roles.intersection({"conduct", "action", "predicate"}):
            features.add("conduct")
        if roles.intersection({"object", "patient", "theme"}):
            features.add("object")
        if row.qualifier_state.get("modality") or "normative" in row.predicate_ref:
            features.add("modality")
        if row.qualifier_state.get("condition_ref"):
            features.add("condition")
        if row.qualifier_state.get("exception_ref"):
            features.add("exception")
        if row.wrapper_state.get("jurisdiction_ref"):
            features.add("jurisdiction")
        if row.wrapper_state.get("validity_interval"):
            features.add("temporal_validity")
        if row.wrapper_state.get("authority_class"):
            features.add("authority_wrapper")
    return features


def build_legal_pnf_probe(
    compilation: Mapping[str, Any],
    *,
    legacy_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a deterministic probe ledger from one document compilation."""

    artifacts = compilation.get("artifacts") or compilation
    factors = _factor_rows(artifacts)
    legal_ir = project_legal_ir(factors)
    pnf_features = _pnf_features(factors)
    ir_features = _legal_ir_features(legal_ir)
    legacy_features = _legacy_features(legacy_rows)
    coverage: list[CoverageRow] = []
    for coordinate in _EXPECTED_COORDINATES:
        pnf_present = coordinate in pnf_features
        ir_present = coordinate in ir_features
        legacy_present = coordinate in legacy_features
        residuals: list[str] = []
        if legacy_present and not pnf_present:
            residuals.append(f"legacy_{coordinate}_candidate_not_reconstructed_in_pnf")
        if pnf_present and not ir_present and coordinate not in {"conduct", "actor", "object"}:
            residuals.append(f"pnf_{coordinate}_not_projected_to_legal_ir")
        state = (
            "pnf_and_legal_ir"
            if pnf_present and ir_present
            else "pnf_only"
            if pnf_present
            else "legacy_only_gap"
            if legacy_present
            else "not_observed"
        )
        coverage.append(
            CoverageRow(
                coordinate=coordinate,
                pnf_present=pnf_present,
                legal_ir_present=ir_present,
                legacy_present=legacy_present,
                state=state,
                residual_refs=tuple(residuals),
            )
        )
    entity_decisions = plan_legal_entity_resolution(artifacts, legal_ir)
    entity_demands = legal_entity_lookup_demands(entity_decisions)
    payload = {
        "schema_version": "sl.legal_pnf_probe.v0_1",
        "contract_ref": LEGAL_PNF_PROBE_CONTRACT,
        "document_ref": compilation.get("document_ref"),
        "canonical_text": artifacts.get("canonical_text"),
        "parser_receipt": artifacts.get("parser_receipt") or {},
        "parser_observations": artifacts.get("semantic_annotation_layer") or {},
        "relational_bundle": artifacts.get("relational_bundle") or {},
        "pnf_graph": artifacts.get("pnf_graph") or {},
        "refined_pnf_graph": artifacts.get("refined_pnf_graph") or {},
        "legal_ir": [row.to_dict() for row in legal_ir],
        "legacy_observations": list(legacy_rows),
        "comparison_ledger": [row.to_dict() for row in coverage],
        "entity_resolution_decisions": [row.to_dict() for row in entity_decisions],
        "wikidata_lookup_demands": [row.to_dict() for row in entity_demands],
        "summary": {
            "pnf_factor_count": len(factors),
            "legal_ir_observation_count": len(legal_ir),
            "legacy_observation_count": len(legacy_rows),
            "coverage_gap_count": sum(bool(row.residual_refs) for row in coverage),
            "wikidata_lookup_demand_count": len(entity_demands),
            "identity_closure_count": 0,
            "legal_conclusion_promotion_count": 0,
        },
        "authority": "diagnostic_only",
    }
    payload["probe_ref"] = "legal-pnf-probe:" + canonical_sha256(payload)
    return payload


__all__ = [
    "LEGAL_ENTITY_RESOLUTION_POLICY",
    "LEGAL_PNF_PROBE_CONTRACT",
    "CoverageRow",
    "LegalEntityResolutionDecision",
    "build_legal_pnf_probe",
    "legal_entity_lookup_demands",
    "plan_legal_entity_resolution",
]
