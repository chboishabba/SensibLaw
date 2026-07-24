"""Lawful Legal, timeline, and retrieval projections from resolved PNF.

Only explicitly resolved PNF may project. Missing domain coordinates become typed
projection demands that return to the PNF resolution frontier. Memory and NASHI
projections are deliberately absent.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.pnf.domain_ir import (
    DomainIRBuild,
    DomainIRProjection,
    DomainIRProjectionContract,
    DomainIRProjectionReceipt,
    DomainIRProjectionResult,
    ProjectionDemand,
    ProjectionLossReceipt,
    refs,
)
from src.pnf.semantic_lifecycle import ResolutionReceipt


LEGAL_IR_CONTRACT = DomainIRProjectionContract(
    domain="legal",
    accepted_factor_families=("semantic.normative_relation", "semantic.legal.*"),
    required_ontology_axis_refs=(),
    required_statement_roles=("main",),
    preserved_fields=(
        "predicate_ref",
        "role_bindings",
        "qualifier_state",
        "jurisdiction",
        "temporal_force",
        "provenance_refs",
        "residual_refs",
        "structural_signature_ref",
    ),
    forgotten_fields=(
        "unselected_alternatives",
        "parser_execution_metadata",
        "nonlegal_ontology_axes",
    ),
    authority_ceiling="legal_ir_candidate",
    residual_policy="block_required_coordinates_retain_other_residuals",
)
TIMELINE_IR_CONTRACT = DomainIRProjectionContract(
    domain="timeline",
    accepted_factor_families=(
        "semantic.event",
        "semantic.eventuality",
        "semantic.legal_transition",
        "semantic.legal_condition",
        "semantic.legal_exception",
    ),
    required_ontology_axis_refs=(),
    required_statement_roles=("main",),
    preserved_fields=(
        "predicate_ref",
        "role_bindings",
        "qualifier_state",
        "event_time",
        "publication_time",
        "provenance_refs",
        "residual_refs",
        "structural_signature_ref",
    ),
    forgotten_fields=("unselected_alternatives", "parser_execution_metadata"),
    authority_ceiling="timeline_ir_candidate",
    residual_policy="block_temporal_identity_retain_partial_order_residuals",
)
RETRIEVAL_IR_CONTRACT = DomainIRProjectionContract(
    domain="retrieval",
    accepted_factor_families=("*",),
    required_ontology_axis_refs=(),
    required_statement_roles=(),
    preserved_fields=(
        "predicate_ref",
        "role_bindings",
        "qualifier_state",
        "provenance_refs",
        "source_span_refs",
        "ontology_axis_refs",
        "structural_signature_ref",
    ),
    forgotten_fields=("unselected_alternatives", "execution_metadata"),
    authority_ceiling="retrieval_ir_candidate",
    residual_policy="retain_residuals_without_promoting_semantic_identity",
)
DEFAULT_DOMAIN_IR_CONTRACTS = (
    LEGAL_IR_CONTRACT,
    RETRIEVAL_IR_CONTRACT,
    TIMELINE_IR_CONTRACT,
)


def _get(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, Mapping) else getattr(
        value, name, default
    )


def _mapping(value: Any, name: str) -> dict[str, Any]:
    candidate = _get(value, name, {})
    return dict(candidate) if isinstance(candidate, Mapping) else {}


def _metadata(factor: Any) -> dict[str, Any]:
    return _mapping(factor, "metadata")


def _factor_type(factor: Any) -> str:
    return str(
        _get(factor, "factor_type_ref", "")
        or _get(factor, "factor_type", "")
        or ""
    )


def _factor_ref(factor: Any) -> str:
    return str(_get(factor, "factor_ref", "") or "")


def _signature(factor: Any) -> str:
    metadata = _metadata(factor)
    return str(
        _get(factor, "structural_signature", "")
        or metadata.get("structural_signature_ref")
        or metadata.get("signature_ref")
        or ""
    )


def _roles(factor: Any) -> dict[str, str]:
    direct = _mapping(factor, "role_bindings")
    values = direct or dict(_metadata(factor).get("role_bindings") or {})
    return {str(key): str(value) for key, value in values.items() if str(value)}


def _qualifiers(factor: Any) -> dict[str, Any]:
    return _mapping(factor, "qualifier_state") or dict(
        _metadata(factor).get("qualifier_state") or {}
    )


def _residuals(factor: Any) -> tuple[str, ...]:
    return refs(_get(factor, "residuals", ()) or ())


def _selected(
    resolution: ResolutionReceipt, proposals: Mapping[str, Any]
) -> Any | None:
    return (
        proposals.get(resolution.selected_proposal_ref)
        if resolution.selected_proposal_ref
        else None
    )


def _statement_role(proposal: Any | None) -> str:
    return str(_get(proposal, "statement_role", "main") or "main")


def _axes(factor: Any, proposal: Any | None) -> tuple[str, ...]:
    values = list(_metadata(factor).get("ontology_axis_refs") or ())
    if proposal is not None:
        values.extend(_get(proposal, "ontology_axis_refs", ()) or ())
    return refs(values)


def _provenance(factor: Any, proposal: Any | None) -> tuple[str, ...]:
    values = list(_metadata(factor).get("provenance_refs") or ())
    if proposal is not None:
        for name in (
            "source_span_refs",
            "input_observation_refs",
            "dependency_factor_refs",
            "transport_refs",
            "ontology_axis_refs",
        ):
            values.extend(_get(proposal, name, ()) or ())
    return refs(values)


def _demand(
    resolution: ResolutionReceipt,
    factor: Any,
    domain: str,
    kind: str,
    required: Iterable[str],
    observed: Iterable[str],
    message: str,
    priority: int = 50,
) -> ProjectionDemand:
    return ProjectionDemand(
        document_ref=resolution.document_ref,
        domain=domain,
        resolution_ref=resolution.resolution_ref,
        source_factor_ref=_factor_ref(factor) or resolution.fibre_summary_ref,
        structural_signature_ref=_signature(factor),
        demand_kind=kind,
        required_refs=refs(required),
        observed_refs=refs(observed),
        message=message,
        priority=priority,
    )


def _common_demands(
    resolution: ResolutionReceipt,
    factor: Any | None,
    proposal: Any | None,
    contract: DomainIRProjectionContract,
) -> list[ProjectionDemand]:
    if not resolution.operationally_resolved:
        kind = {
            "blocked_conflict": "conflicting_interpretations",
            "retained_plural": "plural_interpretations",
        }.get(resolution.state, "insufficient_semantic_coverage")
        return [
            ProjectionDemand(
                document_ref=resolution.document_ref,
                domain=contract.domain,
                resolution_ref=resolution.resolution_ref,
                source_factor_ref=resolution.fibre_summary_ref,
                structural_signature_ref="",
                demand_kind=kind,
                required_refs=resolution.admitted_proposal_refs,
                observed_refs=resolution.retained_alternative_refs,
                message=(
                    "Domain IR requires resolved PNF; "
                    f"current state is {resolution.state}."
                ),
                priority=90,
            )
        ]
    if factor is None:
        return [
            ProjectionDemand(
                document_ref=resolution.document_ref,
                domain=contract.domain,
                resolution_ref=resolution.resolution_ref,
                source_factor_ref=resolution.fibre_summary_ref,
                structural_signature_ref="",
                demand_kind="materialized_factor_missing",
                required_refs=(resolution.fibre_summary_ref,),
                observed_refs=(),
                message="Resolved PNF has no matching materialized factor.",
                priority=100,
            )
        ]
    demands: list[ProjectionDemand] = []
    role = _statement_role(proposal)
    if contract.required_statement_roles and role not in contract.required_statement_roles:
        demands.append(
            _demand(
                resolution,
                factor,
                contract.domain,
                "statement_role_inapplicable",
                contract.required_statement_roles,
                (role,),
                f"{contract.domain} projection is undefined for role {role}.",
            )
        )
    available_axes = _axes(factor, proposal)
    missing_axes = set(contract.required_ontology_axis_refs) - set(available_axes)
    if missing_axes:
        demands.append(
            _demand(
                resolution,
                factor,
                contract.domain,
                "ontology_axis_missing",
                missing_axes,
                available_axes,
                "Required ontology-axis classifications are unresolved.",
                80,
            )
        )
    return demands


def _legal_demands(
    resolution: ResolutionReceipt, factor: Any
) -> list[ProjectionDemand]:
    roles, qualifiers = _roles(factor), _qualifiers(factor)
    residuals, factor_type = set(_residuals(factor)), _factor_type(factor)
    demands: list[ProjectionDemand] = []
    jurisdiction = (
        roles.get("jurisdiction")
        or str(qualifiers.get("jurisdiction_ref") or "")
        or str(qualifiers.get("jurisdiction") or "")
    )
    if not jurisdiction or "jurisdiction_unresolved" in residuals:
        demands.append(
            _demand(
                resolution,
                factor,
                "legal",
                "missing_jurisdiction",
                ("role:jurisdiction", "qualifier:jurisdiction_ref"),
                (*roles, *qualifiers),
                "Legal IR requires an explicit jurisdiction coordinate.",
                100,
            )
        )
    if factor_type == "semantic.normative_relation":
        if not (roles.get("bearer") or roles.get("actor") or roles.get("subject")):
            demands.append(
                _demand(
                    resolution,
                    factor,
                    "legal",
                    "unresolved_actor_role",
                    ("role:bearer", "role:actor"),
                    roles,
                    "Normative Legal IR requires a resolved bearer or actor.",
                    90,
                )
            )
        if not roles.get("conduct"):
            demands.append(
                _demand(
                    resolution,
                    factor,
                    "legal",
                    "unresolved_conduct_role",
                    ("role:conduct",),
                    roles,
                    "Normative Legal IR requires a resolved conduct.",
                    90,
                )
            )
        modality = str(qualifiers.get("modality") or "")
        if modality in {"", "permission_candidate"} or "modal_sense_unresolved" in residuals:
            demands.append(
                _demand(
                    resolution,
                    factor,
                    "legal",
                    "conflicting_modality",
                    ("qualifier:resolved_modality",),
                    (modality,),
                    "Operative legal modality remains unresolved.",
                    90,
                )
            )
    if factor_type == "semantic.legal_exception" and not roles.get("host"):
        demands.append(
            _demand(
                resolution,
                factor,
                "legal",
                "unresolved_exception_host",
                ("role:host",),
                roles,
                "A legal exception cannot project without its host.",
                95,
            )
        )
    if factor_type == "semantic.legal_transition":
        temporal = (
            str(qualifiers.get("effective_time_ref") or "")
            or str(qualifiers.get("effective_time") or "")
        )
        if not temporal or {
            "effective_time_unresolved",
            "legal_time_unresolved",
        }.intersection(residuals):
            demands.append(
                _demand(
                    resolution,
                    factor,
                    "legal",
                    "missing_temporal_force",
                    ("qualifier:effective_time_ref",),
                    qualifiers,
                    "Legal transition requires a resolved effective time.",
                    100,
                )
            )
    if factor_type == "semantic.legal_authority":
        authority = roles.get("authority") or str(
            qualifiers.get("authority_ref") or ""
        )
        if not authority:
            demands.append(
                _demand(
                    resolution,
                    factor,
                    "legal",
                    "missing_authority_source",
                    ("role:authority", "qualifier:authority_ref"),
                    (*roles, *qualifiers),
                    "Legal authority projection requires a source authority.",
                    100,
                )
            )
    return demands


def _timeline_demands(
    resolution: ResolutionReceipt, factor: Any
) -> list[ProjectionDemand]:
    qualifiers, residuals = _qualifiers(factor), set(_residuals(factor))
    temporal = [
        qualifiers[name]
        for name in (
            "event_time",
            "effective_time",
            "effective_time_ref",
            "publication_time",
            "observation_time",
        )
        if qualifiers.get(name)
    ]
    unresolved = {
        "effective_time_unresolved",
        "event_time_unresolved",
        "temporal_scope_unresolved",
    }
    if temporal and not unresolved.intersection(residuals):
        return []
    return [
        _demand(
            resolution,
            factor,
            "timeline",
            "missing_temporal_coordinate",
            ("qualifier:event_time", "qualifier:effective_time"),
            (*qualifiers, *residuals),
            "Timeline IR requires a resolved temporal coordinate.",
            80,
        )
    ]


def _retrieval_demands(
    resolution: ResolutionReceipt, factor: Any, proposal: Any | None
) -> list[ProjectionDemand]:
    if _provenance(factor, proposal):
        return []
    return [
        _demand(
            resolution,
            factor,
            "retrieval",
            "missing_source_binding",
            ("source_span_ref", "provenance_ref"),
            (),
            "Retrieval IR requires a source-bound PNF witness.",
            70,
        )
    ]


def project_resolved_factor(
    *,
    resolution: ResolutionReceipt,
    factors: Mapping[str, Any],
    proposals: Mapping[str, Any],
    contract: DomainIRProjectionContract,
) -> DomainIRProjectionResult:
    factor = factors.get(resolution.fibre_summary_ref)
    proposal = _selected(resolution, proposals)
    if factor is not None and not contract.accepts(_factor_type(factor)):
        receipt = DomainIRProjectionReceipt(
            document_ref=resolution.document_ref,
            domain=contract.domain,
            source_resolution_ref=resolution.resolution_ref,
            source_factor_ref=_factor_ref(factor),
            projection_contract_ref=contract.contract_ref,
            state="inapplicable",
            selected_proposal_ref=resolution.selected_proposal_ref,
            demand_refs=(),
            loss_ref=None,
            reason_refs=("factor_family_inapplicable",),
        )
        return DomainIRProjectionResult(contract, None, receipt, None, ())

    demands = _common_demands(resolution, factor, proposal, contract)
    if factor is not None and resolution.operationally_resolved:
        if contract.domain == "legal":
            demands.extend(_legal_demands(resolution, factor))
        elif contract.domain == "timeline":
            demands.extend(_timeline_demands(resolution, factor))
        else:
            demands.extend(_retrieval_demands(resolution, factor, proposal))
    demands = list(
        sorted({row.demand_ref: row for row in demands}.values(), key=lambda row: row.demand_ref)
    )
    if demands or factor is None or proposal is None:
        receipt = DomainIRProjectionReceipt(
            document_ref=resolution.document_ref,
            domain=contract.domain,
            source_resolution_ref=resolution.resolution_ref,
            source_factor_ref=(
                _factor_ref(factor) if factor is not None
                else resolution.fibre_summary_ref
            ),
            projection_contract_ref=contract.contract_ref,
            state="blocked",
            selected_proposal_ref=resolution.selected_proposal_ref,
            demand_refs=refs(row.demand_ref for row in demands),
            loss_ref=None,
            reason_refs=refs(
                (
                    *resolution.unresolved_residual_refs,
                    *(row.demand_kind for row in demands),
                )
            ),
        )
        return DomainIRProjectionResult(
            contract, None, receipt, None, tuple(demands)
        )

    roles, qualifiers, metadata = (
        _roles(factor),
        _qualifiers(factor),
        _metadata(factor),
    )
    provenance = _provenance(factor, proposal)
    residuals = refs((*_residuals(factor), *resolution.unresolved_residual_refs))
    loss = ProjectionLossReceipt(
        document_ref=resolution.document_ref,
        domain=contract.domain,
        source_resolution_ref=resolution.resolution_ref,
        projection_contract_ref=contract.contract_ref,
        preserved_fields=contract.preserved_fields,
        forgotten_fields=contract.forgotten_fields,
        source_residual_refs=residuals,
    )
    receipt = DomainIRProjectionReceipt(
        document_ref=resolution.document_ref,
        domain=contract.domain,
        source_resolution_ref=resolution.resolution_ref,
        source_factor_ref=_factor_ref(factor),
        projection_contract_ref=contract.contract_ref,
        state="projected",
        selected_proposal_ref=resolution.selected_proposal_ref,
        demand_refs=(),
        loss_ref=loss.loss_ref,
        reason_refs=(
            resolution.resolution_ref,
            resolution.selected_proposal_ref,
            contract.contract_ref,
        ),
    )
    candidate_payload = _get(proposal, "candidate_payload", {})
    predicate = (
        str(candidate_payload.get("predicate_ref") or "")
        if isinstance(candidate_payload, Mapping)
        else ""
    ) or str(metadata.get("predicate_ref") or _factor_type(factor))
    payload: dict[str, Any] = {
        "factor_type_ref": _factor_type(factor),
        "predicate_ref": predicate,
        "role_bindings": roles,
        "qualifier_state": qualifiers,
        "statement_role": _statement_role(proposal),
        "ontology_axis_refs": list(_axes(factor, proposal)),
        "source_span_refs": list(
            refs(_get(proposal, "source_span_refs", ()) or ())
        ),
    }
    if contract.domain == "legal":
        payload.update(
            {
                "jurisdiction_ref": (
                    roles.get("jurisdiction")
                    or str(qualifiers.get("jurisdiction_ref") or "")
                    or str(qualifiers.get("jurisdiction") or "")
                ),
                "temporal_force_ref": (
                    str(qualifiers.get("effective_time_ref") or "")
                    or str(qualifiers.get("effective_time") or "")
                ),
                "authority_ceiling": contract.authority_ceiling,
            }
        )
    elif contract.domain == "timeline":
        payload["temporal_coordinates"] = {
            name: qualifiers[name]
            for name in (
                "event_time",
                "effective_time",
                "effective_time_ref",
                "publication_time",
                "observation_time",
            )
            if name in qualifiers
        }
    else:
        payload["retrieval_keys"] = sorted(
            {
                str(value)
                for value in (
                    *roles.values(),
                    predicate,
                    *payload["source_span_refs"],
                )
                if str(value)
            }
        )
    projection = DomainIRProjection(
        document_ref=resolution.document_ref,
        domain=contract.domain,
        source_resolution_ref=resolution.resolution_ref,
        source_factor_ref=_factor_ref(factor),
        selected_proposal_ref=resolution.selected_proposal_ref,
        structural_signature_ref=_signature(factor),
        projection_contract_ref=contract.contract_ref,
        projection_receipt_ref=receipt.receipt_ref,
        loss_ref=loss.loss_ref,
        payload=payload,
        provenance_refs=provenance,
        residual_refs=residuals,
    )
    return DomainIRProjectionResult(contract, projection, receipt, loss, ())


def _factor_index(factors: Sequence[Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for factor in factors:
        factor_ref = _factor_ref(factor)
        summary_ref = str(_metadata(factor).get("fibre_summary_ref") or "")
        if factor_ref:
            output[factor_ref] = factor
        if summary_ref:
            output[summary_ref] = factor
    return output


def build_domain_ir(
    *,
    document_ref: str,
    resolutions: Sequence[ResolutionReceipt],
    factors: Sequence[Any],
    proposals: Sequence[Any],
    contracts: Sequence[
        DomainIRProjectionContract
    ] = DEFAULT_DOMAIN_IR_CONTRACTS,
) -> DomainIRBuild:
    factor_by_ref = _factor_index(factors)
    proposal_by_ref = {
        str(_get(row, "proposal_ref", "") or ""): row
        for row in proposals
        if _get(row, "proposal_ref", "")
    }
    results = tuple(
        project_resolved_factor(
            resolution=resolution,
            factors=factor_by_ref,
            proposals=proposal_by_ref,
            contract=contract,
        )
        for resolution in resolutions
        for contract in contracts
    )
    return DomainIRBuild(
        document_ref=document_ref,
        contracts=tuple(sorted(contracts, key=lambda row: row.contract_ref)),
        projections=tuple(
            sorted(
                (row.projection for row in results if row.projection is not None),
                key=lambda row: row.domain_ir_ref,
            )
        ),
        receipts=tuple(
            sorted((row.receipt for row in results), key=lambda row: row.receipt_ref)
        ),
        losses=tuple(
            sorted(
                (row.loss for row in results if row.loss is not None),
                key=lambda row: row.loss_ref,
            )
        ),
        demands=tuple(
            sorted(
                {
                    demand.demand_ref: demand
                    for row in results
                    for demand in row.demands
                }.values(),
                key=lambda row: row.demand_ref,
            )
        ),
    )


__all__ = [
    "DEFAULT_DOMAIN_IR_CONTRACTS",
    "LEGAL_IR_CONTRACT",
    "RETRIEVAL_IR_CONTRACT",
    "TIMELINE_IR_CONTRACT",
    "build_domain_ir",
    "project_resolved_factor",
]
